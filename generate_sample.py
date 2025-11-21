import pandas as pd
import numpy as np

# Create dummy data
dates = pd.date_range(start='2023-01-01', periods=250)
# Random walk for TAIEX
np.random.seed(42)
taiex_returns = np.random.normal(0.0005, 0.01, 250)
taiex_price = 15000 * (1 + taiex_returns).cumprod()

# 00631L roughly 2x TAIEX
lev_returns = taiex_returns * 2
lev_price = 100 * (1 + lev_returns).cumprod()

data = {
    'Date': dates,
    '00631L': lev_price,
    'TAIEX': taiex_price
}
df_sample = pd.DataFrame(data)
df_sample.to_csv("sample_data.csv", index=False)
print("sample_data.csv created.")
