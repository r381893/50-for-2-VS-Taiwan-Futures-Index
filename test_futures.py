
import pandas as pd
import numpy as np
import yfinance as yf

# Mock Data
dates = pd.date_range(start='2020-01-01', periods=100)
prices = np.linspace(10000, 12000, 100) # Uptrend
# Add some volatility
prices += np.random.normal(0, 100, 100)
df = pd.DataFrame({'TAIEX': prices, '00631L': prices * 2}, index=dates)

def run_backtest_futures_simple(df_data, initial_capital, leverage, mode, ma_period, dividend_yield=0.04, cost_fee=40, cost_tax=2e-5, cost_slippage=1):
    df = df_data.copy()
    
    # Calculate Signal
    if mode == 'Trend':
        df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
        df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, -1)
        df['Signal'] = df['Signal'].shift(1).fillna(0)
    else:
        df['Signal'] = 1
        
    equity = initial_capital
    held_contracts = 0
    daily_yield_rate = dividend_yield / 252.0
    
    print(f"--- Mode: {mode} ---")
    
    for i in range(len(df)):
        price = df['TAIEX'].iloc[i]
        signal = df['Signal'].iloc[i]
        
        if i > 0:
            prev_price = df['TAIEX'].iloc[i-1]
            diff = price - prev_price
            
            price_pnl = held_contracts * diff * 50
            yield_points = prev_price * daily_yield_rate
            yield_pnl = held_contracts * yield_points * 50
            
            day_pnl = price_pnl + yield_pnl
            equity += day_pnl
            
            if i % 20 == 0: # Print some logs
                print(f"Day {i}: Price={price:.0f}, Signal={signal}, Contracts={held_contracts}, PnL={day_pnl:.0f} (Price={price_pnl:.0f}, Yield={yield_pnl:.0f}), Equity={equity:.0f}")

        if signal != 0:
            target_notional = equity * leverage * signal
            if price > 0:
                target_contracts = int(round(target_notional / (price * 50)))
            else:
                target_contracts = 0
        else:
            target_contracts = 0
            
        if target_contracts != held_contracts:
            held_contracts = target_contracts
            
    return equity

cap = 1000000
lev = 2.0
ma = 10

print("Running Long-Only...")
eq_long = run_backtest_futures_simple(df, cap, lev, 'Long-Only', ma)
print(f"Final Long-Only: {eq_long:.0f}")

print("\nRunning Trend...")
eq_trend = run_backtest_futures_simple(df, cap, lev, 'Trend', ma)
print(f"Final Trend: {eq_trend:.0f}")
