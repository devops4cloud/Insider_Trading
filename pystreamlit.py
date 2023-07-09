import streamlit as st
import pandas as pd
import numpy as np
#import hvplot.pandas
from pathlib import Path
import yfinance as yf
import pickle as pckl
from tensorflow import keras
import xgboost as xgb
from sklearn.metrics import classification_report

# Define a class for handling insider dataframes
class InsiderDataFrame:

    # Initialize the class with file path and dataframe arguments
    def __init__(self, file_path, dataframe=None) -> None:
        if file_path:
            self.source = Path(file_path)
        # Define a list of tickers to be used in the class
        self.tickers = ["MSFT", "GOOG", "AMZN","TSLA"]
        # Define the date range for the data to be used in the class
        self.fromdate = "2019-06-21"
        self.todate = "2023-06-30"
        self.df_tickers = None
        if dataframe is None:
            self.df = None
        else:
            self.df = dataframe
             # Clean the insider dataframe if a dataframe is provided during initialization
            self._clean_insider_dataframe()
            self.df.index = self.df.index.date

    # Method to set the insider dataframe using a CSV file from the provided file path
    def _set_insider_dataframe(self,date_column="Filing Date"):
        self.df = pd.read_csv(self.source,parse_dates=True,
                 infer_datetime_format=True,
                 index_col=date_column)
        self.df.index = self.df.index.date
        self._clean_insider_dataframe()
        #self.df.info()
    
     # Method to clean the insider dataframe by dropping unnecessary columns and converting data types of certain columns
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

     # Method to set the tickers data by retrieving historical data from Yahoo Finance for each ticker in the list of tickers defined in the class
    def _set_tickers(self):
        self.df_tickers = pd.DataFrame()
        for ticker in self.tickers:
            data = yf.Ticker(ticker).history(period='5y')
            close_prices = data['Close']
            # Add offset price column for each ticker by shifting the close price column by 7 days
            self.df_tickers[ticker+"_OffsetPrice"] = data['Close'].shift(7)
             # Add close price column for each ticker
            self.df_tickers[ticker] = close_prices
        # Set index name and convert index to date type
        self.df_tickers.index.name = 'Date'
        self.df_tickers.index = self.df_tickers.index.date
    
    # Method to get a processed dataframe for a specific ticker 
    # by merging insider data and tickers data and adding a trend column based 
    # on close and offset prices comparison 
    def get_processed_df(self,ticker):
        if self.df is None:
        # Set insider dataframe if it is not already set 
            self._set_insider_dataframe()
        if self.df_tickers is None:
        # Set tickers data if it is not already set 
            self._set_tickers()
        tmp_df_tickers = self.df_tickers
        # Select rows from an specific ticker
        tmp_df = self.df.where(self.df["Ticker"] == ticker)
        tmp_df = tmp_df.dropna(subset=["Ticker"])
        tmp_df = tmp_df.drop(columns=["Ticker"])

        # Add close price and offset price columns from tickers data to insider data for the specified ticker 
        tmp_df["ClosePrice"] = tmp_df_tickers[ticker]
        tmp_df["OffsetPrice"] = tmp_df_tickers[ticker+"_OffsetPrice"]
        # Add trend column based on comparison of close and offset prices (weekly)
        tmp_df.loc[tmp_df["ClosePrice"]>tmp_df["OffsetPrice"], "Trend"] = 0
        tmp_df.loc[tmp_df["ClosePrice"]<tmp_df["OffsetPrice"], "Trend"] = 1
        tmp_df = tmp_df.drop(columns=["OffsetPrice"])
        tmp_df = tmp_df.sort_index(ascending=True)
        return tmp_df

