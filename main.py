import logging
import json
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

import vk_api
import uvicorn
from vk_api.exceptions import VkApiError
from vk_api.utils import get_random_id
from pydantic import BaseModel, field_validator

import credentials

def setup_logging():
    """Настраивает логирование в файл и консоль"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = logging.DEBUG if True else logging.INFO

    # Базовый конфиг
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )

    # Дополнительно в файл, если включено
    if True:
        file_handler = logging.FileHandler(
            "vk_bot.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)

    return logging.getLogger(__name__)


logger = setup_logging()

class VKMessage(BaseModel):
    """Модель входящего сообщения VK"""
    from_id: int
    text: str = ""
    peer_id: int
    id: int
    conversation_message_id: int
    payload: Optional[str] = None

    class Config:
        extra = "ignore"  # Игнорировать лишние поля от VK


class CallbackEvent(BaseModel):
    """Модель события Callback API"""
    type: str
    group_id: int
    object: Dict[str, Any]
    secret: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Модель запроса на отправку сообщения через API"""
    user_id: int
    message: str
    keyboard: Optional[Dict] = None

    @field_validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Сообщение не может быть пустым')
        return v.strip()


class CommandInfo(BaseModel):
    """Информация о команде бота"""
    name: str
    description: str
    aliases: List[str] = []


# ===== ИНИЦИАЛИЗАЦИЯ VK API =====
class VKManager:
    """Менеджер для работы с VK API"""

    def __init__(self):
        self.vk_session = None
        self.vk = None
        self.group_id = None
        self.bot_name = None
        self.init_vk()

    def init_vk(self):
        """Инициализация подключения к VK API"""
        try:
            if not credentials.VK_PRED_TOKEN:
                raise ValueError("VK_TOKEN не указан в credentials.py")

            # Создаем сессию
            self.vk_session = vk_api.VkApi(token=credentials.VK_PRED_TOKEN)
            self.vk = self.vk_session.get_api()

            # Проверяем подключение
            user_info = self.vk.users.get()
            self.bot_name = f"{user_info[0]['first_name']} {user_info[0]['last_name']}"

            logger.info(f"Успешное подключение к VK API. Бот: {self.bot_name}")

        except Exception as e:
            logger.error(f"Ошибка при подключении к VK API: {e}")
            self.vk = None

    def send_message(self, peer_id: int, message: str,
                     keyboard: Optional[Dict] = None,
                     attachment: Optional[str] = None) -> bool:
        """Отправляет сообщение в диалог"""
        try:
            params = {
                'peer_id': peer_id,
                'message': message,
                'random_id': get_random_id(),
                'dont_parse_links': 0,
                'disable_mentions': 0,
            }

            if keyboard:
                params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)

            if attachment:
                params['attachment'] = attachment

            self.vk.messages.send(**params)
            logger.debug(f"Сообщение отправлено в {peer_id}")
            return True

        except VkApiError as e:
            logger.error(f"Ошибка VK API при отправке сообщения: {e}")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке сообщения: {e}")
            return False

    def get_user_info(self, user_ids: List[int]) -> List[Dict]:
        """Получает информацию о пользователях"""
        try:
            return self.vk.users.get(
                user_ids=user_ids,
                fields="first_name,last_name,photo_100,online"
            )
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователях: {e}")
            return []


app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация менеджера VK
vk_manager = VKManager()


