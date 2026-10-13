import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_Host="localhost"
DB_Port="5432"
DB_Name="data_cleaning"
DB_User="postgres"
DB_Password=os.getenv("DB_Password")
try:
    connection= psycopg2.connect(
        dbname=DB_Name,
        user=DB_User,
        password=DB_Password,
        host=DB_Host,
        port=DB_Port
    )
    cursor=connection.cursor()
    print("Successfull connection")
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables=cursor.fetchall()
    print("Tables in Database are")
    for table in tables:
        print(table)
    cursor.close()
    connection.close()
    print("Test successful Db connection closed")
except psycopg2.Error:
    print("Something went worng.connection failed")
