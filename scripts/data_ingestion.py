import os

import pandas as pd
from requests.api import get
from sqlalchemy import create_engine

DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../data")
class DataIngestion:
    def __init__(self,db_url=None):
        "Db connection"
        self.engine=create_engine(db_url) if db_url else None
    def load_csv(self,file_name):
        """Load a CSV from the project's data directory."""
        file_path=os.path.join(DATA_DIR,file_name)
        return pd.read_csv(file_path)
    def connect_database(self,db_url):
        """Create and store a SQLAlchemy engine for the supplied database URL."""
        self.engine=create_engine(db_url)
        return self.engine
    def load_from_database(self,query):
        """Execute a SQL query and return its results as a DataFrame."""
        if self.engine is None:
            raise RuntimeError("Database engine is not configured")
        return pd.read_sql(query,self.engine)
    def fetch_from_api(self,api_url,params=None):
        """Fetch JSON from an API and return it as a DataFrame."""
        response = get(api_url, params=params, timeout=30)
        response.raise_for_status()
        return pd.DataFrame(response.json())
