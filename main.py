import logging
import random
import time
import json
import os
import vk_api
from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests

from datetime import datetime
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

import credentials
import bd

active_mutes = {}
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


ALARM_FILE = 'alarms.json'

def load_alarms():
    if not os.path.exists(ALARM_FILE):
        return {}
    with open(ALARM_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return {}

def save_alarms(alarms):
    with open(ALARM_FILE, 'w', encoding='utf-8') as f:
        json.dump(alarms, f, indent=4, ensure_ascii=False)


# Авторизация по токену
VK_TOKEN = credentials.VK_TOKEN
if not VK_TOKEN:
    logger.error("Токен не найден!")
    exit(1)

bd.init_db()
# Авторизация сообщества
try:
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    logger.info("Бот успешно авторизован")
except Exception as e:
    logger.error(f"Ошибка авторизации: {e}")
    exit(1)

def create_quote_image(text, author_name, avatar_url):
    width, height = 800, 400
    img = Image.new('RGB', (width, height), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    try:
        font_text = ImageFont.load_default() # Используем стандартный
        font_author = ImageFont.load_default()
    except:
        pass

    # --- РУЧНОЙ ПЕРЕНОС СТРОК ---
    max_chars = 35  # Максимальное количество символов в строке
    words = text.split(' ') # Разбиваем текст на слова
    lines = []
    current_line = ""

    for word in words:
        # Если слово влезает в текущую строку
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line += (word + " ")
        else:
            # Если не влезает, сохраняем текущую и начинаем новую
            lines.append(current_line.strip())
            current_line = word + " "
    lines.append(current_line.strip()) # Добавляем последний кусочек
    # ----------------------------

    # Отрисовка аватарки (логика та же)
    try:
        res = requests.get(avatar_url, timeout=5)
        with open("temp_avatar.png", "wb") as f:
            f.write(res.content)
        avatar = Image.open("temp_avatar.png").convert("RGBA")
        avatar = avatar.resize((180, 180))
        mask = Image.new('L', (180, 180), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 180, 180), fill=255)
        img.paste(avatar, (50, 110), mask)
    except:
        draw.ellipse((50, 110, 230, 290), fill="gray")

    # Отрисовка строк текста
    y = 120
    for line in lines:
        draw.text((260, y), line, font=font_text, fill="white")
        y += 45 # Смещение вниз для следующей строки

    # Подпись автора
    draw.text((260, y + 20), f"— {author_name}", font=font_author, fill="gray")

    img.save('quote_result.png')
    return 'quote_result.png'

def upload_photo(peer_id, file_path, vk_session):
    """Загружает файл на сервер ВК и возвращает attachment строку."""
    upload = vk_api.VkUpload(vk_session)
    photo = upload.photo_messages(file_path)[0]
    return f"photo{photo['owner_id']}_{photo['id']}"

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

active_alarms = load_alarms()
# Основной цикл работы
try:
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.object.message
            peer_id = message['peer_id']
            user_id = message['from_id']
            full_text = message['text'].strip()

            if not full_text: continue
            p_id_str = str(peer_id)

            current_time = datetime.now().strftime("%H:%M")
            if p_id_str in active_alarms:
                for u_id_str, alarm_time in list(active_alarms[p_id_str].items()):
                    if current_time >= alarm_time:
                        send_message(peer_id, f"🔔 [id{u_id_str}|ПРОСЫПАЙСЯ!] Пора вставать, уже {alarm_time}!")
                        del active_alarms[p_id_str][u_id_str]
                        save_alarms(active_alarms)

            cmd = full_text.split()[0].lower()
            text = ' '.join(full_text.split()[1:])
            if user_id in active_mutes.keys():
                if time.time() < active_mutes[user_id]:
                    try:
                        vk.messages.delete(
                            peer_id=peer_id,
                            conversation_message_ids=message['conversation_message_id'],
                            delete_for_all=1
                        )
                    except Exception as e:
                        logger.error(f"Не удалось удалить сообщение: {e}")
                    continue
                else:
                    del active_mutes[user_id]
            if cmd == "!айди":
                if peer_id >= 2000000000:
                    chat_id = peer_id - 2000000000
                    answer = f"ID чата: {peer_id}"
                else:
                    answer = f"Это личное сообщение. ID пользователя: {user_id}"
                send_message(peer_id, answer)
            elif cmd == "!цт":
                send_message(peer_id, "БУДЕТ СВОБОДНО")
            elif cmd == "!помощь":
                send = (
                    'Команды:\n'
                    '!помощь - просмотр списка команд\n'
                    '!инфа [@username] - информация об активисте. Можно использовать ответом на сообщение\n'
                    '!разбудить\n'
                    '!не будить\n'
                    '!будильник - список разбудяшек\n'
                    '!дуэль [@username] - вызвать активиста на дуэль\n'
                    '!рулетка - испытай удачу\n'
                    '!вероятность [текст] - рассчитывает вероятность события\n'
                    '!кто — узнать, кто больше всего соответствует запросу\n'
                    '!цитата - сохраняет цитату активиста. Используйте ответом на сообщение\n'
                    '!мысль\n'
                    '!мут - мутит пользователя на 1 день. Используйте ответом на сообщение\n'
                    '!анмут - анмутит пользователя. Используйте ответом на сообщение\n'
                )
            elif cmd == "!кто":
                members = vk.messages.getConversationMembers(peer_id=peer_id)
                users = [u for u in members["profiles"] if u["id"] != -credentials.VK_GROUP_ID]
                user = random.choice(users)
                user_id_rand = user["id"]
                name = user["first_name"]
                send_message(peer_id, f"[id{user_id_rand}|{name}] {text}")
            elif cmd == "!мут":
                try:
                    members = vk.messages.getConversationMembers(peer_id=peer_id)
                    sender_is_admin = False
                    for member in members['items']:
                        if member["member_id"] == user_id:
                            if member.get("is_admin", False) or member.get("is_owner", False):
                                sender_is_admin = True
                            break
                    if not sender_is_admin:
                        send_message(peer_id, "Нельзя тебе мутить, маленький еще!")
                        continue
                    if not message.get("reply_message"):
                        send_message(peer_id, "Ответь на сообщение пользователя")
                        continue
                    mute_time = 3600 * 24
                    target_id = message["reply_message"]["from_id"]
                    end_time = time.time() + mute_time
                    active_mutes[target_id] = end_time
                    name = next((u['first_name'] for u in members['profiles'] if u['id'] == target_id), 'Пользователь')
                    send_message(peer_id, f"[id{target_id}|{name}] замучен на 1 день")
                except Exception as e:
                    logger.error(f"Ошибка команды !мут: {e}")
            elif cmd == "!анмут":
                sender_is_admin = False
                members = vk.messages.getConversationMembers(peer_id=peer_id)
                for member in members['items']:
                    if member["member_id"] == user_id:
                        if member.get("is_admin") or member.get("is_owner"):
                            sender_is_admin = True
                        break
                if not sender_is_admin:
                    send_message(peer_id, "Нельзя тебе анмутить, маленький еще!")
                    continue
                if not message.get("reply_message"):
                    send_message(peer_id, "Ответь на сообщение пользователя")
                    continue
                target_id = message["reply_message"]["from_id"]
                if target_id in active_mutes:
                    del active_mutes[target_id]
                    name = next((u['first_name'] for u in members['profiles'] if u['id'] == target_id), 'Пользователь')
                    send_message(peer_id, f"✅ [id{target_id}|{name}] был размучен")
                else:
                    send_message(peer_id, "Этот пользователь не находится в муте")
            elif cmd == "!рулетка":
                try:
                    chance = random.randint(1,6)
                    if chance != 1:
                        mute_time = 3600
                        end_time = time.time() + mute_time
                        active_mutes[user_id] = end_time
                        members = vk.messages.getConversationMembers(peer_id=peer_id)
                        name = next((u['first_name'] for u in members['profiles'] if u['id'] == user_id), 'Пользователь')
                        send_message(peer_id, f'[id{user_id}|{name}] лови бан на 1 час.')
                    else:
                        send_message(peer_id, 'Повезло, попробуй еще разок!')
                except Exception as e:
                    logger.error(f"Ошибка команды !рулетка: {e}")
            elif cmd == '!цитата':
                try:
                    if not message.get('reply_message'):
                        send_message(peer_id, 'Ответь на сообщение текстом')
                        continue
                    target_id = message['reply_message']['from_id']
                    quote_text = message['reply_message']['text']
                    bd.add_quote(target_id, quote_text)
                    send_message(peer_id, 'Цитата сохранена')
                except Exception as e:
                    logger.error(f"Ошибка команды !цитата: {e}")
            # elif cmd == "!мысль":
                # try:
                #     print(f"--- Команда !мысль вызвана пользователем {user_id} ---")
                    
                #     target_user_id = None
                #     if text.startswith("[id"):
                #         target_user_id = text.split('|')[0].replace("[id", "")
                #         print(f"Ищем цитату конкретного пользователя: {target_user_id}")
                
                #     quote = bd.random_quote(target_user_id)
                
                #     if not quote:
                #         send_message(peer_id, "💬 В базе нет подходящих цитат.")
                #         continue

                #     print(f"Цитата найдена: {quote}")
                #     # ВАЖНО: Проверь индексы! Если в БД (id, author, text), то это 1 и 2
                #     q_author_id = quote[1]
                #     q_text = quote[2]

                #     # Получаем данные автора из ВК
                #     user_data = vk.users.get(user_ids=q_author_id, fields="photo_200")[0]
                #     full_name = f"{user_data['first_name']} {user_data['last_name']}"
                #     photo_url = user_data['photo_200']

                #     print(f"Генерирую картинку для {full_name}...")
                #     path = create_quote_image(q_text, full_name, photo_url)
                
                #     print("Загружаю фото на сервер ВК...")
                #     attach = upload_photo(peer_id, path, vk_session)
                    
                #     print(f"Отправляю результат в чат {peer_id}...")
                #     send_message(peer_id, message="", attachment=attach)
                #     print("--- Успешно отправлено! ---")

                # except Exception as e:
                #     import traceback
                #     logger.error(f"Ошибка в !мысль: {e}")
                #     print(traceback.format_exc()) # Это выведет подробную ошибку в консоль
                #     send_message(peer_id, "⚠️ Ошибка при создании цитаты. Проверь консоль.")
            elif cmd == "!инфа":
                    if message.get('reply_message'):
                        data = message['reply_message']['from_id']
                    else:
                        data = text.lower()
                        data = list(data)
                        data[0] = data[0].upper()
                        data = ''.join(data)
                    user_date = bd.userdata(data)
                    if user_date == None:
                        send = 'Активист не найден'
                    else:
                        send = (
                                f'Фамилия: {user_date[1]}\n'
                                f'Имя: {user_date[2]}\n'
                                f'Отчество: {user_date[3]}\n'
                                f'Дата рождения: {''.join(user_date[5].split()[0])}\n'
                                f'Учебная группа: {user_date[6]}\n'
                                f'Номер телефона: {user_date[7]}\n'
                                f'Почта: {user_date[8]}\n'
                                f'Инста: {user_date[9]}\n'
                                f'Телега: {user_date[10]}\n'
                                f'Размер одежды: {user_date[11]}\n'
                                f'Метро: {user_date[12]}\n'
                                f'Дата прихода: {''.join(user_date[14].split()[0])}\n'
                                f'Дата ухода: {user_date[15]}\n'
                            )
                    send_message(peer_id, send)
            elif cmd.strip(',') == "!вероятность":
                chance = random.randint(0, 100)
                send_message(peer_id, f'Вероятность {text} - {chance}%')
            elif cmd == '!дуэль':
                members = vk.messages.getConversationMembers(peer_id=peer_id)
                if not text:
                    send_message(peer_id, f"[id{user_id}|Ты] забыл указать противника! Напиши: !дуэль @противник")
                    continue
                if text.startswith('['):
                        id_user = ''
                        for i in text[3:]:
                            id_user += i
                            if i == '|':
                                id_user = id_user[:-1]
                                break
                id_user = int(id_user)
                time.sleep(2)
                looser = random.choice([user_id, id_user])
                name = next((u['first_name'] for u in members['profiles'] if u['id'] == looser), 'Пользователь')
                mute_time = 3600
                end_time = time.time() + mute_time
                active_mutes[looser] = end_time
                send_message(peer_id, f"[id{looser}|{name}] застрелен. Воскрешайся через час")
                print(name)
            if cmd == "!разбудить":
                clean_time = text.strip()
                if ":" in clean_time:
                    if len(clean_time) == 4: clean_time = "0" + clean_time
                    if p_id_str not in active_alarms:
                        active_alarms[p_id_str] = {}
                    
                    active_alarms[p_id_str][str(user_id)] = clean_time
                    save_alarms(active_alarms)
                    send_message(peer_id, f"⏰ Окей, разбужу в {clean_time}")
            elif cmd == "!небудить":
                if p_id_str in active_alarms and str(user_id) in active_alarms[p_id_str]:
                    del active_alarms[p_id_str][str(user_id)]
                    save_alarms(active_alarms)
                    send_message(peer_id, "🔕 Будильник отменен.")
            elif cmd == "!будильник":
                if p_id_str in active_alarms and active_alarms[p_id_str]:
                    msg = "📋 Будильники чата:\n"
                    for u_id, t in active_alarms[p_id_str].items():
                        msg += f"• [id{u_id}|Спящий] — {t}\n"
                    send_message(peer_id, msg)
                else:
                    send_message(peer_id, "⏰ Активных будильников нет.")

except KeyboardInterrupt:
    logger.info("Бот остановлен")
except Exception as e:
    logger.error(f"Ошибка: {e}")