# ===== МЕНЕДЖЕР КОМАНД БОТА =====
class CommandManager:
    """Менеджер команд бота"""

    def __init__(self):
        self.commands: Dict[str, CommandInfo] = {}
        self.register_default_commands()

    def register_command(self, command: CommandInfo):
        """Регистрирует новую команду"""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def register_default_commands(self):
        """Регистрирует стандартные команды"""
        default_commands = [
            CommandInfo(
                name="помощь",
                description="Показать это сообщение",
                aliases=["help", "хелп", "команды"]
            ),
            CommandInfo(
                name="инфо",
                description="Информация о боте",
                aliases=["info", "бот", "about"]
            ),
            CommandInfo(
                name="пинг",
                description="Проверка работы бота",
                aliases=["ping", "тест"]
            ),
            CommandInfo(
                name="статус",
                description="Статус бота и статистика",
                aliases=["status", "stats", "стата"]
            ),
            CommandInfo(
                name="повтори",
                description="Повторить сообщение",
                aliases=["echo", "скажи"]
            ),
        ]

        for cmd in default_commands:
            self.register_command(cmd)

    def process_command(self, text: str) -> Optional[str]:
        """Обрабатывает команду и возвращает ответ"""
        if not text.startswith("!"):
            return None

        # Убираем префикс и разбиваем на части
        cmd_text = text[len("!"):].strip()
        parts = cmd_text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Ищем команду
        if cmd_name not in self.commands:
            return None

        # Обработка команд
        if cmd_name in ["помощь", "help", "хелп", "команды"]:
            return self._help_command()

        elif cmd_name in ["инфо", "info", "бот", "about"]:
            return self._info_command()

        elif cmd_name in ["пинг", "ping", "тест"]:
            return "Бот работает корректно."

        elif cmd_name in ["статус", "status", "stats", "стата"]:
            return self._status_command()

        elif cmd_name in ["повтори", "echo", "скажи"]:
            return args if args else "Что повторить?"

        return None

    def _help_command(self) -> str:
        """Генерирует текст помощи"""
        help_text = "📚 Доступные команды:\n\n"

        shown_commands = set()
        for cmd in self.commands.values():
            if cmd.name in shown_commands:
                continue

            aliases = ", ".join(cmd.aliases) if cmd.aliases else "нет"
            help_text += f"• {"!"}{cmd.name}"
            if cmd.aliases:
                help_text += f" (или {', '.join(cmd.aliases)})"
            help_text += f" - {cmd.description}\n"
            shown_commands.add(cmd.name)

        help_text += f"\nПрефикс команд: {"!"}"
        return help_text

    def _info_command(self) -> str:
        """Генерирует информацию о боте"""
        return (
            f"VK бот\n"
            f"Версия: 2.0.0\n"
            f"Платформа: FastAPI + VK API\n"
            f"Команд: {len(set(cmd.name for cmd in self.commands.values()))}\n"
        )

    def _status_command(self) -> str:
        """Генерирует статус бота"""
        status = "Работает" if vk_manager.vk else "Не работает"
        return (
            f"Статус бота:\n"
            f"VK API: {status}\n"
            f"Имя: {vk_manager.bot_name or 'Неизвестно'}\n"
            f"Время: {datetime.now().strftime('%H:%M:%S')}\n"
            f"Команд: {len(set(cmd.name for cmd in self.commands.values()))}"
        )


command_manager = CommandManager()


# ===== ВАЛИДАЦИЯ ПОДПИСИ CALLBACK API =====
def verify_signature(signature: str, body_bytes: bytes) -> bool:
    """Проверяет подпись VK-Signature"""
    if not credentials.VK_SECRET_KEY or not signature:
        return False

    # Создаем HMAC SHA256 подпись
    hmac_obj = hmac.new(
        key=credentials.VK_SECRET_KEY.encode(),
        msg=body_bytes,
        digestmod=hashlib.sha256
    )
    expected_signature = hmac_obj.hexdigest()

    # Безопасное сравнение
    return hmac.compare_digest(f"sha256={expected_signature}", signature)


# ===== ОСНОВНЫЕ ЭНДПОИНТЫ API =====
@app.get("/")
async def root():
    """Корневой эндпоинт с информацией"""
    return {
        "service": "VK Bot API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "webhook": "/webhook (POST)",
            "api_docs": "/api/docs",
            "send_message": "/api/send (POST)"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    vk_status = "connected" if vk_manager.vk else "disconnected"

    # Пробуем отправить тестовый запрос к VK API
    if vk_manager.vk:
        try:
            vk_manager.vk.users.get()
            vk_status = "healthy"
        except Exception:
            vk_status = "error"

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "vk_api": vk_status,
        "version": "2.0.0"
    }


