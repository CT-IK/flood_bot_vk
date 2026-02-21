import logging

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

import credentials

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('vk_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)



# Авторизация по токену
VK_TOKEN = credentials.VK_TOKEN
if not VK_TOKEN:
    logger.error("Токен не найден!")
    exit(1)


# Авторизация сообщества
try:
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    logger.info("Бот успешно авторизован")
except Exception as e:
    logger.error(f"Ошибка авторизации: {e}")
    exit(1)


# Запуск лонгпулла
longpoll = VkBotLongPoll(vk_session, credentials.VK_GROUP_ID)


# Функция отправки сообщения
def send_message(peer_id, message):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id()
        )

    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")


# Основной цикл работы
try:
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.object.message
            peer_id = message['peer_id']
            user_id = message['from_id']
            text = message['text'].strip().lower()

            if text == "!айди":
                if peer_id >= 2000000000:
                    chat_id = peer_id - 2000000000
                    answer = f"ID чата: {peer_id}"
                else:
                    answer = f"Это личное сообщение. ID пользователя: {user_id}"
                send_message(peer_id, answer)

            elif text == "!цт":
                send_message(peer_id, "БУДЕТ СВОБОДНО")

except KeyboardInterrupt:
    logger.info("Бот остановлен")
except Exception as e:
    logger.error(f"Ошибка: {e}")