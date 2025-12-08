
import yfinance as yf
import pandas as pd

# Force auto_adjust=False to see both Close and Adj Close if possible, 
# or check default behavior.
print("--- Default Download ---")
df = yf.download("00878.TW", start="2023-01-01", end="2023-01-10", progress=False)
print(df.columns)
print(df.head())

print("\n--- auto_adjust=False ---")
df2 = yf.download("00878.TW", start="2023-01-01", end="2023-01-10", progress=False, auto_adjust=False)
print(df2.columns)
print(df2.head())
