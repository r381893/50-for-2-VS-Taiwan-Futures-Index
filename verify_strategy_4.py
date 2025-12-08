import pandas as pd
import numpy as np
from app import run_backtest_futures_simple

# Create dummy data
dates = pd.date_range(start='2023-01-01', periods=10)
df = pd.DataFrame({
    'TAIEX': [10000, 9900, 9800, 9700, 9600, 9500, 9400, 9300, 9200, 9100], # Downtrend
    '00631L': [100] * 10
}, index=dates)

# Run with ignore_short_yield=False (Default)
# Trend mode with MA=5. Price is decreasing, so it should be Short.
# Shorting pays dividend yield.
df_res_1, log_1 = run_backtest_futures_simple(
    df, 
    initial_capital=1000000, 
    leverage=1, 
    mode='Trend', 
    ma_period=20, # MA will be NaN initially, then calculated. 
                  # Actually, let's force signal to be Short.
    dividend_yield=0.04,
    ignore_short_yield=False
)

# Manually force signal to -1 for testing logic directly if needed, 
# but let's rely on the function's trend logic.
# With price dropping 100 points a day, MA (e.g. 5) will be higher than price.
# So Signal should be -1 (Short).

# Run with ignore_short_yield=True
df_res_2, log_2 = run_backtest_futures_simple(
    df, 
    initial_capital=1000000, 
    leverage=1, 
    mode='Trend', 
    ma_period=20, 
    dividend_yield=0.04,
    ignore_short_yield=True
)

print("Test 1 (Yield Cost Included):")
print(df_res_1['Total_Equity'].tail())
print("\nTest 2 (Yield Cost Ignored):")
print(df_res_2['Total_Equity'].tail())

final_eq_1 = df_res_1['Total_Equity'].iloc[-1]
final_eq_2 = df_res_2['Total_Equity'].iloc[-1]

print(f"\nDifference: {final_eq_2 - final_eq_1}")

if final_eq_2 > final_eq_1:
    print("SUCCESS: Ignoring short yield cost resulted in higher equity.")
else:
    print("FAILURE: Equity did not increase as expected.")