@app.post("/webhook")
async def vk_webhook(
        request: Request,
        x_vk_signature: Optional[str] = Header(None),
        background_tasks: BackgroundTasks = None
):
    """
    Основной эндпоинт для Callback API ВКонтакте.
    Принимает события от VK и обрабатывает их.
    """
    try:
        # Читаем тело запроса
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        data = json.loads(body_str) if body_str else {}

        logger.debug(f"Получен вебхук: {data.get('type', 'unknown')}")

        # 1. Проверяем подпись (если есть секретный ключ)
        if credentials.VK_SECRET_KEY and not verify_signature(x_vk_signature, body_bytes):
            logger.warning(f"Неверная подпись: {x_vk_signature}")
            raise HTTPException(status_code=403, detail="Invalid signature")

        # 2. Обработка подтверждения сервера
        if data.get('type') == 'confirmation':
            logger.info("Отправлен код подтверждения")
            return credentials.CONFIRMATION_CODE

        # 3. Проверяем group_id
        group_id = data.get('group_id')
        if group_id and abs(group_id) != credentials.VK_GROUP_ID:
            logger.warning(f"Неверный group_id: {group_id}")
            return "ok"  # Все равно возвращаем ok, чтобы VK не повторял

        # 4. Обрабатываем события в фоновом режиме
        if background_tasks:
            background_tasks.add_task(process_event, data)
        else:
            process_event(data)

        return "ok"

    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON")
        return "ok"
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return "ok"


def process_event(data: Dict):
    """Обрабатывает события от VK в основном потоке"""
    event_type = data.get('type')

    if event_type == 'message_new':
        handle_new_message(data['object']['message'])

    elif event_type == 'message_reply':
        logger.info(f"Ответ на сообщение: {data.get('object', {})}")

    elif event_type == 'message_allow':
        user_id = data['object']['user_id']
        logger.info(f"Пользователь {user_id} разрешил сообщения")

    elif event_type == 'message_deny':
        user_id = data['object']['user_id']
        logger.info(f"Пользователь {user_id} запретил сообщения")


def handle_new_message(message_data: Dict):
    """Обрабатывает новое входящее сообщение"""
    try:
        # Парсим данные сообщения
        message = VKMessage(**message_data)

        # Игнорируем сообщения от самого бота
        if message.from_id < 0:  # Отрицательные ID - это группы
            return

        # Логируем полученное сообщение
        user_info = vk_manager.get_user_info([message.from_id])
        user_name = f"{user_info[0]['first_name']} {user_info[0]['last_name']}" if user_info else f"id{message.from_id}"

        logger.info(f"📩 Сообщение от {user_name} ({message.from_id}): {message.text}")

        # Обрабатываем команды
        response = command_manager.process_command(message.text)

        # Отправляем ответ, если есть
        if response:
            vk_manager.send_message(message.peer_id, response)
            logger.debug(f"Отправлен ответ: {response}")

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")


@app.post("/api/send")
async def api_send_message(request: SendMessageRequest):
    """
    API эндпоинт для отправки сообщений через бота.
    Требует авторизации (можно добавить позже).
    """
    try:
        success = vk_manager.send_message(
            peer_id=request.user_id,
            message=request.message,
            keyboard=request.keyboard
        )

        if success:
            return {
                "success": True,
                "message": "Сообщение отправлено",
                "user_id": request.user_id,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Ошибка отправки сообщения")

    except Exception as e:
        logger.error(f"Ошибка в API /send: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/user/{user_id}")
async def api_get_user_info(user_id: int):
    """Получение информации о пользователе VK"""
    try:
        user_info = vk_manager.get_user_info([user_id])
        if not user_info:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return {
            "success": True,
            "user": user_info[0]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":

    # Запускаем сервер
    logger.info("Запуск VK бота")
    logger.info(f"Сервер доступен по http://{"127.0.0.1"}:{5000}")
    logger.info(f"Документация API: http://{"127.0.0.1"}:{5000}/api/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5000,
        reload=True
    )

