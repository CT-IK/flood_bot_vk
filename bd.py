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