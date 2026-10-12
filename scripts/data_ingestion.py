import os
import pandas as pd
import requests
from sqlalchemy import create_engine
DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../data")
class DataIngestion:
    def __init__(self,db_url=None):
        "Db connection"
        self.engine=create_engine(db_url) if db_url else None
    def load_csv(self,file_name):
        "loading csv in df"
        file_path=os.path.join(DATA_DIR,file_name)
        try:
            df=pd.read_csv(file_path)
            print(f"data loaded successfully:{file_path}")
            return df
        except Exception as e:
            print(f"Error while loading the csv:{e}")
            return None
    def connect_database(self,db_url):
        "Establishing Db connection"
        try:
            self.engine=create_engine(db_url)
            print("database connection successful.")
        except Exception as e:
            print(f"Error connecting the database:{e}")
    def load_from_database(self,query):
        "fetching data from database"
        if not self.engine:
            print("No database connection establish yet.Connect database first.")
            return None
        try:
            df=pd.read_sql(query,self.engine)
            print("Data Loaded Successfully.")
            return df
        except Exception as e:
            print(f"Error while loading the data from database:{e}")
    def fetch_from_api(self,api_url,params=None):
        "Fetches data from api and return it as DataFrame"
        try:
            response=requests.get(api_url,params=params)
            if response.status_code==200:
                data=response.json()
                df=pd.DataFrame(data)
                print("Data Fetched from api")
                return df
            else:
                print(f"Request failed:{response.status_code}")
                return None
        except Exception as e:
            print(f"Couldn't make a request something went wrong:{e}")
            return None
    