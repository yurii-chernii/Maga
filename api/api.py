from flask import Flask
import mysql.connector
from threading import Thread
import time
import os
from datetime import datetime

app = Flask(__name__)

# Конфігурація бази даних MariaDB
DB_CONFIG = {
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "maga"),
    "port": int(os.getenv("DB_PORT", 3306))
}

# Лічильник запитів
request_counter = 0

# Обробник HTTP-запитів
@app.route("/")
def handle_request():
    global request_counter
    request_counter += 1
    return "Request received", 200

def save_metrics_to_db():
    """Збереження кількості запитів у базу даних щогодини"""
    global request_counter

    while True:
        try:
            # Отримання поточного часу
            current_hour = datetime.now().strftime('%Y-%m-%d %H:00:00')

            # Підключення до бази даних MariaDB
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()

            # Перевірка, чи є вже дані для поточної години
            cursor.execute("""
                INSERT INTO request_metrics (hour, count)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE count = count + VALUES(count)
            """, (current_hour, request_counter))

            # Очищення лічильника
            request_counter = 0

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Error saving metrics: {e}")

        # Очікування до наступної години
        time.sleep(3)

if __name__ == "__main__":
    # Запуск бекграунд-потоку для збереження даних
    Thread(target=save_metrics_to_db, daemon=True).start()

    # Запуск HTTP-сервера
    app.run(host="0.0.0.0", port=5000)
