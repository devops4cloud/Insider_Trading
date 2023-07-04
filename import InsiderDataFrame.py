from pystreamlit import InsiderDataFrame


insider = InsiderDataFrame("./insider_data_v2.csv")
print(insider.get_processed_df("MSFT").head(13))
