
import pymysql
import tensorflow as tf
import numpy as np
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import datetime
import schedule
import time
import os

DB_CONFIG = {
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "maga"),
    "port": int(os.getenv("DB_PORT", 3306))
}

# Завантаження готової моделі
ts_model = tf.keras.models.load_model('model3.h5')

# Створення лічильника для масштабу
scaler = StandardScaler()


def get_database_connection():
    return pymysql.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            port=DB_CONFIG["port"],
        )


def fetch_recent_data(lookback):
    try:
        connection = get_database_connection()
        with connection.cursor() as cursor:
            query = f"SELECT count FROM request_metrics ORDER BY hour DESC LIMIT %s"
            cursor.execute(query, (lookback,))
            data = cursor.fetchall()
        connection.close()

        return np.array([row[0] for row in data][::-1])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch data from the database: {str(e)}")


def upsert_prediction_to_db(date_time, count):
    # Assuming you have a `predictions` table with columns `ds` (timestamp) and `count_of_instances`
    connection = get_database_connection()  # Use your DB connection here
    cursor = connection.cursor()

    query = """
    INSERT INTO predictions (hour, count_of_instances)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE count_of_instances = VALUES(count_of_instances)
    """

    cursor.execute(query, (date_time, count))
    connection.commit()
    cursor.close()
    connection.close()


def delete_historical_data(current_datetime):
    query = """
    DELETE FROM predictions
    WHERE hour < %s
    """
    connection = get_database_connection()
    cursor = connection.cursor()

    cursor.execute(query, (current_datetime,))

    connection.commit()
    cursor.close()
    connection.close()


def predict():
    try:
        # Parse input parameters
        lookback = 24 * 7
        predict_for = 24 * 7
        requests_per_instance = 100

        # Fetch data from the database
        recent_data = fetch_recent_data(lookback)

        # Scale the recent data
        recent_data_scaled = scaler.fit_transform(recent_data.reshape(-1, 1))

        # Initialize the input for predictions
        curr_input = recent_data_scaled.flatten()

        # Predict iteratively
        future_predictions = []
        for _ in range(predict_for):
            # Reshape the last `lookback` samples for the model
            this_input = curr_input[-lookback:].reshape((1, 1, lookback))
            # Predict the next value
            next_prediction = ts_model.predict(this_input)
            future_predictions.append(next_prediction.flatten()[0])
            # Update the current input with the new prediction
            curr_input = np.append(curr_input, next_prediction.flatten())

        # Inverse transform the predictions to the original scale
        future_predictions = np.array(future_predictions)
        future_predictions = scaler.inverse_transform(future_predictions.reshape(-1, 1))


        # Prepare data for plotting
        # Create a time axis for the historical data and predictions
        time_axis = np.arange(len(recent_data))
        # Create time axis for future predictions
        future_time_axis = np.arange(len(recent_data), len(recent_data) + predict_for)
        # Plot the historical data and future predictions
        plt.figure(figsize=(20, 10))
        plt.plot(time_axis, scaler.inverse_transform(recent_data_scaled.reshape(-1, 1)), label="Historical Data",
                 color='blue')
        plt.plot(future_time_axis, future_predictions, label="Future Predictions", color='green')
        # Add labels and title
        plt.title("Historical Data and Future Predictions", fontsize=20)
        plt.xlabel("Time (hours)", fontsize=14)
        plt.ylabel("Scaled Values", fontsize=14)
        plt.legend()
        # Display the plot
        plt.show()

        predicted_requests = future_predictions.flatten()
        instance_counts = np.ceil(predicted_requests / requests_per_instance).astype(int)

        # Delete all historical data (before the current time)
        delete_historical_data(datetime.datetime.now() - datetime.timedelta(hours=1))
        # Start from the next hour after the current time
        current_datetime = datetime.datetime.now() + datetime.timedelta(hours=1)
        # Save predictions to the database (date and instance counts)
        for i, count in enumerate(instance_counts):
            # Calculate the timestamp for each predicted hour
            prediction_datetime = current_datetime + datetime.timedelta(hours=i)
            prediction_hour = prediction_datetime.replace(minute=0, second=0, microsecond=0)

            # Save the prediction with timestamp
            upsert_prediction_to_db(prediction_hour, count)

        # Return predictions as JSON (optional)
        return future_predictions

    except Exception as e:
        return e

def schedule_task():
    # Schedule the task to run every hour at the 5th second
    #schedule.every().hour.at(":05").do(predict)
    # Testing
    schedule.every().minute.do(predict)

    while True:
        schedule.run_pending()  # Run all pending tasks
        time.sleep(1)  # Sleep for 1 second


# Run the scheduler
if __name__ == "__main__":
    schedule_task()
