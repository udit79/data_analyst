import numpy as np
import pandas as pd
class DataCleaning:
    def handle_missing_values(self,df,strategy='mean'):
        "Handling missing by filling it with mean,median,mode or droping."
        if strategy=="mean":
            df.fillna(df.mean(numeric_only=True),inplace=True)
        elif strategy=="median":
            df.fillna(df.median(numeric_only=True),inplac=True)
        elif strategy=="mode":
            df.fillna(df.mode.iloc[0],inplac=True)
        elif strategy=="drop":
            df.fillna(inplac=True)
    def remove_duplicates(self,df):
        "Remove duplicate rows"
        return df.drop_duplicates()
    def fix_data_types(self,df):
        "convert the columns into appropriate types."
        for col in df.columns:
            try:
                df[col]=pd.to_numeric(df[col])
            except ValueError:
                pass
        return df
    def clean_data(self,df):
        df=self.handle_missing_values(df)
        df=self.remove_duplicates(df)
        df=self.fix_data_types(df)
        return df