
import os
import logging
from pathlib import Path

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv


# ------------------------------------------------------------
# Load database credentials from .env
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)


# ------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ------------------------------------------------------------
# Database connection
# ------------------------------------------------------------

def connect_to_database():
    db_config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME")
    }

    required_values = {
        "DB_USER": db_config["user"],
        "DB_PASSWORD": db_config["password"],
        "DB_NAME": db_config["database"]
    }

    missing = [
        variable
        for variable, value in required_values.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing environment variables: "
            + ", ".join(missing)
        )

    try:
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            logging.info(
                "Connected successfully to database '%s' at %s:%s",
                db_config["database"],
                db_config["host"],
                db_config["port"]
            )

            return connection

    except Error as error:
        logging.error("Failed to connect to the database: %s", error)
        raise


# ------------------------------------------------------------
# Test the connection
# ------------------------------------------------------------

if __name__ == "__main__":
    connection = None

    try:
        connection = connect_to_database()

        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE(), VERSION();")

        database_name, mysql_version = cursor.fetchone()

        print(f"Database: {database_name}")
        print(f"MySQL version: {mysql_version}")

        cursor.close()

    except Exception as error:
        logging.error("Process failed: %s", error)

    finally:
        if connection and connection.is_connected():
            connection.close()
            logging.info("Database connection closed.")