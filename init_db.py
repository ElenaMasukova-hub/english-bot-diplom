import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS common_words (
    id SERIAL PRIMARY KEY,
    russian VARCHAR(255),
    english VARCHAR(255)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS user_words (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    russian VARCHAR(255),
    english VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

common_words = [
    ("сервер", "server"), ("массив", "array"), ("клавиатура", "keyboard"),
    ("монитор", "monitor"), ("мышь", "mouse"), ("база данных", "database"),
    ("функция", "function"), ("переменная", "variable"), ("цикл", "loop"),
    ("условие", "condition")
]

for russian, english in common_words:
    cur.execute("INSERT INTO common_words (russian, english) VALUES (%s, %s) ON CONFLICT DO NOTHING", 
                (russian, english))

conn.commit()
cur.close()
conn.close()
print("БД создана и заполнена!")