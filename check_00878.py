
import yfinance as yf
import pandas as pd

try:
    print("Downloading 00878.TW...")
    df = yf.download("00878.TW", start="2020-07-01", progress=False)
    if not df.empty:
        print(f"Success! Rows: {len(df)}")
        print(df.head())
    else:
        print("Empty dataframe.")
except Exception as e:
    print(f"Error: {e}")