# Define a class for creating a Streamlit report app 
class ReportApp:
    def __init__(self):
        # Define a list of stocks and machine learning algorithms to be used in the app 
        self.stocks = ['MSFT', 'TSLA', 'GOOG', 'AMZN']
        self.ml_algorithms = ['Logistics Regression', 'LSTM', 'SVM', 'XGBoost']
         # Define the file path for the insider data CSV file 
        self.file_path = 'insider_data_v2.csv'
        # Create an instance of the InsiderDataFrame class using the provided file path 
        self.insider_dataframe = InsiderDataFrame(self.file_path)
        st.header('Insider Trader Trend Prediction')

     # Method to load data for a selected stock using the InsiderDataFrame instance 
    def load_data(self, stock):
        # Load data for the selected stock
        df= self.insider_dataframe.get_processed_df(stock)
        return df

    def run(self):
        st.sidebar.title('Stock Selection')
        stock = st.sidebar.selectbox('Select a stock:', self.stocks)

        # Add a title and dataframe display for the selected stock insider data 
        st.title(f'Insider Data for {stock}')
        df = self.load_data(stock)
        df = df.dropna()
        st.dataframe(df)

         # Add a title and selection box for machine learning algorithm selection in the sidebar 
        st.sidebar.title('Machine Learning Algorithm Selection')
        algorithm = st.sidebar.selectbox('Select an algorithm:', self.ml_algorithms)
        #st.write(f'Selected Algorithm: {algorithm}')
        model_loader = ModelProcessing()
        (model,scaler) = model_loader.load_ml_model(algorithm,stock)
        if hasattr(model, 'layers'):
            input_shape = model.layers[0].input_shape
            #fix for only selecting valid samples for LSTM, list only with divisible 
            # samples by the number of input_shape combined dimensions
            sample_number = st.sidebar.selectbox('Select a number of samples:', [ num for num in range(1,len(df)) if num % (input_shape[1] * input_shape[2])==0 ])
        else:
            sample_number = st.sidebar.slider("Select a number of samples: ",1,len(df))
        tmp_df = df.sample(sample_number)
        self._run_results(tmp_df,model,scaler)

    def _run_results(self,tmp_df,model,scaler):
        y = tmp_df["Trend"]
        X = tmp_df.drop(columns=["Trend"])
        if scaler is not None:
            X_scaled = scaler.fit_transform(X)
            predictions = model.predict(X_scaled)
        else:
            if hasattr(model, 'layers') and model.layers is not None and model.layers[0].input_shape is not None:
                input_shape = model.layers[0].input_shape
                #print(input_shape)
                #print(model.summary())
                X_reshaped=np.reshape(np.array(X), (-1,input_shape[1],input_shape[2]))
                #print(X_reshaped.shape)
                predictions = model.predict(X_reshaped)
                predictions = np.where(predictions >= 0.5, 1, 0)
                y = np.resize(y,(X_reshaped.shape[0]))
            else:
                predictions = model.predict(X)
        st.text("Sample selected")
        st.dataframe(X)
        st.text(classification_report(y,predictions))

class ModelProcessing:

    def __init__(self) -> None:
        pass

    def load_ml_model(self,ml_model,stock):
        
        (filename,extension)= self._get_file_name(ml_model,stock)
        scaler_model = self._get_scaler_model(ml_model,stock)

        if extension == "sav": # SVM and Logistics Regression - sklearn
            readmode = 'rb'
            with open(f"./models/{filename}.{extension}",readmode) as file:
                loaded_model = pckl.load(file)
                return (loaded_model, scaler_model)
        elif extension== "h5": # LSTM - Keras
            loaded_model = keras.models.load_model(f"./models/{filename}.{extension}")
            loaded_model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
            return (loaded_model, scaler_model)
        elif extension=="json":
            loaded_model =xgb.XGBClassifier() #https://github.com/dmlc/xgboost/issues/706
            booster = xgb.Booster()
            booster.load_model(f"./models/{filename}.{extension}")
            loaded_model._Booster = booster
            return (loaded_model, scaler_model)
    
    def _get_file_name(self,ml_model,stock):
        if ml_model == "Logistics Regression":
            return (f"{stock}_logistics_model","sav")
        elif ml_model == "LSTM":
            return (f"{stock}_LSTM_model","h5")
        elif ml_model == "SVM":
            return (f"{stock}_SVM_model","sav")
        elif ml_model == "XGBoost":
            return (f"{stock}_xgboost_model","json")
    
    def _get_scaler_model(self,ml_model,stock):
        if ml_model == "Logistics Regression":
            filename= (f"{stock}_logistics_model.scaler")
        elif ml_model == "SVM":
            filename =  (f"{stock}_SVM_model.scaler")
        else:
            return None
        
        with open(f"./models/{filename}","rb") as file:
            loaded_model = pckl.load(file)
        
        return loaded_model




