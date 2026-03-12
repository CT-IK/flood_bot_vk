import logging
import random
import time

import vk_api
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


# Основной цикл работы
try:
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.object.message
            peer_id = message['peer_id']
            user_id = message['from_id']
            full_text = message['text'].strip()
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
            elif cmd == '!мысль':
                try:
                    members=vk.messages.getConversationMembers(peer_id=peer_id)
                    if text.startswith('['):
                        id_user = ''
                        for i in text[3:]:
                            id_user += i
                            if i == '|':
                                id_user = id_user[:-1]
                                break
                    else:
                        id_user = None
                    quote = bd.random_quote(id_user)
                    quote_text = quote[2]
                    quote_author_id = quote[1]
                    user = vk.users.get(
                        user_ids=quote_author_id,
                        fields="photo_200"
                    )[0]
                    quote_id = quote[0]
                except Exception as e:
                    logger.error(f"Ошибка команды !мысль: {e}")
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

except KeyboardInterrupt:
    logger.info("Бот остановлен")
except Exception as e:
    logger.error(f"Ошибка: {e}")