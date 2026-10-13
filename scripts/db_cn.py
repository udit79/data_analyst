"""Host-side PostgreSQL configuration and connection check."""

import os

import psycopg2
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()

DB_Host = "localhost"
DB_Port = "5432"
DB_Name = "data_cleaning"
DB_User = "postgres"


def get_database_url() -> URL:
    """Build a SQLAlchemy URL from local settings without exposing the password."""
    password = os.getenv("DB_Password")
    if not password:
        raise RuntimeError("Set DB_Password in the host environment or .env file")
    return URL.create(
        "postgresql+psycopg2",
        username=DB_User,
        password=password,
        host=DB_Host,
        port=int(DB_Port),
        database=DB_Name,
    )


def main() -> None:
    """Check the configured PostgreSQL connection and list public table names."""
    try:
        with psycopg2.connect(
            dbname=DB_Name,
            user=DB_User,
            password=os.getenv("DB_Password"),
            host=DB_Host,
            port=DB_Port,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public';"
            )
            print("PostgreSQL connection successful")
            print("Public tables:")
            for (table_name,) in cursor.fetchall():
                print(table_name)
    except psycopg2.Error:
        print("PostgreSQL connection failed")
        raise


if __name__ == "__main__":
    main()
