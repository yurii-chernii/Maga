import mysql.connector
from datetime import datetime, timedelta
import pandas as pd

# Database configuration
DB_CONFIG = {
    "user": "root",
    "password": "123456",
    "host": "localhost",
    "database": "maga",
    "port": 3306
}

# Path to your file
FILE_PATH = "requests_every_hour.csv"

# Starting timestamp (customize as needed)
START_TIMESTAMP = datetime(2024, 12, 1, 12, 0, 0)  # Example: 1st Dec 2024, 12:00 PM

# Load data from the CSV file
data = pd.read_csv(FILE_PATH, header=0)  # Ensure column "Requests" exists
values = data["Requests"].to_list()  # Convert the "Requests" column to a Python list

# Insert data into the database
try:
    # Connect to the database
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Insert each value with an auto-generated timestamp
    current_timestamp = START_TIMESTAMP
    for value in values:
        sql = """
        INSERT INTO request_metrics (hour, count)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE count = %s
        """
        # Convert value to native Python int before inserting
        cursor.execute(sql, (current_timestamp, int(value), int(value)))

        # Increment the timestamp by one hour
        current_timestamp += timedelta(hours=1)

    # Commit changes
    conn.commit()
    print("Data successfully saved to the database.")

except mysql.connector.Error as e:
    print(f"Error: {e}")

finally:
    # Close the connection
    if conn.is_connected():
        cursor.close()
        conn.close()
