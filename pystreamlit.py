import streamlit as st
import pandas as pd
import numpy as np
#import hvplot.pandas
from pathlib import Path
import yfinance as yf

class InsiderDataFrame:

    def __init__(self, file_path, dataframe=None) -> None:
        if file_path:
            self.source = Path(file_path)
        self.tickers = ["MSFT", "GOOG", "AMZN", "BIDU", "ADBE", "IBM", "MU", "NVDA", "PLTR", "AI", "TSLA"]
        self.fromdate = "2019-06-21"
        self.todate = "2023-06-30"
        self.df_tickers = None
        if dataframe is None:
            self.df = None
        else:
            self.df = dataframe
            self._clean_insider_dataframe()
            self.df.index = self.df.index.date

    def _set_insider_dataframe(self,date_column="Filing Date"):
        self.df = pd.read_csv(self.source,parse_dates=True,
                 infer_datetime_format=True,
                 index_col=date_column)
        self.df.index = self.df.index.date
        self._clean_insider_dataframe()
        #self.df.info()
    
    def _clean_insider_dataframe(self):
        self.df = self.df.drop(columns=["X", "Trade Date", "Insider Name", "Title","Trade Type"]) # do we need trade type?
        cols_to_convert = ['Price', 'Qty', 'Owned', 'ΔOwn', 'Value']
        row_to_del = self.df[cols_to_convert].apply(lambda x: x.astype(str).str.contains('#ERROR')).any(axis=1)
        self.df = self.df.loc[~row_to_del]
        for col in cols_to_convert:
            self.df[col] = self.df[col].astype(str).str.replace('%', '', regex=False)
            self.df[col] = self.df[col].astype(str).str.replace('$', '', regex=False)
            self.df[col] = self.df[col].astype(str).str.replace(',', '', regex=False)
            self.df[col] = pd.to_numeric(self.df[col])

    def _set_tickers(self):
        self.df_tickers = pd.DataFrame()
        for ticker in self.tickers:
            data = yf.Ticker(ticker).history(period='5y')
            close_prices = data['Close']
            self.df_tickers[ticker+"_OffsetPrice"] = data['Close'].shift(7)
            self.df_tickers[ticker] = close_prices
        self.df_tickers.index.name = 'Date'
        self.df_tickers.index = self.df_tickers.index.date
    
    def get_processed_df(self,ticker):
        if self.df is None:
            self._set_insider_dataframe()
        if self.df_tickers is None:
            self._set_tickers()
        tmp_df_tickers = self.df_tickers
        tmp_df = self.df.where(self.df["Ticker"] == ticker)
        tmp_df = tmp_df.dropna(subset=["Ticker"])
        tmp_df = tmp_df.drop(columns=["Ticker"])
        tmp_df["ClosePrice"] = tmp_df_tickers[ticker]
        tmp_df["OffsetPrice"] = tmp_df_tickers[ticker+"_OffsetPrice"]
        tmp_df.loc[tmp_df["ClosePrice"]>tmp_df["OffsetPrice"], "Trend"] = 0
        tmp_df.loc[tmp_df["ClosePrice"]<tmp_df["OffsetPrice"], "Trend"] = 1
        tmp_df = tmp_df.drop(columns=["OffsetPrice"])
        tmp_df = tmp_df.sort_index(ascending=True)
        return tmp_df

class ReportApp:
    def __init__(self):
        self.stocks = ['MSFT', 'TSLA', 'GOOG', 'AMZN']
        self.ml_algorithms = ['Linear Regression', 'Random Forest', 'SVM', 'KNN']
        self.file_path = 'insider_data_v2.csv'
        self.insider_dataframe = InsiderDataFrame(self.file_path)


    def load_data(self, stock):
        # Load data for the selected stock
        df= self.insider_dataframe.get_processed_df(stock)
        return df

    def run(self):
        st.sidebar.title('Stock Selection')
        stock = st.sidebar.selectbox('Select a stock:', self.stocks)

        st.title(f'Stock Data for {stock}')
        df = self.load_data(stock)
        st.dataframe(df)

        st.sidebar.title('Machine Learning Algorithm Selection')
        algorithm = st.sidebar.selectbox('Select an algorithm:', self.ml_algorithms)
        st.write(f'Selected Algorithm: {algorithm}')


class DataProcessing:

    def __init__(self) -> None:
        pass
    




"""
data = pd.read_csv(Path("./insider_data_v2.csv"),parse_dates=True,
                 infer_datetime_format=True,
                 index_col="Filing Date")
insider = InsiderDataFrame(None,data)
print(insider.get_processed_df("MSFT").head(13))
"""





