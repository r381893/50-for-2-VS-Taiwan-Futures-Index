
import yfinance as yf
import pandas as pd

try:
    print("Downloading 00631L.TW...")
    df = yf.download("00631L.TW", start="2024-01-01", progress=False)
    print("Shape:", df.shape)
    print("Columns:", df.columns)
    print("Head:\n", df.head())
    
    # Check if 'Close' is accessible directly or nested
    if not df.empty:
        df.reset_index(inplace=True)
        print("\nAfter reset_index:")
        print("Columns:", df.columns)
        try:
            print("Close sample:", df['Close'].head())
        except Exception as e:
            print("Error accessing 'Close':", e)

except Exception as e:
    print("Global Error:", e)
