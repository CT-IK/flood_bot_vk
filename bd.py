import sqlite3
import random

con = sqlite3.connect('db.sqlite')
cur = con.cursor()

def init_db():
    cur.execute('''
    CREATE TABLE IF NOT EXISTS quotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT
        );
''')
    con.commit()

def add_quote(user_id, text):
    cur.execute('INSERT INTO quotes(user_id, text) VALUES(?,?);', (user_id, text))
    con.commit()

def random_quote(user_id=None):
    quote = []
    if user_id:
        results = cur.execute('''
        SELECT *
        FROM quotes
        WHERE user_id=?;''', (user_id,))
    else:
        results = cur.execute('''
        SELECT *
        FROM quotes;
        ''')       
    for result in results:
        quote.append(result)
    return random.choice(quote)

def userdata(date):
    if date.isdigit():
        query = ('SELECT * FROM database WHERE VK_ID=?')
    else:
        query = ('SELECT * FROM database WHERE surname=?')
    results = cur.execute(query, (date,))
    for result in results:
        return result
    
def init_db():
    conn = sqlite3.connect('db.sqlite') # Убедись, что имя файла совпадает с твоим
    cursor = conn.cursor()
    # Создаем таблицу для будильников
    cursor.execute('''CREATE TABLE IF NOT EXISTS alarms 
                      (user_id INTEGER, peer_id INTEGER, alarm_time TEXT)''')
    conn.commit()
    conn.close()

def add_alarm(user_id, peer_id, alarm_time):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    # Сначала удаляем старый будильник этого юзера в этом чате, если он был
    cursor.execute("DELETE FROM alarms WHERE user_id = ? AND peer_id = ?", (user_id, peer_id))
    # Записываем новый
    cursor.execute("INSERT INTO alarms VALUES (?, ?, ?)", (user_id, peer_id, alarm_time))
    conn.commit()
    conn.close()

def delete_alarm(user_id, peer_id):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alarms WHERE user_id = ? AND peer_id = ?", (user_id, peer_id))
    conn.commit()
    conn.close()

def get_all_alarms():
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, peer_id, alarm_time FROM alarms")
    rows = cursor.fetchall()
    conn.close()
    return rows