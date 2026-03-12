import os
from typing import Final
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

#Ключи доступа (токен преда для доступа к VK API, токен доступа группы (бота), секретный ключ сообщества и код доступа)
VK_TOKEN: Final=os.getenv("TOKEN")

#ВК айди разработчиков
DEVS: Final=000000000

#Айди преда
PRED: Final=00000000

#Айдишники чатов
CHAT_FLOOD_ID: Final=0000000
CHAT_MANAGERS_ID: Final=0000000
CHAT_TEST_ID: Final=0000000

#Для работы с VK методами
VK_GROUP_ID: Final=229101179#Важный параметр
VK_ALBUM_ID: Final=00000