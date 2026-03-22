import logging
import random
import time
import json
import os
import io
import vk_api
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji


from datetime import datetime
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from vk_api import VkUpload

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

#создание файла для будильников
ALARM_FILE = 'alarms.json'
#перенос данных из файла в оперативную память
def load_alarms():
    if not os.path.exists(ALARM_FILE):
        return {}
    with open(ALARM_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return {}
#сохранение самих будильников
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

            #фонавая проверка будильников
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
            elif cmd == "!мысль":
                font_eb_60=ImageFont.truetype('ArialBlackPrimer.ttf', 36)
                random_quote = bd.random_quote()
                if not random_quote:
                    send_message(peer_id, "В базе еще нет сохраненных цитат!")
                    continue
                fwd_user_id = random_quote['user_id']
                fwd_text = random_quote['text']
                user_data = vk.users.get(user_ids=fwd_user_id, fields='photo_max')[0]
                fwd_user_name = f"© {user_data['first_name']} {user_data['last_name']}"
                # Настройка текста и высоты
                lines = textwrap.wrap(f'«{fwd_text}»', width=42)
                img_height = 620 + (len(lines) - 6) * 54 if (len(lines) - 6) > 0 else 620
                img = Image.new('RGB', (1080, img_height), color='black')
                # Отрисовка текста через Pilmoji
                with Pilmoji(img) as pilmoji:
                    y_text = 130
                    for line in lines:
                        pilmoji.text((50, y_text), line, font= font_eb_60, fill='white')
                        y_text += 60
                # Вставка фото автора (Requests + BytesIO)
                resp = requests.get(user_data['photo_max'])
                user_photo = Image.open(io.BytesIO(resp.content)).convert("RGBA").resize((110, 110))
                mask = Image.new('L', (110, 110), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 110, 110), fill=255)
                img.paste(user_photo, (50, img_height - 135), mask)
                # Подпись даты и имени
                d = ImageDraw.Draw(img)
                d.text((180, img_height - 115), fwd_user_name, font=font_eb_60, fill='white')
                # Загрузка в ВК
                img_ptr = io.BytesIO()
                img.save(img_ptr, format='PNG')
                img_ptr.seek(0)
                upload = VkUpload(vk_session)
                photo = upload.photo_messages(photos=img_ptr)[0]
                vk.messages.send(peer_id=peer_id, random_id=0, attachment=f"photo{photo['owner_id']}_{photo['id']}")
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
                    send_message(peer_id, f"Окей, разбужу в {clean_time}")
            elif cmd == "!небудить":
                if p_id_str in active_alarms and str(user_id) in active_alarms[p_id_str]:
                    del active_alarms[p_id_str][str(user_id)]
                    save_alarms(active_alarms)
                    send_message(peer_id, "Будильник отменен.")
            elif cmd == "!будильник":
                if p_id_str in active_alarms and active_alarms[p_id_str]:
                    msg = "Будильники чата:\n"
                    for u_id, t in active_alarms[p_id_str].items():
                        msg += f"[id{u_id}|Спящий] — {t}\n"
                    send_message(peer_id, msg)
                else:
                    send_message(peer_id, "Активных будильников нет.")

except KeyboardInterrupt:
    logger.info("Бот остановлен")
except Exception as e:
    logger.error(f"Ошибка: {e}")