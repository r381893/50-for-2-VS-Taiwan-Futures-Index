import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import yfinance as yf
import json

# =============================================================================
# 00878 股息資料 (季配息)
# =============================================================================
DIVIDEND_00878 = {
    '2020-11-17': 0.05,
    '2021-02-22': 0.15, '2021-05-18': 0.30, '2021-08-17': 0.35, '2021-11-16': 0.35,
    '2022-02-17': 0.32, '2022-05-17': 0.28, '2022-08-16': 0.28, '2022-11-16': 0.27,
    '2023-02-17': 0.35, '2023-05-17': 0.35, '2023-08-16': 0.35, '2023-11-16': 0.35,
    '2024-02-27': 0.40, '2024-05-17': 0.51, '2024-08-16': 0.55, '2024-11-18': 0.64,
    '2025-02-18': 0.56, '2025-05-16': 0.37, '2025-08-15': 0.37,
}

def get_dividend_00878(date_str):
    """取得指定日期的 00878 股息"""
    return DIVIDEND_00878.get(date_str, 0)

# =============================================================================
# 00631L 股息資料 (年配息，通常在除息後價格會調整)
# =============================================================================
# 注意：yfinance 使用 auto_adjust=True 時，價格已經包含股利調整
# 這個資料用於顯示歷史配息記錄，不用於回測計算（已反映在調整後價格）
DIVIDEND_00631L = {
    # 年度: 配息金額 (每股)
    '2016-10-24': 0.23,
    '2017-10-23': 0.88,
    '2018-10-22': 1.95,
    '2019-10-21': 0.05,
    '2020-10-19': 0.00,  # 2020 無配息
    '2021-10-18': 2.00,
    '2022-10-17': 3.30,
    '2023-10-16': 2.13,
    '2024-10-21': 3.75,
}

def get_dividend_00631L(date_str):
    """取得指定日期的 00631L 股息"""
    return DIVIDEND_00631L.get(date_str, 0)


st.set_page_config(page_title="台灣五十正2 & 小台 Backtest", layout="wide")
st.title("台灣五十正2 (00631L) & 小台指 策略回測平台")

# --- CSS Styling (Original) ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Inter', 'Microsoft JhengHei', sans-serif; }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
        margin-bottom: 10px;
    }
    .dark-theme .metric-card { background-color: #262730; border: 1px solid #464b59; }
    .metric-label { font-size: 0.9rem; color: #666; margin-bottom: 5px; }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #333; }
    .metric-delta { font-size: 0.9rem; margin-top: 5px; }
    .delta-pos { color: #d32f2f; }
    .delta-neg { color: #388e3c; }
    .delta-neutral { color: #888888; font-size: 0.8rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; padding: 10px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b; color: white; }
</style>
""", unsafe_allow_html=True)

def metric_card(label, value, delta=None, delta_color="normal"):
    delta_html = ""
    if delta:
        if delta_color == "inverse":
            try:
                val = float(str(delta).replace(',','').replace('%','').split()[0]) # Try simple parse
                color_class = "delta-neg" if "-" not in str(delta) and val > 0 else "delta-pos"
            except:
                color_class = "delta-neutral"
        else:
            try:
                val = float(str(delta).replace(',','').replace('%','').split()[0])
                is_positive = "-" not in str(delta) and val != 0
                color_class = "delta-pos" if is_positive else "delta-neg"
            except:
                color_class = "delta-neutral" # Fallback for text-only deltas
        delta_html = f'<div class="metric-delta {color_class}">{delta}</div>'
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{delta_html}</div>', unsafe_allow_html=True)

# --- 1. Original Backtest Function (Unchanged Logic) ---
def run_backtest_original(df_data, ma_period, initial_capital, long_allocation_pct, short_allocation_pct, 
                          margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
                          cost_fee, cost_tax, cost_slippage, include_costs):
    df = df_data.copy()
    df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
    df['Position'] = (df['TAIEX'] < df['MA']).shift(1).fillna(0)
    
    long_capital = initial_capital * long_allocation_pct
    short_capital = initial_capital * short_allocation_pct
    
    long_equity_arr, short_equity_arr, total_equity_arr = [], [], []
    trades = []
    
    total_long_pnl = 0
    total_short_pnl = 0
    total_cost = 0
    
    current_short_capital = short_capital # Use this to track short cap
    
    initial_price_00631L = df['00631L'].iloc[0]
    shares_00631L = long_capital / initial_price_00631L
    
    in_trade = False
    entry_date, entry_price, entry_capital, entry_long_equity = None, 0, 0, 0
    last_month = df.index[0].month
    
    for i in range(len(df)):
        date = df.index[i]
        price_00631L = df['00631L'].iloc[i]
        price_taiex = df['TAIEX'].iloc[i]
        position = df['Position'].iloc[i]
        
        long_equity = shares_00631L * price_00631L
        
        if i > 0:
            prev_price = df['00631L'].iloc[i-1]
            total_long_pnl += shares_00631L * (price_00631L - prev_price)
            
            prev_taiex = df['TAIEX'].iloc[i-1]
            if position == 1:
                # Contracts
                safe_margin = 3.0
                max_contracts = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
                if hedge_mode == "完全避險 (Neutral Hedge)":
                    tg_notional = long_equity * 2
                    tg_contracts = int(round(tg_notional / (prev_taiex * 50)))
                    actual_contracts = min(tg_contracts, max_contracts)
                else:
                    actual_contracts = max_contracts
                    
                diff = price_taiex - prev_taiex
                short_pnl = actual_contracts * diff * 50 * (-1)
                current_short_capital += short_pnl
                total_short_pnl += short_pnl
        
        # Costs & Trades
        prev_pos = df['Position'].iloc[i-1] if i > 0 else 0
        if position != prev_pos:
            safe_margin = 3.0
            max_c = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
            if hedge_mode == "完全避險 (Neutral Hedge)":
                tg_c = int(round((long_equity * 2) / (price_taiex * 50)))
                act_c = min(tg_c, max_c)
            else:
                act_c = max_c
                
            contracts = act_c
            if contracts > 0 and include_costs:
                fee = contracts * cost_fee
                tax = price_taiex * 50 * contracts * cost_tax
                slip = contracts * cost_slippage * 50
                tc = fee + tax + slip
                current_short_capital -= tc
                total_cost += tc
            
            if position == 1 and not in_trade:
                in_trade = True
                entry_date = date
                entry_price = price_taiex
                entry_capital = current_short_capital
                entry_long_equity = long_equity
            elif position == 0 and in_trade:
                in_trade = False
                exit_price = price_taiex
                pts = entry_price - exit_price
                
                # Re-calc entries logic for record
                max_ce = int(entry_capital / (3.0 * margin_per_contract)) if margin_per_contract > 0 else 0
                if hedge_mode == "完全避險 (Neutral Hedge)":
                    tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
                    act_ce = min(tg_ce, max_ce)
                else:
                    act_ce = max_ce
                
                prof_twd = pts * 50 * act_ce
                entry_notional = act_ce * entry_price * 50
                eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
                ret = (entry_price - exit_price) / entry_price
                
                trades.append({
                    '進場日期': entry_date, '進場指數': entry_price,
                    '出場日期': date, '出場指數': exit_price,
                    '避險口數': act_ce, '獲利點數': pts,
                    '獲利金額 (TWD)': prof_twd, '報酬率': ret * eff_lev
                })

        short_equity = current_short_capital
        total_equity = long_equity + short_equity
        
        # Rebalance
        curr_month = date.month
        if do_rebalance and i > 0 and curr_month != last_month:
            t_long = total_equity * rebalance_long_target
            t_short = total_equity * (1 - rebalance_long_target)
            shares_00631L = t_long / price_00631L
            current_short_capital = t_short
            long_equity = t_long
            short_equity = t_short
            
        last_month = curr_month
        
        long_equity_arr.append(long_equity)
        short_equity_arr.append(short_equity)
        total_equity_arr.append(total_equity)
        
    # Open Trade
    if in_trade:
        now_price = df['TAIEX'].iloc[-1]
        pts = entry_price - now_price
        
        max_ce = int(entry_capital / (3.0 * margin_per_contract)) if margin_per_contract > 0 else 0
        if hedge_mode == "完全避險 (Neutral Hedge)":
            tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
            act_ce = min(tg_ce, max_ce)
        else:
            act_ce = max_ce
        
        prof_twd = pts * 50 * act_ce
        entry_notional = act_ce * entry_price * 50
        eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
        ret = (entry_price - now_price) / entry_price
        
        trades.append({
            '進場日期': entry_date, '進場指數': entry_price,
            '出場日期': df.index[-1], '出場指數': now_price,
            '避險口數': act_ce, '獲利點數': pts,
            '獲利金額 (TWD)': prof_twd, '報酬率': ret * eff_lev, '備註': '持倉中'
        })
        
    df['Long_Equity'] = long_equity_arr
    df['Short_Equity'] = short_equity_arr
    df['Total_Equity'] = total_equity_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, trades, total_long_pnl, total_short_pnl, total_cost

# --- 2. New Rebalance Strategy ---
def run_backtest_rebalance(df_data, initial_capital, target_00631_pct):
    df = df_data.copy()
    cash = initial_capital * (1 - target_00631_pct)
    alloc_00631 = initial_capital * target_00631_pct
    shares = alloc_00631 / df['00631L'].iloc[0]
    
    # Simple cost model for rebalance
    cost_rate = 0.001425 * 0.6 + 0.001
    total_cost_accum = 0  # Track transaction costs properly
    
    # Initial purchase cost
    init_cost = alloc_00631 * cost_rate
    cash -= init_cost
    total_cost_accum += init_cost
    
    eq_arr, cash_arr = [], []
    log = []
    last_month = df.index[0].month
    
    # Initial Log
    log.append({
        '日期': df.index[0].strftime('%Y-%m-%d'),
        '動作': '建倉',
        '成交價': f"{df['00631L'].iloc[0]:.2f}",
        '股數變動': int(shares),
        '持有股數': int(shares),
        '現金餘額': int(cash),
        '總資產': int(initial_capital),
        '交易成本': int(init_cost)
    })
    
    for i in range(len(df)):
        price = df['00631L'].iloc[i]
        val = shares * price
        tot = val + cash
        
        curr_month = df.index[i].month
        if i > 0 and curr_month != last_month:
            tgt_val = tot * target_00631_pct
            diff = tgt_val - val
            if abs(diff) > 1000:
                cost = abs(diff) * cost_rate
                shares_diff = diff / price
                shares += shares_diff
                cash -= (diff + cost)
                total_cost_accum += cost
                
                log.append({
                    '日期': df.index[i].strftime('%Y-%m-%d'),
                    '動作': '再平衡',
                    '成交價': f"{price:.2f}",
                    '股數變動': int(shares_diff),
                    '持有股數': int(shares),
                    '現金餘額': int(cash),
                    '總資產': int(tot),
                    '交易成本': int(cost)
                })
        
        last_month = curr_month
        eq_arr.append(shares * price + cash)
        cash_arr.append(cash)
        
    df['Total_Equity'] = eq_arr
    df['Cash'] = cash_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, pd.DataFrame(log), total_cost_accum

# --- 3. Simple Futures Strategy (Long Only / Trend) ---
def run_backtest_futures_simple(df_data, initial_capital, leverage, mode, ma_period, dividend_yield=0.04, cost_fee=40, cost_tax=2e-5, cost_slippage=1, ignore_short_yield=False):
    df = df_data.copy()
    
    # Calculate Signal
    if mode == 'Trend':
        # Trend: Price > MA -> Long (1), Price < MA -> Short (-1)
        df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
        # Signal is based on Yesterday's Close vs MA to trade Today
        # 1 = Long, -1 = Short
        df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, -1)
        df['Signal'] = df['Signal'].shift(1).fillna(0) # shift to apply to next day
    elif mode == 'Long-MA':
        # Long-MA: Price > MA -> Long (1), Price < MA -> Cash (0)
        df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
        df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, 0)
        df['Signal'] = df['Signal'].shift(1).fillna(0)
    else:
        # Long Only
        df['Signal'] = 1
        
    equity = initial_capital
    held_contracts = 0
    cash = initial_capital # Track cash for PnL calculation
    
    equity_arr = []
    cash_arr = []
    log = []
    total_cost_accum = 0
    
    # Margin per contract (小台)
    margin_per_contract = 85000
    is_liquidated = False
    liquidation_date = None
    
    # Daily Yield Rate (approx)
    daily_yield_rate = dividend_yield / 252.0
    
    avg_entry = 0
    
    for i in range(len(df)):
        price = df['TAIEX'].iloc[i]
        date = df.index[i]
        signal = df['Signal'].iloc[i]
        
        # 1. Calculate PnL from previous day's holding
        if i > 0:
            prev_price = df['TAIEX'].iloc[i-1]
            
            # Price PnL
            price_pnl = (price - prev_price) * held_contracts * 50
            
            # Yield PnL
            if held_contracts < 0 and ignore_short_yield:
                yield_pnl = 0
            else:
                yield_points = prev_price * daily_yield_rate
                yield_pnl = held_contracts * yield_points * 50
            
            total_pnl = price_pnl + yield_pnl
            cash += total_pnl
            
            # Check for liquidation (margin call)
            required_margin = abs(held_contracts) * margin_per_contract
            if held_contracts != 0 and cash < required_margin * 0.25:  # Below 25% maintenance margin
                # Liquidation!
                is_liquidated = True
                liquidation_date = date
                
                # Force close all positions
                close_cost = abs(held_contracts) * (cost_fee + cost_tax * price * 50 + cost_slippage * 50)
                cash -= close_cost
                total_cost_accum += close_cost
                
                log.append({
                    '日期': date.strftime('%Y-%m-%d'),
                    '動作': '💥 爆倉 (強制平倉)',
                    '指數': int(price),
                    '目標口數': 0,
                    '變動口數': -held_contracts,
                    '成交均價': int(price),
                    '持有成本': int(avg_entry),
                    '交易成本': int(close_cost),
                    '本筆損益': 0,
                    '帳戶權益': int(cash)
                })
                
                held_contracts = 0
                avg_entry = 0
            
        # 2. Adjust Position (Rebalance or Signal Change)
        target_contracts = 0
        
        if mode == 'Long-Only':
            target_notional = cash * leverage
            target_contracts = int(round(target_notional / (price * 50)))
        elif mode == 'Trend' or mode == 'Long-MA':
            if signal == 1: # Long
                target_notional = cash * leverage
                target_contracts = int(round(target_notional / (price * 50)))
            elif signal == -1: # Short
                target_notional = cash * leverage
                target_contracts = -int(round(target_notional / (price * 50)))
            else: # Cash
                target_contracts = 0
                
        # Execute Trade
        if target_contracts != held_contracts:
            diff = target_contracts - held_contracts
            
            # Calculate Transaction Cost
            cost = abs(diff) * (cost_fee + cost_tax * price * 50 + cost_slippage * 50)
            cash -= cost
            total_cost_accum += cost
            
            # Calculate Realized PnL (for log only)
            realized_pnl = 0
            
            # Closing/Reducing
            if held_contracts != 0:
                if held_contracts * target_contracts < 0: # Reversal
                    closed_qty = abs(held_contracts)
                elif target_contracts == 0: # Full Close
                    closed_qty = abs(held_contracts)
                elif abs(target_contracts) < abs(held_contracts) and (held_contracts * target_contracts > 0): # Partial Reduce
                    closed_qty = abs(diff)
                else:
                    closed_qty = 0
                
                if closed_qty > 0:
                    direction = 1 if held_contracts > 0 else -1
                    realized_pnl = (price - avg_entry) * closed_qty * 50 * direction
            
            # Update Avg Entry for New/Increased Position
            if target_contracts != 0:
                if held_contracts == 0 or (held_contracts * target_contracts < 0):
                    # Fresh or Reversal
                    avg_entry = price
                elif abs(target_contracts) > abs(held_contracts):
                    # Increasing
                    old_vol = abs(held_contracts)
                    added_vol = abs(diff)
                    avg_entry = (old_vol * avg_entry + added_vol * price) / (old_vol + added_vol)
            
            # Update Position
            prev_contracts = held_contracts
            held_contracts = target_contracts
            
            # Determine Action Label
            if prev_contracts == 0:
                action = '新倉 (多)' if target_contracts > 0 else '新倉 (空)'
            elif target_contracts == 0:
                action = '平倉'
            elif prev_contracts * target_contracts < 0:
                action = '反手 (多)' if target_contracts > 0 else '反手 (空)'
            elif abs(target_contracts) > abs(prev_contracts):
                action = '加碼 (多)' if target_contracts > 0 else '加碼 (空)'
            else:
                action = '減碼 (多)' if target_contracts > 0 else '減碼 (空)'
            
            log.append({
                '日期': date.strftime('%Y-%m-%d'),
                '動作': action,
                '指數': int(price),
                '目標口數': int(target_contracts),
                '變動口數': int(diff),
                '成交均價': int(price),
                '持有成本': int(avg_entry),
                '交易成本': int(cost),
                '本筆損益': int(realized_pnl) if realized_pnl != 0 else 0,
                '帳戶權益': int(cash)
            })
            
        cash_arr.append(cash)
        
    df['Total_Equity'] = cash_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, pd.DataFrame(log), total_cost_accum, is_liquidated

# --- 4. Futures + 00878 Strategy ---
def run_backtest_futures_00878(df_data, initial_capital, leverage, margin_per_contract, target_risk_ratio=3.0, dividend_yield=0.04):
    df = df_data.copy()
    
    # Fill 00878 NaN with 0 (or handle in loop)
    # Actually, if 00878 is NaN, we just hold Cash.
    
    cash = initial_capital
    shares_00878 = 0
    held_contracts = 0
    
    equity_arr = []
    cash_arr = []
    held_00878_val_arr = []
    rebalance_log = []
    total_cost_accum = 0
    
    # Track cumulative PnL by component
    total_futures_pnl = 0
    total_00878_pnl = 0
    total_dividend_received = 0
    
    last_month = df.index[0].month
    daily_yield_rate = dividend_yield / 252.0
    
    # Cost parameters (approx)
    cost_fee = 40
    cost_tax = 2e-5
    cost_slippage = 1
    
    for i in range(len(df)):
        date = df.index[i]
        price_taiex = df['TAIEX'].iloc[i]
        price_00878 = df['00878'].iloc[i]
        
        # 1. Update Equity from Price Changes
        if i > 0:
            prev_taiex = df['TAIEX'].iloc[i-1]
            prev_00878 = df['00878'].iloc[i-1]
            
            # Futures PnL (Price Difference)
            diff_pts = price_taiex - prev_taiex
            price_pnl = held_contracts * diff_pts * 50
            
            # Futures Yield PnL (Backwardation/Dividend)
            # Same logic as Strategy 3
            yield_points = prev_taiex * daily_yield_rate
            yield_pnl = held_contracts * yield_points * 50
            
            fut_pnl = price_pnl + yield_pnl
            
            # 00878 PnL (Price Change)
            if shares_00878 > 0 and not pd.isna(price_00878) and not pd.isna(prev_00878):
                stock_pnl = shares_00878 * (price_00878 - prev_00878)
            else:
                stock_pnl = 0
            
            # 00878 Dividend Income (check if today is ex-dividend date)
            date_str = date.strftime('%Y-%m-%d')
            if shares_00878 > 0 and date_str in DIVIDEND_00878:
                dividend_per_share = DIVIDEND_00878[date_str]
                dividend_income = shares_00878 * dividend_per_share
                cash += dividend_income  # Dividend goes to cash
                total_dividend_received += dividend_income
            else:
                dividend_income = 0
            
            # Accumulate component PnL
            total_futures_pnl += fut_pnl
            total_00878_pnl += stock_pnl
                
            cash += fut_pnl # Futures PnL settles to cash
            # Stock PnL is unrealized until rebalance, but for Total Equity we add it.
            
        # Recalculate Equity based on components to be precise
        current_00878_val = shares_00878 * price_00878 if (shares_00878 > 0 and not pd.isna(price_00878)) else 0
        # Note: 'cash' here includes the futures margin deposit.
        # So Total Equity = Cash + Stock Value.
        total_equity = cash + current_00878_val
        
        # 2. Rebalance (Monthly)
        curr_month = date.month
        if i == 0 or (i > 0 and curr_month != last_month):
            # Target Exposure
            target_notional = total_equity * leverage
            
            if price_taiex > 0:
                target_contracts = int(round(target_notional / (price_taiex * 50)))
            else:
                target_contracts = 0
            
            # Calculate Cash needed for Futures (Risk Management)
            # Required Margin = Contracts * Margin
            # Target Cash in Futures Account = Required Margin * Risk Ratio
            req_margin = target_contracts * margin_per_contract
            target_futures_cash = req_margin * target_risk_ratio
            
            # Remaining for 00878
            if total_equity < req_margin:
                # Not enough money even for 1x margin
                target_contracts = int(total_equity / margin_per_contract)
                target_futures_cash = total_equity
                target_00878_val = 0
                note = "資金不足(降槓桿)"
            else:
                # We have enough for margin.
                if total_equity < target_futures_cash:
                    # Not enough for 300% risk, but enough for margin.
                    # Put all in cash to be safe(r).
                    target_futures_cash = total_equity
                    target_00878_val = 0
                    note = "風險指標不足(全現金)"
                else:
                    # We have excess.
                    target_00878_val = total_equity - target_futures_cash
                    note = "正常平衡"
            
            # Execute Rebalance
            prev_contracts = held_contracts
            held_contracts = target_contracts
            
            # Futures Cost
            diff_contracts = held_contracts - prev_contracts
            if diff_contracts != 0:
                f_cost = abs(diff_contracts) * (cost_fee + cost_tax * price_taiex * 50 + cost_slippage * 50)
                cash -= f_cost
                total_cost_accum += f_cost
            
            # 00878
            prev_shares = shares_00878
            if target_00878_val > 0 and not pd.isna(price_00878):
                shares_00878 = target_00878_val / price_00878
                cash = target_futures_cash # The rest is in stock
            else:
                shares_00878 = 0
                cash = total_equity # All cash
            
            # 00878 Cost (Simple 0.1425% * 0.6 + 0.3% Tax for Sell)
            diff_shares = shares_00878 - prev_shares
            if diff_shares != 0 and not pd.isna(price_00878):
                val_trade = abs(diff_shares) * price_00878
                fee = val_trade * 0.001425 * 0.6
                tax = val_trade * 0.003 if diff_shares < 0 else 0
                s_cost = fee + tax
                cash -= s_cost
                total_cost_accum += s_cost
                
            # Log
            rebalance_log.append({
                '日期': date.strftime('%Y-%m-%d'),
                '總資產': int(total_equity),
                '加權指數': int(price_taiex),
                '目標曝險': int(target_notional),
                '期貨口數': int(held_contracts),
                '期貨變動': int(held_contracts - prev_contracts),
                '保留現金(期貨)': int(cash),
                '00878股價': f"{price_00878:.2f}" if not pd.isna(price_00878) else "N/A",
                '00878股數': int(shares_00878),
                '00878變動': int(shares_00878 - prev_shares),
                '備註': note
            })
        
        last_month = curr_month
        
        equity_arr.append(total_equity)
        cash_arr.append(cash)
        held_00878_val_arr.append(shares_00878 * price_00878 if not pd.isna(price_00878) else 0)
        
    df['Total_Equity'] = equity_arr
    df['Cash_Pos'] = cash_arr
    df['Stock_Pos'] = held_00878_val_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    pnl_breakdown = {
        '期貨損益': total_futures_pnl,
        '00878損益': total_00878_pnl,
        '股利收入': total_dividend_received
    }
    
    return df, pd.DataFrame(rebalance_log), total_cost_accum, pnl_breakdown


# --- 5b. Futures + 00878 Strategy (Long-MA Version) ---
def run_backtest_futures_00878_ma(df_data, initial_capital, leverage, margin_per_contract, target_risk_ratio=3.0, dividend_yield=0.04, ma_period=13):
    """
    期貨 + 00878 策略 (均線做多版)
    
    與策略 5 相同的基礎邏輯：
    - 目標曝險 = 總資產 × 槓桿
    - 保留現金 = 保證金 × 風險指標 (預設 300%)
    - 剩餘資金 → 買 00878
    - 每月調倉
    
    差異：
    - 均線以上：持有期貨 (跟策略 5 一樣)
    - 均線以下：期貨平倉，現金保留不動
    """
    df = df_data.copy()
    
    # Calculate MA Signal
    df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
    df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, 0)
    df['Signal'] = df['Signal'].shift(1).fillna(0)  # Apply signal next day
    
    cash = initial_capital
    shares_00878 = 0
    held_contracts = 0
    
    equity_arr = []
    cash_arr = []
    held_00878_val_arr = []
    rebalance_log = []
    total_cost_accum = 0
    is_liquidated = False
    
    # Track cumulative PnL by component
    total_futures_pnl = 0
    total_00878_pnl = 0
    total_dividend_received = 0
    
    last_month = df.index[0].month
    last_signal = 0
    daily_yield_rate = dividend_yield / 252.0
    
    # Cost parameters
    cost_fee = 40
    cost_tax = 2e-5
    cost_slippage = 1
    
    for i in range(len(df)):
        date = df.index[i]
        price_taiex = df['TAIEX'].iloc[i]
        price_00878 = df['00878'].iloc[i]
        signal = df['Signal'].iloc[i]
        
        # 1. Update Equity from Price Changes
        if i > 0:
            prev_taiex = df['TAIEX'].iloc[i-1]
            prev_00878 = df['00878'].iloc[i-1]
            
            # Futures PnL
            diff_pts = price_taiex - prev_taiex
            price_pnl = held_contracts * diff_pts * 50
            
            # Futures Yield PnL (逆價差)
            yield_points = prev_taiex * daily_yield_rate
            yield_pnl = held_contracts * yield_points * 50
            
            fut_pnl = price_pnl + yield_pnl
            
            # 00878 PnL
            if shares_00878 > 0 and not pd.isna(price_00878) and not pd.isna(prev_00878):
                stock_pnl = shares_00878 * (price_00878 - prev_00878)
            else:
                stock_pnl = 0
            
            # 00878 Dividend Income
            date_str = date.strftime('%Y-%m-%d')
            if shares_00878 > 0 and date_str in DIVIDEND_00878:
                dividend_per_share = DIVIDEND_00878[date_str]
                dividend_income = shares_00878 * dividend_per_share
                cash += dividend_income  # 股利進現金
                total_dividend_received += dividend_income
            
            # Accumulate component PnL
            total_futures_pnl += fut_pnl
            total_00878_pnl += stock_pnl
            
            cash += fut_pnl  # Futures PnL settles to cash
            
            # Check for liquidation
            required_margin = abs(held_contracts) * margin_per_contract
            if held_contracts != 0 and cash < required_margin * 0.25:
                is_liquidated = True
                close_cost = abs(held_contracts) * (cost_fee + cost_tax * price_taiex * 50 + cost_slippage * 50)
                cash -= close_cost
                total_cost_accum += close_cost
                
                rebalance_log.append({
                    '日期': date.strftime('%Y-%m-%d'),
                    '動作': '💥 爆倉',
                    '總資產': int(cash + (shares_00878 * price_00878 if not pd.isna(price_00878) else 0)),
                    '加權指數': int(price_taiex),
                    'MA': int(df['MA'].iloc[i]) if not pd.isna(df['MA'].iloc[i]) else 0,
                    '期貨口數': 0,
                    '現金': int(cash),
                    '00878股數': int(shares_00878),
                    '備註': '保證金不足'
                })
                
                held_contracts = 0
        
        # Recalculate Total Equity
        current_00878_val = shares_00878 * price_00878 if (shares_00878 > 0 and not pd.isna(price_00878)) else 0
        total_equity = cash + current_00878_val
        
        # 2. Rebalance: Monthly OR Signal Change
        curr_month = date.month
        signal_changed = (signal != last_signal)
        monthly_rebal = (i == 0 or (i > 0 and curr_month != last_month))
        
        if signal_changed or monthly_rebal:
            prev_contracts = held_contracts
            prev_shares = shares_00878
            note = ""
            
            # 1. Calculate Theoretical Target Structure (Same as Strategy 5)
            target_notional = total_equity * leverage
            
            if price_taiex > 0:
                theoretical_contracts = int(round(target_notional / (price_taiex * 50)))
            else:
                theoretical_contracts = 0
            
            # Calculate Cash needed for Futures (Risk Management)
            req_margin = theoretical_contracts * margin_per_contract
            target_futures_cash = req_margin * target_risk_ratio
            
            # Remaining for 00878
            if total_equity < req_margin:
                theoretical_contracts = int(total_equity / margin_per_contract)
                target_futures_cash = total_equity
                target_00878_val = 0
                note_alloc = "資金不足"
            elif total_equity < target_futures_cash:
                target_futures_cash = total_equity
                target_00878_val = 0
                note_alloc = "風險不足"
            else:
                target_00878_val = total_equity - target_futures_cash
                note_alloc = "正常"
            
            # 2. Apply Signal
            if signal == 1:
                # Long: Hold the theoretical contracts
                target_contracts = theoretical_contracts
                # 00878 = 總資產 - 期貨所需現金
                final_00878_val = target_00878_val
                note = f"做多 ({note_alloc})"
            else:
                # Flat: Hold 0 contracts, but KEEP holding 00878
                target_contracts = 0
                # 重點：空手時不需要保留期貨保證金，所有資金都可以買 00878
                final_00878_val = total_equity * 0.95  # 保留 5% 現金緩衝
                note = f"空手 (持續持有878)"
            
            # 3. Execute Futures Rebalance
            held_contracts = target_contracts
            
            diff_contracts = held_contracts - prev_contracts
            if diff_contracts != 0:
                f_cost = abs(diff_contracts) * (cost_fee + cost_tax * price_taiex * 50 + cost_slippage * 50)
                cash -= f_cost
                total_cost_accum += f_cost
            
            # 4. Execute 00878 Rebalance (Only if Monthly or i=0)
            if monthly_rebal:
                if final_00878_val > 0 and not pd.isna(price_00878):
                    # Calculate equity available for rebalancing (after futures cost)
                    current_equity_after_futures = cash + (prev_shares * price_00878 if not pd.isna(price_00878) else 0)
                    
                    shares_00878 = final_00878_val / price_00878
                    cash = current_equity_after_futures - (shares_00878 * price_00878)
                else:
                    # 維持現有持股
                    pass
                
                # 00878 Cost
                diff_shares = shares_00878 - prev_shares
                if diff_shares != 0 and not pd.isna(price_00878):
                    val_trade = abs(diff_shares) * price_00878
                    fee = val_trade * 0.001425 * 0.6
                    tax = val_trade * 0.003 if diff_shares < 0 else 0
                    s_cost = fee + tax
                    cash -= s_cost
                    total_cost_accum += s_cost
            
            # Update values for logging
            current_00878_val = shares_00878 * price_00878 if (shares_00878 > 0 and not pd.isna(price_00878)) else 0
            
            # Log
            rebalance_log.append({
                '日期': date.strftime('%Y-%m-%d'),
                '動作': '做多' if signal == 1 else '空手',
                '總資產': int(cash + current_00878_val),
                '加權指數': int(price_taiex),
                'MA': int(df['MA'].iloc[i]) if not pd.isna(df['MA'].iloc[i]) else 0,
                '目標曝險': int(target_notional),
                '期貨口數': int(held_contracts),
                '期貨變動': int(held_contracts - prev_contracts),
                '現金': int(cash),
                '00878股數': int(shares_00878),
                '00878變動': int(shares_00878 - prev_shares),
                '備註': note
            })
        
        last_month = curr_month
        last_signal = signal
        
        equity_arr.append(total_equity)
        cash_arr.append(cash)
        held_00878_val_arr.append(shares_00878 * price_00878 if not pd.isna(price_00878) else 0)
        
    df['Total_Equity'] = equity_arr
    df['Cash_Pos'] = cash_arr
    df['Stock_Pos'] = held_00878_val_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    pnl_breakdown = {
        '期貨損益': total_futures_pnl,
        '00878損益': total_00878_pnl,
        '股利收入': total_dividend_received
    }
    
    return df, pd.DataFrame(rebalance_log), total_cost_accum, is_liquidated, pnl_breakdown


# --- 6. Pure 00878 Buy & Hold (with Dividend) ---
def run_backtest_00878_only(df_data, initial_capital, reinvest_dividend=True):
    """
    00878 純持有策略 (含股利計算)
    
    Args:
        df_data: 包含 00878 價格的 DataFrame
        initial_capital: 初始資金
        reinvest_dividend: 是否將股利再投入 (預設: 是)
    """
    df = df_data.copy()
    
    # Find first valid date for 00878
    first_valid_idx = df['00878'].first_valid_index()
    
    equity_arr = []
    log = []
    
    shares = 0
    cash = initial_capital
    has_bought = False
    total_cost_accum = 0
    total_dividend_received = 0
    
    for i in range(len(df)):
        date = df.index[i]
        date_str = date.strftime('%Y-%m-%d')
        price = df['00878'].iloc[i]
        
        # Buy on first valid day
        if not has_bought and not pd.isna(price) and price > 0:
            shares = int(cash / price)
            cost = shares * price
            
            # Transaction Cost
            fee = cost * 0.001425 * 0.6
            total_cost_accum += fee
            
            cash -= (cost + fee)
            has_bought = True
            
            log.append({
                '日期': date_str,
                '動作': '買進持有',
                '價格': f"{price:.2f}",
                '股數': shares,
                '成本': int(cost),
                '股利收入': 0,
                '剩餘現金': int(cash)
            })
        
        # Check for dividend payment
        if has_bought and date_str in DIVIDEND_00878:
            dividend_per_share = DIVIDEND_00878[date_str]
            dividend_income = shares * dividend_per_share
            total_dividend_received += dividend_income
            
            # Add dividend to cash first (Accumulate)
            cash += dividend_income
            
            if reinvest_dividend and not pd.isna(price) and price > 0:
                # Reinvest: Try to buy shares with TOTAL available cash (Accumulated)
                # Considering transaction cost: Price * Shares * (1 + FeeRate) <= Cash
                # FeeRate = 0.001425 * 0.6 ~= 0.000855
                cost_multiplier = 1 + (0.001425 * 0.6)
                
                # Max shares we can afford
                can_buy_shares = int(cash / (price * cost_multiplier))
                
                if can_buy_shares > 0:
                    reinvest_cost = can_buy_shares * price
                    fee = reinvest_cost * 0.001425 * 0.6
                    total_cost_accum += fee
                    
                    shares += can_buy_shares
                    cash -= (reinvest_cost + fee)
                    
                    log.append({
                        '日期': date_str,
                        '動作': f'股利再投入 (每股 ${dividend_per_share:.2f})',
                        '價格': f"{price:.2f}",
                        '股數': int(can_buy_shares),
                        '成本': int(reinvest_cost),
                        '股利收入': int(dividend_income),
                        '剩餘現金': int(cash)
                    })
                else:
                    # Cash accumulated but not enough for 1 share + fee
                    log.append({
                        '日期': date_str,
                        '動作': f'收取股利 (累積中) (每股 ${dividend_per_share:.2f})',
                        '價格': f"{price:.2f}",
                        '股數': 0,
                        '成本': 0,
                        '股利收入': int(dividend_income),
                        '剩餘現金': int(cash)
                    })
            else:
                # Not reinvesting, just keep in cash
                log.append({
                    '日期': date_str,
                    '動作': f'收取股利 (每股 ${dividend_per_share:.2f})',
                    '價格': f"{price:.2f}",
                    '股數': 0,
                    '成本': 0,
                    '股利收入': int(dividend_income),
                    '剩餘現金': int(cash)
                })
            
        # Calculate Equity
        if has_bought and not pd.isna(price):
            equity = shares * price + cash
        else:
            equity = initial_capital # Still holding cash
            
        equity_arr.append(equity)
        
    df['Total_Equity'] = equity_arr
    
    # Add summary to log
    if log:
        final_log_entry = log[-1].copy() if log else {}
        
    return df, pd.DataFrame(log), total_cost_accum, total_dividend_received

# =============================================================================
# 實戰資金配置計算器
# =============================================================================
def render_live_trading_page():
    """實戰分頁：計算期貨+00878 資金配置"""
    
    st.header("💰 實戰資金配置計算器")
    st.markdown("根據您的總資金，計算期貨口數與 00878 配置")
    
    # 自動抓取即時報價
    @st.cache_data(ttl=300)
    def fetch_current_prices():
        try:
            twii = yf.Ticker("^TWII")
            twii_hist = twii.history(period="1d")
            twii_price = int(twii_hist['Close'].iloc[-1]) if not twii_hist.empty else 23000
            
            etf = yf.Ticker("00878.TW")
            etf_hist = etf.history(period="1d")
            etf_price = round(etf_hist['Close'].iloc[-1], 2) if not etf_hist.empty else 24.0
            
            return {'twii': twii_price, 'etf': etf_price, 'success': True}
        except:
            return {'twii': 23000, 'etf': 24.0, 'success': False}
    
    prices = fetch_current_prices()
    if prices['success']:
        st.success("✅ 即時報價已載入")
    else:
        st.warning("⚠️ 無法取得即時報價，使用預設值")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 輸入參數")
        total_capital = st.number_input("總資金 (TWD)", value=3000000, step=100000, format="%d")
        target_leverage = st.slider("目標槓桿倍數", 1.0, 4.0, 2.0, 0.5)
        risk_indicator = st.slider("風險指標 (%)", 100, 500, 300, 50)
        current_index = st.number_input("目前加權指數 (自動)", value=prices['twii'], step=100)
        margin_per_contract = st.number_input("每口保證金", value=85000, step=5000)
        contract_type = st.selectbox("期貨種類", ["小台 (50 TWD/點)", "大台 (200 TWD/點)"])
        contract_multiplier = 50 if "小台" in contract_type else 200
        current_00878_price = st.number_input("00878 目前股價 (自動)", value=prices['etf'], step=0.1)
    
    with col2:
        st.subheader("📊 計算結果")
        
        target_exposure = total_capital * target_leverage
        target_contracts = int(round(target_exposure / (current_index * contract_multiplier)))
        required_margin = target_contracts * margin_per_contract
        cash_for_futures = required_margin * (risk_indicator / 100)
        remaining = total_capital - cash_for_futures
        shares_00878 = int(remaining / current_00878_price / 1000) * 1000
        actual_00878_cost = shares_00878 * current_00878_price
        final_cash = total_capital - actual_00878_cost
        
        st.metric("目標曝險金額", f"${target_exposure:,.0f}")
        st.markdown("---")
        st.markdown("#### 📈 期貨部位")
        st.metric("建議口數", f"{target_contracts} 口")
        st.metric("所需保證金", f"${required_margin:,.0f}")
        st.metric(f"期貨帳戶保留 ({risk_indicator}%)", f"${cash_for_futures:,.0f}")
        st.markdown("---")
        st.markdown("#### 💵 00878 部位")
        st.metric("可購買股數", f"{shares_00878:,} 股 ({shares_00878//1000} 張)")
        st.metric("購買金額", f"${actual_00878_cost:,.0f}")
        st.markdown("---")
        st.metric("期貨帳戶剩餘", f"${final_cash:,.0f}")
    
    # 預估收益
    st.markdown("---")
    st.subheader("📈 預估年化收益")
    col3, col4, col5 = st.columns(3)
    futures_yield = target_contracts * current_index * contract_multiplier * 0.04
    dividend_income = actual_00878_cost * 0.055
    total_passive = futures_yield + dividend_income
    
    with col3:
        st.metric("期貨逆價差收益", f"${futures_yield:,.0f}/年")
    with col4:
        st.metric("00878 股息收益", f"${dividend_income:,.0f}/年")
    with col5:
        st.metric("總被動收益", f"${total_passive:,.0f}/年", f"{total_passive/total_capital*100:.1f}%")
    
    st.warning("⚠️ 以上為估算，實際請依即時報價操作。期貨有保證金追繳風險。")

def render_original_strategy_page(df):
    # This logic matches lines 530+ of the backup, restored fully
    initial_capital = st.sidebar.number_input("初始總資金 (TWD)", value=1000000, step=100000)
    
    if 'ma_period' not in st.session_state: st.session_state['ma_period'] = 13
    ma_period = st.sidebar.number_input("加權指數均線週期 (MA)", value=st.session_state['ma_period'], step=1, key='ma_input_orig')
    if ma_period != st.session_state['ma_period']: st.session_state['ma_period'] = ma_period
    
    st.sidebar.subheader("資金分配與策略")
    do_rebalance = st.sidebar.checkbox("啟用每月動態平衡", value=True)
    if do_rebalance:
        rebalance_long_target = st.sidebar.slider("動態平衡：做多部位目標比例 (%)", 10, 100, 90, 5) / 100.0
        long_alloc = rebalance_long_target
    else:
        rebalance_long_target, long_alloc = 0.5, 0.5
        
    short_alloc = 1 - long_alloc
    st.sidebar.write(f"初始做多: {long_alloc:.0%} | 初始做空: {short_alloc:.0%}")
    
    margin = st.sidebar.number_input("小台保證金", 85000, step=1000)
    hedge_mode = st.sidebar.radio("避險模式", ("積極做空", "完全避險 (Neutral Hedge)"), index=1)
    
    st.sidebar.subheader("交易成本設定")
    fee = st.sidebar.number_input("手續費", 40)
    tax = st.sidebar.number_input("交易稅", 0.00002, format="%.5f")
    slip = st.sidebar.number_input("滑價", 1)
    inc_cost = st.sidebar.checkbox("計入成本", True)
    
    # Run
    df_res, trades, lp, sp, cost = run_backtest_original(
        df, ma_period, initial_capital, long_alloc, short_alloc, margin,
        hedge_mode, do_rebalance, rebalance_long_target, fee, tax, slip, inc_cost
    )
    
    # Tabs - Restoring ALL 7 Tabs
    # Tabs - Restoring ALL Tabs + New Comparison Tab
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["📊 總覽", "📈 績效分析", "📅 週期分析", "📋 交易明細", "🔭 最新訊號判斷", "🎯 參數敏感度", "🎮 真實操作模擬", "⚔️ 策略綜合比較"])
    
    with t1:
        st.subheader("回測結果總覽")
        
        fin = df_res['Total_Equity'].iloc[-1]
        ret = (fin - initial_capital) / initial_capital
        
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("期末總資產", f"{fin:,.0f}")
        with c2: metric_card("總報酬率", f"{ret:.2%}", delta=f"{ret:.2%}")
        with c3: metric_card("交易天數", f"{len(df_res)}")
        
        c4, c5, c6 = st.columns(3)
        with c4: metric_card("做的總獲利", f"{lp:,.0f}", delta=f"{lp/initial_capital:.1%}")
        with c5: metric_card("做空總獲利", f"{sp:,.0f}", delta=f"{sp/initial_capital:.1%}")
        with c6: metric_card("總成本", f"{cost:,.0f}", delta=f"-{cost/initial_capital:.1%}", delta_color="inverse")
        
        # Equity Curve
        st.subheader("資產曲線")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Total_Equity'], mode='lines', name='總資產 (策略)', line=dict(color='#d32f2f', width=3)))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Benchmark'], mode='lines', name='Buy & Hold 00631L (對照)', line=dict(color='#9e9e9e', width=3)))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Long_Equity'], mode='lines', name='做多部位', line=dict(width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Short_Equity'], mode='lines', name='做空部位', line=dict(width=1.5, dash='dot')))
        
        fig.update_layout(title="策略 vs. 純買進持有 (00631L)", xaxis_title="日期", yaxis_title="金額 (TWD)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), template="plotly_white", height=600)
        st.plotly_chart(fig, use_container_width=True)
        
        # Trend 100
        st.subheader("最近 100 日多空趨勢分析")
        dfr = df_res.iloc[-100:].copy()
        dfr['C'] = dfr['Position'].apply(lambda x: 'green' if x==1 else 'red')
        figt = go.Figure(go.Bar(x=dfr.index, y=dfr['TAIEX'], marker_color=dfr['C'], name='趨勢'))
        figt.update_layout(title="近100日趨勢 (紅=多方/綠=空方避險)", yaxis_range=[dfr['TAIEX'].min()*0.95, dfr['TAIEX'].max()*1.05], showlegend=False, xaxis_title="日期", yaxis_title="加權指數", template="plotly_white")
        st.plotly_chart(figt, use_container_width=True)
        
    with t2:
        st.subheader("績效統計")
        eq = df_res['Total_Equity']
        dd = (eq - eq.cummax()) / eq.cummax()
        mdd = dd.min()
        
        ben_eq = df_res['Benchmark']
        ben_dd = (ben_eq - ben_eq.cummax()) / ben_eq.cummax()
        ben_mdd = ben_dd.min()
        
        tr_cnt = len(trades)
        if trades:
            dft = pd.DataFrame(trades)
            win = dft['獲利金額 (TWD)'].gt(0).mean()
        else:
            win = 0
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("策略最大回撤 (MDD)", f"{mdd:.2%}", delta_color="inverse")
        with c2: metric_card("大盤最大回撤", f"{ben_mdd:.2%}", delta=f"{ben_mdd-mdd:.2%}", delta_color="inverse")
        with c3: metric_card("做空次數", f"{tr_cnt}")
        with c4: metric_card("做空勝率", f"{win:.2%}")
        
        st.subheader("回撤曲線 (Drawdown)")
        figd = go.Figure()
        figd.add_trace(go.Scatter(x=dd.index, y=dd, fill='tozeroy', line=dict(color='red'), name='策略回撤'))
        figd.add_trace(go.Scatter(x=ben_dd.index, y=ben_dd, line=dict(color='gray', dash='dot'), name='00631L回撤'))
        figd.update_layout(title="總資產回撤幅度", yaxis_title="回撤 %", hovermode="x unified", template="plotly_white", yaxis=dict(tickformat=".0%"))
        st.plotly_chart(figd, use_container_width=True)
        
    with t3:
        st.subheader("年度報酬率與風險分析")
        df_res['Year'] = df_res.index.year
        yr = df_res.groupby('Year').agg({'Total_Equity':['first','last'], 'Benchmark':['first','last']})
        
        yret = pd.DataFrame()
        yret['年化報酬率'] = (yr['Total_Equity']['last'] - yr['Total_Equity']['first']) / yr['Total_Equity']['first']
        yret['Benchmark 報酬率'] = (yr['Benchmark']['last'] - yr['Benchmark']['first']) / yr['Benchmark']['first']
        yret['超額報酬 (Alpha)'] = yret['年化報酬率'] - yret['Benchmark 報酬率']
        
        ymdd = []
        for year in yret.index:
            dy = df_res[df_res['Year'] == year]
            e = dy['Total_Equity']
            d = (e - e.cummax()) / e.cummax()
            ymdd.append(d.min())
        yret['策略最大回撤 (MDD)'] = ymdd
        
        # Add Avg
        avg = yret.mean()
        yret.loc['平均值 (Avg)'] = avg
        
        def hl_avg(row):
            if row.name == '平均值 (Avg)': return ['background-color: #fff8e1; color: #bf360c; font-weight: bold'] * len(row)
            return [''] * len(row)
            
        st.dataframe(yret.style.apply(hl_avg, axis=1).format("{:.2%}"), use_container_width=True)
        
        st.markdown("""
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-size: 0.9em; color: #555;">
        <b>指標說明：</b>
        <ul style="margin-bottom: 0;">
            <li><b>年化報酬率</b>: 策略在該年度的總投資報酬率</li>
            <li><b>Benchmark 報酬率</b>: 單純買進持有 00631L 的年度報酬率</li>
            <li><b>超額報酬 (Alpha)</b>: 策略報酬 - Benchmark 報酬</li>
            <li><b>策略最大回撤 (MDD)</b>: 該年度資產最大回落幅度</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.subheader("月度報酬率分析 (總資產)")
        df_res['Month'] = df_res.index.to_period('M')
        m_stats = df_res.groupby('Month')['Total_Equity'].agg(['first', 'last'])
        m_stats['Ret'] = (m_stats['last'] - m_stats['first']) / m_stats['first']
        m_stats['Y'] = m_stats.index.year
        m_stats['M'] = m_stats.index.month
        piv = m_stats.pivot(index='Y', columns='M', values='Ret')
        piv.columns = [f"{i}月" for i in range(1, 13)]
        
        def c_ret(v):
            if pd.isna(v): return ''
            c = 'red' if v > 0 else 'green'
            return f'color: {c}'
            
        st.dataframe(piv.style.format("{:.2%}").map(c_ret), use_container_width=True)
        
    with t4:
        st.subheader("📋 交易明細")
        if trades:
            df_trades = pd.DataFrame(trades)
            # Check if columns exist before applying
            if '進場日期' in df_trades.columns:
                df_trades['進場日期'] = df_trades['進場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            if '出場日期' in df_trades.columns:
                df_trades['出場日期'] = df_trades['出場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            
            def color_pnl(val):
                if pd.isna(val) or isinstance(val, str): return ''
                color = 'red' if val > 0 else 'green'
                return f'color: {color}'
            
            # Safe styling
            st.dataframe(df_trades.style.applymap(color_pnl, subset=['獲利金額 (TWD)', '報酬率'])
                         .format({'進場指數': '{:,.0f}', '出場指數': '{:,.0f}', '避險口數': '{:.2f}', 
                                  '獲利點數': '{:,.0f}', '獲利金額 (TWD)': '{:,.0f}', '報酬率': '{:.2%}'}),
                         use_container_width=True)
            
            # Annual Short P&L Summary
            st.divider()
            st.subheader("📅 每年做空避險損益統計")
            
            df_trades_raw = pd.DataFrame(trades)
            # Ensure '出場日期' is datetime
            if '出場日期' in df_trades_raw.columns:
                df_trades_raw['Year'] = pd.to_datetime(df_trades_raw['出場日期']).dt.year
                annual_short_pnl = df_trades_raw.groupby('Year')['獲利金額 (TWD)'].sum().reset_index()
                annual_short_pnl.columns = ['年份', '做空總損益 (TWD)']
                
                # Add Trade Count per year
                annual_counts = df_trades_raw.groupby('Year').size().reset_index(name='交易次數')
                annual_counts.columns = ['年份', '交易次數']
                annual_summary = pd.merge(annual_short_pnl, annual_counts, on='年份')
                
                # Calculate Average P&L per trade
                annual_summary['平均單筆損益'] = annual_summary['做空總損益 (TWD)'] / annual_summary['交易次數']
                
                def color_annual_pnl(val):
                    color = 'red' if val > 0 else 'green'
                    return f'color: {color}'

                st.dataframe(
                    annual_summary.style.applymap(color_annual_pnl, subset=['做空總損益 (TWD)', '平均單筆損益'])
                    .format({'年份': '{:d}', '做空總損益 (TWD)': '{:,.0f}', '平均單筆損益': '{:,.0f}'}),
                    use_container_width=True,
                    column_config={
                        "年份": st.column_config.NumberColumn("年份", format="%d"),
                    }
                )
            
            # Export Buttons
            st.divider()
            st.subheader("📥 資料匯出")
            col_ex1, col_ex2 = st.columns(2)
            
            csv_trades = df_trades.to_csv(index=False).encode('utf-8-sig')
            col_ex1.download_button(
                label="下載交易明細 (CSV)",
                data=csv_trades,
                file_name='trades_record.csv',
                mime='text/csv',
            )
            
            csv_equity = df_res.to_csv().encode('utf-8-sig')
            col_ex2.download_button(
                label="下載每日資產權益 (CSV)",
                data=csv_equity,
                file_name='daily_equity.csv',
                mime='text/csv',
            )
        else:
            st.info("區間內無做空交易")
            
    with t5:
        st.subheader("🔭 最新市場狀態與操作建議")
        
        last_row = df_res.iloc[-1]
        last_date = df_res.index[-1]
        last_close = last_row['TAIEX']
        last_ma = last_row['MA']
        last_00631L = last_row['00631L']
        
        # Load Real World Settings if available
        SETTINGS_FILE = "user_simulation_settings.json"
        real_settings = None
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    real_settings = json.load(f)
            except:
                pass
        
        # Determine Signal
        is_bearish = last_close < last_ma
        signal_text = "空方 (跌破均線)" if is_bearish else "多方 (站上均線)"
        action_text = "⚠️ 啟動避險 (做空小台)" if is_bearish else "✅ 僅持有做多部位 (00631L)"
        signal_color = "red" if not is_bearish else "green"
        
        st.markdown(f"""
        ### 📅 資料日期：{last_date.strftime('%Y-%m-%d')}
        
        #### 📊 市場數據
        - **加權指數收盤**：{last_close:,.0f}
        - **均線 ({ma_period}MA)**：{last_ma:,.0f}
        - **乖離率**：{((last_close - last_ma) / last_ma):.2%}
        
        #### 🚦 訊號判斷
        - **目前趨勢**：<span style="color:{signal_color};font-weight:bold;font-size:1.2em">{signal_text}</span>
        - **操作建議**：<span style="color:{signal_color};font-weight:bold;font-size:1.2em">{action_text}</span>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        st.subheader("💰 目前部位損益試算 (基於真實模擬設定)")
        
        col_s1, col_s2 = st.columns(2)
        
        # 1. 00631L Status
        with col_s1:
            st.markdown("#### 🐂 00631L (做多部位)")
            
            # Use Real Settings if available
            if real_settings:
                user_shares = real_settings.get('shares_00631L', 0)
                curr_val_00631L = user_shares * last_00631L
                st.write(f"**目前持有股數**：{user_shares:,.0f} 股")
            else:
                curr_val_00631L = df_res['Long_Equity'].iloc[-1]
                st.write(f"**目前模擬市值**：{curr_val_00631L:,.0f} TWD (回測資金)")

            st.write(f"**目前市值**：{curr_val_00631L:,.0f} TWD")
            st.write(f"**約當大盤曝險**：{curr_val_00631L * 2:,.0f} TWD (2倍槓桿)")
        
        # 2. Short Leg Status
        with col_s2:
            st.markdown("#### 🐻 小台 (做空避險部位)")
            
            if real_settings:
                # Real Mode
                held_contracts = real_settings.get('held_contracts', 0)
                is_holding_short = held_contracts > 0
                st.write(f"**目前持有口數**：{held_contracts} 口")
            else:
                # Sim Mode
                is_holding_short = last_row['Position'] == 1
                held_contracts = "模擬部位"

            if is_holding_short:
                st.write("**目前狀態**：🔴 持有空單中")
                
                # Reason for holding short
                if last_close < last_ma:
                    diff_points = last_ma - last_close
                    st.markdown(f"📉 **持有原因**：目前指數 ({last_close:,.0f}) 低於 {ma_period}MA ({last_ma:,.0f}) 共 **{diff_points:,.0f}** 點")
                    st.markdown(f"👉 **後續操作**：續抱空單")
                else:
                    diff_points = last_close - last_ma
                    st.markdown(f"⚠️ **持有原因**：昨日收盤跌破均線 (目前指數 {last_close:,.0f} 已高於均線 **{diff_points:,.0f}** 點，轉為多方訊號)")
                    st.markdown(f"👉 **後續操作**：🔴 **應平倉空單** (訊號轉多)")
                
                if not real_settings: # Only show entry analysis for Simulation Mode or if valid
                    # Find Entry (Logic: scan backwards for Position=0)
                    current_trade_entry_index = -1
                    for i in range(len(df_res)-1, -1, -1):
                        if df_res['Position'].iloc[i] == 0:
                            current_trade_entry_index = i + 1
                            break
                    if current_trade_entry_index == -1: current_trade_entry_index = 0
                    if current_trade_entry_index >= len(df_res): current_trade_entry_index = 0
                    
                    entry_row = df_res.iloc[current_trade_entry_index]
                    entry_date = df_res.index[current_trade_entry_index]
                    entry_price = entry_row['TAIEX']
                    
                    # Current Short P&L
                    contracts_est = 1 # Dummy for sim
                    points_diff = entry_price - last_close
                    profit_twd = points_diff * 50 * contracts_est
                    ret = (entry_price - last_close) / entry_price
                    
                    st.markdown("---")
                    st.markdown("#### ⚖️ 本次空單持有績效 (回測模擬)")
                    st.write(f"**進場日期**：{entry_date.strftime('%Y-%m-%d')}")
                    st.metric("進場指數", f"{entry_price:,.0f}")
                    st.metric("目前指數", f"{last_close:,.0f}", delta=f"{last_close - entry_price:,.0f}", delta_color="inverse")
                else:
                     st.info("真實部位損益請參考券商報價，此處僅提供策略訊號指引。")

            else:
                st.write("**目前狀態**：⚪ 空手 (無避險)")
                st.write(f"**明日操作指引**：{'續抱空單' if is_bearish else '維持空手'}")
        
    with t6:
        st.subheader("🎯 參數敏感度分析 (MA Sensitivity)")
        
        # Date Context
        if not df.empty:
            sa_start_date = df.index.min().date()
            sa_end_date = df.index.max().date()
            sa_days = (sa_end_date - sa_start_date).days
            sa_years = sa_days / 365.25
            st.info(f"此功能將測試不同均線週期對策略績效的影響。\n\n**目前回測區間**：{sa_start_date} ~ {sa_end_date} (約 {sa_years:.1f} 年)")
        
        col_sa1, col_sa2 = st.columns(2)
        ma_start = col_sa1.number_input("MA 起始", value=5, step=1)
        ma_end = col_sa2.number_input("MA 結束", value=80, step=1)
        ma_step = st.slider("間隔 (Step)", 1, 10, 2)
        
        if st.button("開始分析"):
            progress_bar = st.progress(0)
            results = []
            ma_range = range(ma_start, ma_end + 1, ma_step)
            total_steps = len(ma_range)
            
            for idx, m in enumerate(ma_range):
                # Run Backtest (Silent)
                _df, _trades, _lp, _sp, _cost = run_backtest_original(
                    df, m, initial_capital, long_alloc, short_alloc, margin, 
                    hedge_mode, do_rebalance, rebalance_long_target, fee, tax, slip, inc_cost
                )
                
                final_eq = _df['Total_Equity'].iloc[-1]
                ret = (final_eq - initial_capital) / initial_capital
                
                eq_curve = _df['Total_Equity']
                mdd = ((eq_curve - eq_curve.cummax()) / eq_curve.cummax()).min()
                
                results.append({
                    'MA': m,
                    'Return': ret,
                    'MDD': mdd
                })
                progress_bar.progress((idx + 1) / total_steps)
            
            df_sa = pd.DataFrame(results)
            
            # Find Best Parameter
            best_row = df_sa.loc[df_sa['Return'].idxmax()]
            best_ma = int(best_row['MA'])
            best_ret = best_row['Return']
            
            st.success(f"**最佳均線天數：{best_ma}**，累積報酬率：{best_ret:.2%}")
            
            # Benchmark Return
            benchmark_start = df['00631L'].iloc[0]
            benchmark_end = df['00631L'].iloc[-1]
            benchmark_ret = (benchmark_end - benchmark_start) / benchmark_start
            
            st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <strong>📊 績效對照：</strong>
                <ul>
                    <li><strong>策略最佳報酬率</strong>: {best_ret:.2%} (MA={best_ma})</li>
                    <li><strong>00631L (Buy & Hold) 報酬率</strong>: {benchmark_ret:.2%}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"套用最佳參數 (MA={best_ma})"):
                st.session_state['ma_period'] = best_ma
                st.rerun()
            
            # Visualization (Line Chart)
            st.subheader("不同均線天數累積報酬率")
            fig_sa_ret = go.Figure()
            fig_sa_ret.add_trace(go.Scatter(
                x=df_sa['MA'],
                y=df_sa['Return'],
                mode='lines+markers',
                name='累積報酬率',
                line=dict(width=3)
            ))
            fig_sa_ret.update_layout(
                xaxis_title="均線天數", 
                yaxis_title="累積報酬率", 
                template="plotly_white",
                hovermode="x unified"
            )
            st.plotly_chart(fig_sa_ret, use_container_width=True)
            
            st.subheader("🏆 績效前五名參數 (Top 5)")
            top_5 = df_sa.sort_values('Return', ascending=False).head(5).reset_index(drop=True)
            top_5.index += 1 # Rank 1-based
            
            # Format as string percentage to ensure integer display
            top_5['Return_Str'] = top_5['Return'].apply(lambda x: f"{x:.0%}")

            st.dataframe(
                top_5[['MA', 'Return_Str']],
                use_container_width=True,
                column_config={
                    "MA": st.column_config.NumberColumn("均線天數 (MA)", format="%d"),
                    "Return_Str": st.column_config.TextColumn("累積報酬率")
                }
            )
            
            st.markdown("---")
            st.markdown("""
            ### 🏆 總結：如何選擇最佳參數？
            最佳的參數通常是 **「報酬率高 (高原區)」** 與 **「回撤風險低 (淺水區)」** 的交集。
            *   若某個參數報酬率極高，但回撤也極大，可能不適合心臟不夠強的投資人。
            *   建議選擇一個**位於穩定的高原區中間**的數值，而不是極端值，以避免「過度擬合 (Overfitting)」的風險。
            """)
            
            st.success("分析完成！")
            
    with t7:
        st.subheader("🎮 真實操作模擬 (Real-world Simulation)")
        st.info("在此輸入您目前的實際資產狀況，系統將根據策略邏輯提供操作建議。")
        
        # Load Settings
        SETTINGS_FILE = "user_simulation_settings.json"
        default_settings = {
            "shares_00631L": 1000,
            "short_capital": 100000,
            "held_contracts": 0
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
            except:
                pass

        col_real_1, col_real_2 = st.columns(2)
        
        with col_real_1:
            st.markdown("#### 1. 輸入目前資產狀況")
            
            # Input Shares instead of Value
            real_shares_00631L = st.number_input("目前 00631L 持有股數 (Shares)", value=int(default_settings["shares_00631L"]), step=1000)
            real_short_capital = st.number_input("目前 期貨保證金專戶餘額 (權益數 TWD)", value=int(default_settings["short_capital"]), step=10000)
            real_held_contracts = st.number_input("目前 持有小台口數 (空單)", value=int(default_settings["held_contracts"]), step=1)
            
            # Save Settings
            current_settings = {
                "shares_00631L": real_shares_00631L,
                "short_capital": real_short_capital,
                "held_contracts": real_held_contracts
            }
            if current_settings != default_settings:
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(current_settings, f)
            
            st.markdown("#### 2. 確認市場數據 (預設為最新)")
            # Get last data from df_res
            last_row = df_res.iloc[-1]
            last_close_val = last_row['TAIEX']
            last_ma_val = last_row['MA']
            last_00631L_val = last_row['00631L']

            sim_last_close = st.number_input("加權指數收盤價", value=float(last_close_val), step=10.0)
            sim_ma = st.number_input(f"目前 {ma_period}MA", value=float(last_ma_val), step=10.0)
            
            # Auto-calc Value
            sim_price_00631L = last_00631L_val 
            real_long_value = real_shares_00631L * sim_price_00631L
            st.info(f"ℹ️ 00631L 目前參考價: {sim_price_00631L:.2f} | 推算市值: {real_long_value:,.0f} TWD")
            
        with col_real_2:
            st.markdown("#### 3. 策略運算結果")
            
            # Logic
            sim_is_bearish = sim_last_close < sim_ma
            sim_signal_text = "空方 (跌破均線)" if sim_is_bearish else "多方 (站上均線)"
            sim_signal_color = "red" if not sim_is_bearish else "green"
            
            st.markdown(f"**目前訊號**：<span style='color:{sim_signal_color};font-weight:bold'>{sim_signal_text}</span>", unsafe_allow_html=True)
            
            # Signal Details
            diff_points = sim_last_close - sim_ma
            if sim_is_bearish:
                st.caption(f"📉 指數 ({sim_last_close:,.0f}) 低於 {ma_period}MA ({sim_ma:,.0f}) 共 {abs(diff_points):,.0f} 點")
            else:
                st.caption(f"📈 指數 ({sim_last_close:,.0f}) 高於 {ma_period}MA ({sim_ma:,.0f}) 共 {abs(diff_points):,.0f} 點")
            
            # Calculate Target Contracts
            # Risk Limit
            safe_margin_factor = 3.0
            # Use 'margin' from outer scope
            sim_max_contracts = int(real_short_capital / (safe_margin_factor * margin)) if margin > 0 else 0
            
            if sim_is_bearish:
                if hedge_mode == "完全避險 (Neutral Hedge)":
                    sim_target_notional = real_long_value * 2
                    # Avoid divide by zero
                    if sim_last_close > 0:
                        sim_target_contracts_raw = int(round(sim_target_notional / (sim_last_close * 50)))
                    else:
                        sim_target_contracts_raw = 0
                    sim_target_contracts = min(sim_target_contracts_raw, sim_max_contracts)
                    hedge_reason = f"對沖 2倍市值 (目標 {sim_target_contracts_raw} 口)，受資金/風險限制"
                else: # Aggressive
                    sim_target_contracts = sim_max_contracts
                    hedge_reason = "積極做空 (資金允許最大口數，風險指標 >= 300%)"
            else:
                sim_target_contracts = 0
                hedge_reason = "多方趨勢，不需避險"
            
            # Action
            diff_contracts = sim_target_contracts - real_held_contracts
            
            if diff_contracts > 0:
                action_msg = f"🔴 加空 {diff_contracts} 口"
                action_desc = f"目前持有 {real_held_contracts} 口，目標 {sim_target_contracts} 口"
            elif diff_contracts < 0:
                action_msg = f"🟢 回補 {abs(diff_contracts)} 口"
                action_desc = f"目前持有 {real_held_contracts} 口，目標 {sim_target_contracts} 口"
            else:
                action_msg = "⚪ 維持現狀"
                action_desc = f"目前持有 {real_held_contracts} 口，符合目標"
            
            metric_card("建議操作", action_msg, delta=f"目標: {sim_target_contracts} 口 ({action_desc})")
            st.write(f"**策略邏輯**：{hedge_reason}")
            
            st.divider()
            
            # Risk Preview
            st.markdown("#### ⚠️ 調整後風險預估")
            sim_required_margin = sim_target_contracts * margin
            if sim_required_margin > 0:
                sim_risk_ratio = real_short_capital / sim_required_margin
            else:
                sim_risk_ratio = 999
            
            sim_risk_color = "red" if sim_risk_ratio < 3.0 else "green"
            # metric_card for Risk
            metric_card("預估風險指標", f"{sim_risk_ratio:.0%}", delta="目標 > 300%", delta_color="normal")
            
            if sim_risk_ratio < 3.0 and sim_target_contracts > 0:
                st.warning("⚠️ 注意：即使調整後，風險指標仍低於 300%，建議補錢或減少口數。")
            elif sim_target_contracts == 0:
                st.success("目前無部位，無風險。")
            else:
                st.success("風險指標安全。")

    # New Tab: Comparison
    with t8:
        render_comparison_page(df)

# --- Render Function: New Strategy ---
# Removed Rebalance Page as requested

# --- Render Function: Comparison ---
def render_comparison_page(df):
    st.subheader("策略綜合比較")
    
    col1, col2 = st.columns(2)
    # Fix: Explicitly use value=... to avoid 2000000 being interpreted as min_value
    cap = col1.number_input("比較初始資金", value=2000000, step=100000, min_value=100000)
    
    with st.expander("⚙️ 策略參數設定", expanded=True):
        tab_bench, tab_fut, tab_f8 = st.tabs(["基準 & 平衡策略", "純期貨策略", "期貨 + 00878"])
        
        with tab_bench:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ② 期貨避險策略")
                st.caption("持有 00631L + 空單避險")
                f_long_pct = st.slider("00631L 持有比例 (%)", 50, 100, 90, 5, key='comp_f_long') / 100.0
            
            with col2:
                st.markdown("#### ③ 資產平衡策略")
                st.caption("定期再平衡 00631L 與現金")
                r_long_pct = st.slider("00631L 配置比例 (%)", 10, 90, 50, 5, key='comp_r_long') / 100.0
                
        with tab_fut:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ④ 純期貨做多 (永遠多)")
                fut_lev = st.slider("期貨槓桿 (X)", 1.0, 5.0, 2.0, 0.5, key='comp_fut_lev')
                
                st.divider()
                st.markdown("#### ⑤ 純期貨趨勢 (多空)")
                ma_trend = st.number_input("趨勢均線 (MA)", 5, 200, 13, key='comp_ma_trend')
                st.caption(f">{ma_trend}MA 做多, <{ma_trend}MA 做空")
                
                st.divider()
                div_yield = st.slider("逆價差/殖利率 (%)", 0.0, 10.0, 4.0, 0.5, key='comp_div_yield') / 100.0
                ignore_short_yield = st.checkbox("做空不計逆價差 (測試)", False)
                
            with col2:
                st.markdown("#### ⑥ 純期貨波段 (MA做多)")
                ma_long_lev = st.slider("波段槓桿 (X)", 1.0, 10.0, 2.0, 0.5, key='comp_ma_long_lev')
                ma_long = st.number_input("波段均線 (MA)", 5, 200, 13, key='comp_ma_long')
                st.caption(f">{ma_long}MA 做多, 跌破平倉 (不放空)")

        with tab_f8:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ⑦ 期貨+00878 (永續)")
                st.caption("永遠持有期貨，剩餘買 00878")
                f8_lev = st.slider("期貨槓桿 (X)", 1.0, 4.0, 2.0, 0.5, key='f8_lev')
                f8_risk = st.number_input("風險指標 (%)", 100, 500, 300, 50, key='f8_risk') / 100.0
            
            with col2:
                st.markdown("#### ⑧ 期貨+00878 (均線)")
                st.caption("均線以上持有期貨，以下空手")
                f8m_lev = st.slider("期貨槓桿 (X)", 1.0, 5.0, 3.0, 0.5, key='f8m_lev')
                f8m_risk = st.number_input("風險指標 (%)", 100, 500, 300, 50, key='f8m_risk') / 100.0
                f8m_ma = st.number_input("操作均線 (MA)", 5, 200, 13, key='f8m_ma')

    if 'show_comparison' not in st.session_state:
        st.session_state['show_comparison'] = False

    if st.button("開始比較", type="primary"):
        st.session_state['show_comparison'] = True
        
    if st.session_state['show_comparison']:
        # 1. Futures (Uses user params)
        df_f, trades_f, _, _, cost_f = run_backtest_original(
            df, 13, cap, f_long_pct, 1-f_long_pct, 85000, 
            '完全避險 (Neutral Hedge)', True, f_long_pct, 
            40, 2e-5, 1, True
        )
        
        # 2. Rebalance (Uses user params)
        df_r, log_r, cost_r = run_backtest_rebalance(df, cap, r_long_pct)
        
        # 3. Pure Futures Long
        df_fl, log_fl, cost_fl, liq_fl = run_backtest_futures_simple(df, cap, fut_lev, 'Long-Only', 0, dividend_yield=div_yield)
        
        # 4. Futures Trend
        df_ft, log_ft, cost_ft, liq_ft = run_backtest_futures_simple(df, cap, fut_lev, 'Trend', ma_trend, dividend_yield=div_yield, ignore_short_yield=ignore_short_yield)
        
        # 5. Futures + 00878
        df_f8, log_f8, cost_f8, pnl_f8 = run_backtest_futures_00878(df, cap, f8_lev, 85000, f8_risk, dividend_yield=div_yield)
        
        # 6. Pure 00878 Buy & Hold (with dividend reinvestment)
        df_8only, log_8only, cost_8only, dividend_8only = run_backtest_00878_only(df, cap)
        
        # 7. Futures Long-MA
        df_fma, log_fma, cost_fma, liq_fma = run_backtest_futures_simple(df, cap, ma_long_lev, 'Long-MA', ma_long, dividend_yield=div_yield)
        
        # 8. Futures + 00878 (MA Long-Only)
        df_f8m, log_f8m, cost_f8m, liq_f8m, pnl_f8m = run_backtest_futures_00878_ma(df, cap, f8m_lev, 85000, f8m_risk, dividend_yield=div_yield, ma_period=f8m_ma)
        
        # --- 圖表模式選擇 ---
        chart_mode = st.radio("圖表顯示模式", ["報酬率 (%)", "絕對金額 (TWD)"], horizontal=True)
        
        # 計算報酬率 (從初始資本開始)
        def to_return_pct(equity_series, initial_cap):
            return (equity_series / initial_cap - 1) * 100
        
        # 準備資料 (根據模式選擇)
        if chart_mode == "報酬率 (%)":
            y_bench = to_return_pct(df_f['Benchmark'], cap)
            y_s2 = to_return_pct(df_f['Total_Equity'], cap)
            y_s3 = to_return_pct(df_r['Total_Equity'], cap)
            y_s4 = to_return_pct(df_fl['Total_Equity'], cap)
            y_s5 = to_return_pct(df_ft['Total_Equity'], cap)
            y_s6 = to_return_pct(df_fma['Total_Equity'], cap)
            y_s7 = to_return_pct(df_f8['Total_Equity'], cap)
            y_s8 = to_return_pct(df_f8m['Total_Equity'], cap)
            y_s9 = to_return_pct(df_8only['Total_Equity'], cap)
            y_label = "報酬率 (%)"
            y_format = ".2f"
            hover_suffix = "%"
        else:
            y_bench = df_f['Benchmark']
            y_s2 = df_f['Total_Equity']
            y_s3 = df_r['Total_Equity']
            y_s4 = df_fl['Total_Equity']
            y_s5 = df_ft['Total_Equity']
            y_s6 = df_fma['Total_Equity']
            y_s7 = df_f8['Total_Equity']
            y_s8 = df_f8m['Total_Equity']
            y_s9 = df_8only['Total_Equity']
            y_label = "總資產 (TWD)"
            y_format = ",.0f"
            hover_suffix = ""
        
        fig = go.Figure()
        
        # 主要策略曲線
        fig.add_trace(go.Scatter(x=df_f.index, y=y_bench, name='① Buy&Hold 00631L', 
            line=dict(color='gray', width=2),
            hovertemplate='%{x|%Y-%m-%d}<br>① Buy&Hold: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_f.index, y=y_s2, name=f'② 期貨避險 ({f_long_pct:.0%})', 
            line=dict(color='red', width=2),
            hovertemplate='%{x|%Y-%m-%d}<br>② 期貨避險: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_r.index, y=y_s3, name=f'③ 資產平衡 ({r_long_pct:.0%})', 
            line=dict(color='blue', width=2),
            hovertemplate='%{x|%Y-%m-%d}<br>③ 資產平衡: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_fl.index, y=y_s4, name=f'④ 純期貨做多 ({fut_lev}x)', 
            line=dict(color='orange', width=2, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>④ 純期貨做多: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_ft.index, y=y_s5, name=f'⑤ 純期貨趨勢 ({fut_lev}x) MA{ma_trend}', 
            line=dict(color='purple', width=2, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>⑤ 純期貨趨勢: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_fma.index, y=y_s6, name=f'⑥ 純期貨波段 ({ma_long_lev}x) MA{ma_long}', 
            line=dict(color='#FFD600', width=2),
            hovertemplate='%{x|%Y-%m-%d}<br>⑥ 純期貨波段: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_f8.index, y=y_s7, name=f'⑦ 期貨+00878永續 ({f8_lev}x)', 
            line=dict(color='#00C853', width=3),
            hovertemplate='%{x|%Y-%m-%d}<br>⑦ 期貨+00878永續: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_f8m.index, y=y_s8, name=f'⑧ 期貨+00878均線 ({f8m_lev}x) MA{f8m_ma}', 
            line=dict(color='#E91E63', width=2, dash='dashdot'),
            hovertemplate='%{x|%Y-%m-%d}<br>⑧ 期貨+00878均線: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        fig.add_trace(go.Scatter(x=df_8only.index, y=y_s9, name='⑨ 單純持有 00878', 
            line=dict(color='#00897B', width=2),
            hovertemplate='%{x|%Y-%m-%d}<br>⑨ 單純持有 00878: %{y:' + y_format + '}' + hover_suffix + '<extra></extra>'))
        
        # 買賣點標記已移至「策略買賣點詳情」區塊，主圖表保持清爽
        
        fig.update_layout(
            title='策略績效比較 (含逆價差調整)',
            xaxis_title='日期',
            yaxis_title=y_label,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_white",
            height=600,
            yaxis=dict(tickformat='.1f' if chart_mode == "報酬率 (%)" else ',.0f',
                       ticksuffix='%' if chart_mode == "報酬率 (%)" else '')
        )
        
        # 加入 0% 參考線 (報酬率模式)
        if chart_mode == "報酬率 (%)":
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Table
        data = []
        
        # Map strategy to their trade logs for calculating profit/loss
        strategy_logs_map = {
            'Buy&Hold 00631L': None,  # No trades
            '期貨避險策略': pd.DataFrame(trades_f) if trades_f else pd.DataFrame(),
            '資產平衡策略': log_r,
            '純期貨做多': log_fl,
            '純期貨趨勢 (多空)': log_ft,
            '期貨 + 00878': log_f8,
            '單純持有 00878': log_8only,
            '純期貨 (波段做多)': log_fma,
            '期貨+00878 MA做多': log_f8m
        }
        

        
        # (name, param, equity_series, cost, is_buyhold, is_liquidated)
        # is_buyhold=True means no trading, so profit/loss columns should show '-'
        strategies = [
            ('① Buy&Hold 00631L', '100% 持有', df_f['Benchmark'], 0, True, False), 
            ('② 期貨避險策略', f'00631L {f_long_pct:.0%} / 現金 {1-f_long_pct:.0%}', df_f['Total_Equity'], cost_f, False, False), 
            ('③ 資產平衡策略', f'00631L {r_long_pct:.0%} / 現金 {1-r_long_pct:.0%}', df_r['Total_Equity'], cost_r, False, False),
            ('④ 純期貨做多', f'槓桿 {fut_lev}x / 殖利率 {div_yield:.1%}', df_fl['Total_Equity'], cost_fl, False, liq_fl),
            ('⑤ 純期貨趨勢', f'槓桿 {fut_lev}x / MA{ma_trend} / 殖利率 {div_yield:.1%}', df_ft['Total_Equity'], cost_ft, False, liq_ft),
            ('⑥ 純期貨波段', f'槓桿 {ma_long_lev}x / MA{ma_long}', df_fma['Total_Equity'], cost_fma, False, liq_fma),
            ('⑦ 期貨+00878永續', f'槓桿 {f8_lev}x / 風險 {f8_risk:.0%}', df_f8['Total_Equity'], cost_f8, False, False),
            ('⑧ 期貨+00878均線', f'槓桿 {f8m_lev}x / MA{f8m_ma} / 風險 {f8m_risk:.0%}', df_f8m['Total_Equity'], cost_f8m, False, liq_f8m),
            ('⑨ 單純持有 00878', f'100% 持有 (股利: ${dividend_8only:,.0f})', df_8only['Total_Equity'], cost_8only, True, False)
        ]
        
        for name, param, d, cost, is_buyhold, is_liq in strategies:
            if len(d) == 0:
                continue

            final_val = d.iloc[-1]
            ret = (final_val - cap) / cap
            
            # CAGR
            days = (d.index[-1] - d.index[0]).days
            years = days / 365.25
            if years > 0:
                cagr = (final_val / cap) ** (1 / years) - 1
            else:
                cagr = 0
            
            # MDD
            roll_max = d.cummax()
            drawdown = (d - roll_max) / roll_max
            mdd = drawdown.min()
            
            # Add liquidation indicator to name if applicable
            display_name = f"💥 {name} (爆倉)" if is_liq else name
            
            data.append({
                '策略名稱': display_name,
                '參數設定': param,
                '總報酬率': ret,  # Keep as float for sorting
                '年化報酬率 (CAGR)': cagr,
                '最大回撤 (MDD)': mdd,
                '總交易成本': cost,
                '期末總資產': final_val
            })
        
        # Create DataFrame and sort by 總報酬率 descending
        df_comparison = pd.DataFrame(data)
        df_comparison = df_comparison.sort_values('總報酬率', ascending=False).reset_index(drop=True)
        

        
        try:
            # Format the DataFrame for display
            df_display = df_comparison.copy()
            if not df_display.empty:
                df_display['總報酬率'] = df_display['總報酬率'].apply(lambda x: f"{x:.2%}")
                df_display['年化報酬率 (CAGR)'] = df_display['年化報酬率 (CAGR)'].apply(lambda x: f"{x:.2%}")
                df_display['最大回撤 (MDD)'] = df_display['最大回撤 (MDD)'].apply(lambda x: f"{x:.2%}")
                df_display['總交易成本'] = df_display['總交易成本'].apply(lambda x: f"{x:,.0f}")
                df_display['期末總資產'] = df_display['期末總資產'].apply(lambda x: f"{x:,.0f}")
                
                st.table(df_display)
            else:
                st.warning("無資料可顯示")
        except Exception as e:
            st.error(f"表格顯示發生錯誤: {str(e)}")
            st.dataframe(df_comparison) # Fallback to raw dataframe
        
        # --- 期間績效分析表 ---
        st.subheader("📅 期間績效分析")
        st.caption("比較不同時間區間的策略表現 vs 買入持有")
        
        # 選擇要分析的策略
        strategy_for_period = st.selectbox(
            "選擇策略進行期間分析",
            ['⑥ 純期貨波段', '⑤ 純期貨趨勢', '④ 純期貨做多', '⑦ 期貨+00878永續', '⑧ 期貨+00878均線'],
            index=0,
            key='period_strategy'
        )
        
        # 映射策略名稱到對應的 DataFrame
        strategy_df_map = {
            '④ 純期貨做多': df_fl,
            '⑤ 純期貨趨勢': df_ft,
            '⑥ 純期貨波段': df_fma,
            '⑦ 期貨+00878永續': df_f8,
            '⑧ 期貨+00878均線': df_f8m
        }
        
        selected_df = strategy_df_map.get(strategy_for_period, df_fma)
        benchmark_series = df_f['Benchmark']
        
        # 計算期間績效
        def calc_period_return(equity_series, days_back):
            if len(equity_series) < days_back:
                return None
            start_val = equity_series.iloc[-days_back]
            end_val = equity_series.iloc[-1]
            return (end_val / start_val - 1)
        
        def calc_period_mdd(equity_series, days_back):
            if len(equity_series) < days_back:
                return None
            period_data = equity_series.iloc[-days_back:]
            roll_max = period_data.cummax()
            drawdown = (period_data - roll_max) / roll_max
            return drawdown.min()
        
        periods = [
            ('1M', 21),
            ('3M', 63),
            ('6M', 126),
            ('1Y', 252),
            ('總計', len(selected_df))
        ]
        
        period_data = []
        for period_name, days in periods:
            strat_ret = calc_period_return(selected_df['Total_Equity'], days)
            bench_ret = calc_period_return(benchmark_series, days)
            strat_mdd = calc_period_mdd(selected_df['Total_Equity'], days)
            
            if strat_ret is not None and bench_ret is not None:
                period_data.append({
                    '期間': period_name,
                    '策略報酬 (%)': f"{strat_ret:.2%}",
                    '買入持有報酬 (%)': f"{bench_ret:.2%}",
                    '超額報酬': f"{strat_ret - bench_ret:+.2%}",
                    '策略 MDD (%)': f"{strat_mdd:.2%}" if strat_mdd else '-'
                })
        
        if period_data:
            df_period = pd.DataFrame(period_data)
            
            # 使用 columns 顯示期間績效
            cols = st.columns(len(period_data))
            for i, row in enumerate(period_data):
                with cols[i]:
                    st.markdown(f"**{row['期間']}**")
                    
                    # 策略報酬 (顏色)
                    strat_val = float(row['策略報酬 (%)'].replace('%', '')) / 100
                    color = "red" if strat_val >= 0 else "green"
                    st.markdown(f"策略: <span style='color:{color}'>{row['策略報酬 (%)']}</span>", unsafe_allow_html=True)
                    
                    # 買入持有報酬
                    bench_val = float(row['買入持有報酬 (%)'].replace('%', '')) / 100
                    color = "red" if bench_val >= 0 else "green"
                    st.markdown(f"B&H: <span style='color:{color}'>{row['買入持有報酬 (%)']}</span>", unsafe_allow_html=True)
                    
                    # 超額報酬
                    alpha_val = float(row['超額報酬'].replace('%', '').replace('+', '')) / 100
                    color = "red" if alpha_val >= 0 else "green"
                    st.markdown(f"Alpha: <span style='color:{color}'>{row['超額報酬']}</span>", unsafe_allow_html=True)
                    
                    st.caption(f"MDD: {row['策略 MDD (%)']}")
        
        st.markdown("---")
        
        # --- PnL Breakdown for Futures + 00878 Strategies ---
        st.subheader("📊 期貨+00878 策略損益分解")
        
        st.markdown("---")
        with st.expander("📊 ⑦ & ⑧ 詳細損益分析 (期貨 vs 00878)", expanded=True):
            col_pnl1, col_pnl2 = st.columns(2)
            
            with col_pnl1:
                st.markdown("##### ⑦ 期貨+00878永續")
                c1, c2 = st.columns(2)
                c1.metric("期貨損益", f"{pnl_f8['期貨損益']:,.0f}")
                c2.metric("00878 損益", f"{pnl_f8['00878損益']:,.0f}")
                c1.metric("股利收入", f"{pnl_f8['股利收入']:,.0f}")
                
                total_f8_pnl = pnl_f8['期貨損益'] + pnl_f8['00878損益'] + pnl_f8['股利收入']
                c2.metric("總損益", f"{total_f8_pnl:,.0f}", delta=f"{total_f8_pnl/cap:.1%}")
            
            with col_pnl2:
                st.markdown(f"##### ⑧ 期貨+00878均線 (MA{f8m_ma})")
                c3, c4 = st.columns(2)
                c3.metric("期貨損益", f"{pnl_f8m['期貨損益']:,.0f}")
                c4.metric("00878 損益", f"{pnl_f8m['00878損益']:,.0f}")
                c3.metric("股利收入", f"{pnl_f8m['股利收入']:,.0f}")
                
                total_f8m_pnl = pnl_f8m['期貨損益'] + pnl_f8m['00878損益'] + pnl_f8m['股利收入']
                c4.metric("總損益", f"{total_f8m_pnl:,.0f}", delta=f"{total_f8m_pnl/cap:.1%}")

        
        # --- Detailed Strategy View (Buy/Sell Points) ---
        st.subheader("🔍 策略買賣點詳情")
        
        # Map strategy names to their logs (numbered to match comparison table)
        strategy_logs = {
            '② 期貨避險策略': pd.DataFrame(trades_f) if trades_f else pd.DataFrame(),
            '③ 資產平衡策略': log_r,
            '④ 純期貨做多': log_fl,
            '⑤ 純期貨趨勢': log_ft,
            '⑥ 純期貨波段': log_fma,
            '⑦ 期貨+00878永續': log_f8,
            '⑧ 期貨+00878均線': log_f8m,
            '⑨ 單純持有 00878': log_8only
        }
        
        selected_strategy = st.selectbox("選擇要查看買賣點的策略", list(strategy_logs.keys()), index=1)
        
        if selected_strategy:
            detail_log = strategy_logs[selected_strategy]
            
            if not detail_log.empty:
                # Time range selector for the chart
                st.markdown("**圖表時間範圍**")
                chart_range_options = {
                    "近1年": 252,    # ~252 trading days
                    "近2年": 504,
                    "近3年": 756,
                    "近5年": 1260,
                    "全部": 0
                }
                chart_range_cols = st.columns(5)
                selected_range = "全部"
                for i, (label, days) in enumerate(chart_range_options.items()):
                    if chart_range_cols[i].button(label, key=f"range_{label}"):
                        st.session_state['chart_range'] = label
                        
                selected_range = st.session_state.get('chart_range', '近3年')
                range_days = chart_range_options.get(selected_range, 0)
                
                # Filter the df for chart display
                if range_days > 0 and len(df) > range_days:
                    df_chart = df.iloc[-range_days:].copy()
                    st.caption(f"📅 顯示範圍: {selected_range} (共 {range_days} 個交易日)")
                else:
                    df_chart = df.copy()
                    
                # Create Figure
                fig_detail = go.Figure()
                
                # 1. Base Price Line (TAIEX or 00878 depending on strategy)
                if '00878' in selected_strategy:
                    # For 00878 strategies, maybe show 00878 price? 
                    # But most actions are based on TAIEX or rebalancing.
                    # Let's show TAIEX for consistency, or 00878 for Pure 00878.
                    if '⑥ 單純持有 00878' in selected_strategy:
                        fig_detail.add_trace(go.Scatter(x=df_chart.index, y=df_chart['00878'], name='00878 股價', line=dict(color='gray', width=1)))
                        price_col = '價格'
                    else:
                        fig_detail.add_trace(go.Scatter(x=df_chart.index, y=df_chart['TAIEX'], name='加權指數', line=dict(color='gray', width=1)))
                        price_col = '指數'
                else:
                    fig_detail.add_trace(go.Scatter(x=df_chart.index, y=df_chart['TAIEX'], name='加權指數', line=dict(color='gray', width=1)))
                    price_col = '指數'
                    
                # Get chart date range for filtering markers
                chart_start_date = df_chart.index.min()
                chart_end_date = df_chart.index.max()
                    
                # 2. Add Markers
                # Filter actions
                # Common actions: 新倉 (多/空), 平倉, 反手, 加碼, 減碼
                # Trades log (Strategy 1) has different format: 進場日期, 出場日期...
                
                if '① 期貨避險策略' in selected_strategy:
                    # Handle Strategy 1 (Trades format)
                    # Filter by date range
                    filtered_log = detail_log.copy()
                    if '進場日期' in filtered_log.columns:
                        filtered_log['進場日期'] = pd.to_datetime(filtered_log['進場日期'])
                        filtered_log = filtered_log[(filtered_log['進場日期'] >= chart_start_date) | 
                                                    (pd.to_datetime(filtered_log['出場日期']) >= chart_start_date)]
                    
                    if not filtered_log.empty:
                        # Plot Entries
                        mask_entry = filtered_log['進場日期'] >= chart_start_date
                        if mask_entry.any():
                            fig_detail.add_trace(go.Scatter(
                                x=filtered_log[mask_entry]['進場日期'], 
                                y=filtered_log[mask_entry]['進場指數'],
                                mode='markers',
                                name='進場 (空單)',
                                marker=dict(symbol='triangle-down', size=10, color='red')
                            ))
                        # Plot Exits
                        exit_dates = pd.to_datetime(filtered_log['出場日期'])
                        mask_exit = exit_dates >= chart_start_date
                        if mask_exit.any():
                            fig_detail.add_trace(go.Scatter(
                                x=exit_dates[mask_exit], 
                                y=filtered_log[mask_exit]['出場指數'],
                                mode='markers',
                                name='出場 (平倉)',
                                marker=dict(symbol='x', size=8, color='black')
                            ))
                else:
                    # Handle Standard Logs
                    # Check if '動作' column exists
                    if '動作' in detail_log.columns:
                        # Filter by date range
                        filtered_log = detail_log.copy()
                        if '日期' in filtered_log.columns:
                            filtered_log['日期_dt'] = pd.to_datetime(filtered_log['日期'])
                            filtered_log = filtered_log[filtered_log['日期_dt'] >= chart_start_date]
                        
                        if not filtered_log.empty:
                            # Define colors/symbols
                            # Long Entries: Green Triangle Up
                            # Short Entries: Red Triangle Down
                            # Close: Black X
                            # Reduce: Orange Circle
                            
                            # Helper to filter
                            def get_mask(keyword):
                                return filtered_log['動作'].str.contains(keyword, na=False)
                            
                            # Longs (New, Add, Reverse Long)
                            mask_long = get_mask('多') & (get_mask('新倉') | get_mask('加碼') | get_mask('反手'))
                            if mask_long.any():
                                fig_detail.add_trace(go.Scatter(
                                    x=pd.to_datetime(filtered_log[mask_long]['日期']),
                                    y=filtered_log[mask_long][price_col] if price_col in filtered_log.columns else filtered_log[mask_long]['成交價'],
                                    mode='markers',
                                    name='做多/加碼',
                                    marker=dict(symbol='triangle-up', size=10, color='green')
                                ))
                                
                            # Shorts (New, Add, Reverse Short)
                            mask_short = get_mask('空') & (get_mask('新倉') | get_mask('加碼') | get_mask('反手'))
                            if mask_short.any():
                                fig_detail.add_trace(go.Scatter(
                                    x=pd.to_datetime(filtered_log[mask_short]['日期']),
                                    y=filtered_log[mask_short][price_col] if price_col in filtered_log.columns else filtered_log[mask_short]['成交價'],
                                    mode='markers',
                                    name='做空/加碼',
                                    marker=dict(symbol='triangle-down', size=10, color='red')
                                ))
                                
                            # Close
                            mask_close = get_mask('平倉')
                            if mask_close.any():
                                fig_detail.add_trace(go.Scatter(
                                    x=pd.to_datetime(filtered_log[mask_close]['日期']),
                                    y=filtered_log[mask_close][price_col] if price_col in filtered_log.columns else filtered_log[mask_close]['成交價'],
                                    mode='markers',
                                    name='平倉',
                                    marker=dict(symbol='x', size=8, color='black')
                                ))
                                
                            # Reduce
                            mask_reduce = get_mask('減碼')
                            if mask_reduce.any():
                                fig_detail.add_trace(go.Scatter(
                                    x=pd.to_datetime(filtered_log[mask_reduce]['日期']),
                                    y=filtered_log[mask_reduce][price_col] if price_col in filtered_log.columns else filtered_log[mask_reduce]['成交價'],
                                    mode='markers',
                                    name='減碼',
                                    marker=dict(symbol='circle', size=8, color='orange')
                                ))
                                
                            # Rebalance (Strategy 2)
                            mask_rebal = get_mask('再平衡')
                            if mask_rebal.any():
                                 fig_detail.add_trace(go.Scatter(
                                    x=pd.to_datetime(filtered_log[mask_rebal]['日期']),
                                    y=filtered_log[mask_rebal]['成交價'], # 00631L Price
                                    mode='markers',
                                    name='再平衡',
                                    marker=dict(symbol='circle', size=6, color='blue')
                                ))
                                
                            # Buy & Hold (Strategy 6)
                            mask_buy = get_mask('買進持有')
                            if mask_buy.any():
                             fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_buy]['日期']),
                                y=detail_log[mask_buy]['價格'],
                                mode='markers',
                                name='買進',
                                marker=dict(symbol='triangle-up', size=12, color='green')
                            ))

                fig_detail.update_layout(
                    title=f'{selected_strategy} - 買賣點分佈',
                    xaxis_title='日期',
                    yaxis_title='指數 / 價格',
                    hovermode='closest',
                    template="plotly_white",
                    height=500
                )
                st.plotly_chart(fig_detail, use_container_width=True)
            else:
                st.info("此策略無交易紀錄")

        st.subheader("📋 各策略詳細交易紀錄")
        
        # 顯示模式選擇
        trade_display_mode = st.radio("顯示模式", ["卡片式 (推薦)", "表格式"], horizontal=True, key='trade_display_mode')
        
        # Color styling function for profit/loss
        def color_pnl(val):
            """獲利為紅色, 虧損為綠色 (台股慣例)"""
            if pd.isna(val) or isinstance(val, str):
                return ''
            try:
                num_val = float(val)
                if num_val > 0:
                    return 'color: red; font-weight: bold'
                elif num_val < 0:
                    return 'color: green; font-weight: bold'
                else:
                    return ''
            except:
                return ''
        
        def style_trade_log(log_df, pnl_columns=None):
            """Apply color styling to trade log dataframes"""
            if log_df is None or log_df.empty:
                return None
            
            styled = log_df.copy()
            
            # Find profit/loss columns to style
            if pnl_columns is None:
                # Auto-detect columns with keywords
                pnl_keywords = ['損益', '獲利', 'pnl', 'profit', 'PnL']
                pnl_columns = [col for col in styled.columns if any(kw in str(col).lower() for kw in pnl_keywords)]
            
            if pnl_columns and len(pnl_columns) > 0:
                existing_cols = [col for col in pnl_columns if col in styled.columns]
                if existing_cols:
                    return styled.style.map(color_pnl, subset=existing_cols)
            
            return styled
        
        def render_trade_cards(log_df, strategy_name):
            """以卡片式顯示交易紀錄"""
            if log_df is None or log_df.empty:
                st.info("無交易紀錄")
                return
            
            # 嘗試找出關鍵欄位
            cols = log_df.columns.tolist()
            
            # 常見欄位對應
            date_col = next((c for c in cols if '日期' in c), None)
            action_col = next((c for c in cols if '動作' in c or '備註' in c or '操作' in c), None)
            price_col = next((c for c in cols if '指數' in c or '價格' in c or '成交價' in c or 'TAIEX' in c), None)
            contracts_col = next((c for c in cols if '口數' in c or '股數' in c or '張數' in c), None)
            pnl_col = next((c for c in cols if '損益' in c or '獲利' in c or 'PnL' in c), None)
            equity_col = next((c for c in cols if '資產' in c or '淨值' in c or 'Equity' in c), None)
            
            # 顯示每筆交易
            for idx, row in log_df.iterrows():
                # 取得各欄位值
                date_val = str(row.get(date_col, '')) if date_col else str(idx)
                action_val = str(row.get(action_col, '')) if action_col else ''
                price_val = row.get(price_col, '') if price_col else ''
                contracts_val = row.get(contracts_col, '') if contracts_col else ''
                pnl_val = row.get(pnl_col, 0) if pnl_col else 0
                equity_val = row.get(equity_col, '') if equity_col else ''
                
                # 判斷買/賣標籤
                action_str = str(action_val).lower()
                if any(x in action_str for x in ['多', 'buy', '買', '進場', '新倉多']):
                    if '空' not in action_str:
                        badge = '<span style="background-color:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:4px;font-weight:bold">買入</span>'
                    else:
                        badge = '<span style="background-color:#ffebee;color:#c62828;padding:3px 10px;border-radius:4px;font-weight:bold">放空</span>'
                elif any(x in action_str for x in ['空', 'sell', '賣', '平倉', '出場']):
                    badge = '<span style="background-color:#ffebee;color:#c62828;padding:3px 10px;border-radius:4px;font-weight:bold">賣出</span>'
                elif any(x in action_str for x in ['平衡', '調整', 'rebalance']):
                    badge = '<span style="background-color:#e3f2fd;color:#1565c0;padding:3px 10px;border-radius:4px;font-weight:bold">調整</span>'
                elif action_val:
                    badge = f'<span style="background-color:#fafafa;color:#666;padding:3px 10px;border-radius:4px;border:1px solid #ddd">{action_val[:10]}</span>'
                else:
                    badge = ''
                
                # 價格顯示
                try:
                    price_display = f"{float(price_val):,.0f}" if price_val else ''
                except:
                    price_display = str(price_val) if price_val else ''
                
                # 口數顯示
                try:
                    contracts_display = f"{float(contracts_val):,.0f} 口" if contracts_val and float(contracts_val) != 0 else ''
                except:
                    contracts_display = str(contracts_val) if contracts_val else ''
                
                # 損益顯示
                try:
                    pnl_num = float(pnl_val) if pnl_val else 0
                    if pnl_num > 0:
                        pnl_display = f'<span style="color:red;font-weight:bold;font-size:1.1em">+{pnl_num:,.0f}元</span>'
                    elif pnl_num < 0:
                        pnl_display = f'<span style="color:green;font-weight:bold;font-size:1.1em">{pnl_num:,.0f}元</span>'
                    else:
                        pnl_display = ""
                except:
                    pnl_display = ""
                
                # 資產顯示
                try:
                    equity_display = f"淨值: {float(equity_val):,.0f}" if equity_val else ''
                except:
                    equity_display = ''
                
                # 組合卡片
                info_parts = [x for x in [price_display, contracts_display, equity_display] if x]
                info_str = ' | '.join(info_parts) if info_parts else ''
                
                card_html = f'''
                <div style="background:#fafafa;border:1px solid #e0e0e0;border-radius:8px;padding:12px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
                    <div style="display:flex;align-items:center;gap:12px">
                        <span style="color:#888;font-size:0.9em;min-width:90px">{date_val}</span>
                        {badge}
                        <span style="font-weight:500;color:#333">{info_str}</span>
                    </div>
                    <div>{pnl_display}</div>
                </div>
                '''
                st.markdown(card_html, unsafe_allow_html=True)
        
        with st.expander("② 期貨避險策略 - 交易明細"):
            if trades_f:
                df_trades_f = pd.DataFrame(trades_f)
                if trade_display_mode == "卡片式 (推薦)":
                    render_trade_cards(df_trades_f, "期貨避險策略")
                else:
                    styled_trades = df_trades_f.style.map(
                        color_pnl, 
                        subset=[col for col in ['獲利金額 (TWD)', '報酬率', '獲利點數'] if col in df_trades_f.columns]
                    )
                    st.dataframe(styled_trades, use_container_width=True)
            else:
                st.info("無交易紀錄")
                
        with st.expander("③ 資產平衡策略 - 再平衡紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_r, "資產平衡策略")
            else:
                st.dataframe(log_r, use_container_width=True)
            
        with st.expander("④ 純期貨做多 - 交易紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_fl, "純期貨做多")
            else:
                styled_fl = style_trade_log(log_fl, ['本筆損益'])
                if styled_fl is not None:
                    st.dataframe(styled_fl, use_container_width=True)
                else:
                    st.dataframe(log_fl, use_container_width=True)
            
        with st.expander("⑤ 純期貨趨勢 - 交易紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_ft, "純期貨趨勢")
            else:
                styled_ft = style_trade_log(log_ft, ['本筆損益'])
                if styled_ft is not None:
                    st.dataframe(styled_ft, use_container_width=True)
                else:
                    st.dataframe(log_ft, use_container_width=True)
            
        with st.expander("⑥ 純期貨波段 - 交易紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_fma, "純期貨波段")
            else:
                styled_fma = style_trade_log(log_fma, ['本筆損益'])
                if styled_fma is not None:
                    st.dataframe(styled_fma, use_container_width=True)
                else:
                    st.dataframe(log_fma, use_container_width=True)
            
        with st.expander("⑦ 期貨+00878永續 - 詳細紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_f8, "期貨+00878永續")
            else:
                st.dataframe(log_f8, use_container_width=True)
            
        with st.expander("⑧ 期貨+00878均線 - 詳細紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_f8m, "期貨+00878均線")
            else:
                st.dataframe(log_f8m, use_container_width=True)
            
        with st.expander("⑨ 單純持有 00878 - 交易紀錄"):
            if trade_display_mode == "卡片式 (推薦)":
                render_trade_cards(log_8only, "單純持有 00878")
            else:
                st.dataframe(log_8only, use_container_width=True)

# --- Main Flow ---
st.sidebar.header("資料來源")
dt_src = st.sidebar.selectbox("Source", ["Yahoo Finance", "Local File"])

df_g = None
start_date, end_date = None, None

# Load Data
if dt_src == "Yahoo Finance":
    try:
        # Simple load
        d1 = yf.download("00631L.TW", start="2014-01-01", progress=False)
        d2 = yf.download("^TWII", start="2014-01-01", progress=False)
        if isinstance(d1.columns, pd.MultiIndex): d1.columns = d1.columns.droplevel(1)
        if isinstance(d2.columns, pd.MultiIndex): d2.columns = d2.columns.droplevel(1)
        d1 = d1[['Close']].rename(columns={'Close': '00631L'})
        d2 = d2[['Close']].rename(columns={'Close': 'TAIEX'})
        
        # Download 00878 (Explicitly use auto_adjust=True to include dividends in Close)
        d3 = yf.download("00878.TW", start="2020-07-01", progress=False, auto_adjust=True)
        if isinstance(d3.columns, pd.MultiIndex): d3.columns = d3.columns.droplevel(1)
        d3 = d3[['Close']].rename(columns={'Close': '00878'})
        
        df_g = pd.merge(d1, d2, left_index=True, right_index=True)
        # Left join 00878 (it has shorter history)
        df_g = pd.merge(df_g, d3, left_index=True, right_index=True, how='left')
        st.sidebar.success("Yahoo Download OK")
    except:
        st.sidebar.error("Yahoo Error")
else:
    # Use default files if exist (check both current dir and subdirectory)
    file_00631L = "00631L_2015-2025.xlsx"
    file_taiex = "加權指數資料.xlsx"
    subdir = "50-for-2-VS-Taiwan-Futures-Index-main"
    
    # Check if files exist in current directory or subdirectory
    if os.path.exists(file_00631L):
        pass  # Use current directory
    elif os.path.exists(os.path.join(subdir, file_00631L)):
        file_00631L = os.path.join(subdir, file_00631L)
        file_taiex = os.path.join(subdir, file_taiex)
    
    if os.path.exists(file_00631L):
        d1 = pd.read_excel(file_00631L)
        d2 = pd.read_excel(file_taiex)
        # Quick clean
        def cl(d, n):
            d.columns = [str(x).lower() for x in d.columns]
            dc = [c for c in d if 'date' in c or '日期' in c][0]
            pc = [c for c in d if 'close' in c or '價' in c][0]
            d[dc] = pd.to_datetime(d[dc])
            return d[[dc, pc]].rename(columns={dc:'Date', pc:n}).set_index('Date')
        df_g = pd.merge(cl(d1, '00631L'), cl(d2, 'TAIEX'), left_index=True, right_index=True)
        
        # Try load 00878 from file if exists, else fill NaN
        file_00878 = "00878.xlsx"
        if os.path.exists(file_00878):
             d3 = pd.read_excel(file_00878)
             df_g = pd.merge(df_g, cl(d3, '00878'), left_index=True, right_index=True, how='left')
        elif os.path.exists(os.path.join(subdir, file_00878)):
             d3 = pd.read_excel(os.path.join(subdir, file_00878))
             df_g = pd.merge(df_g, cl(d3, '00878'), left_index=True, right_index=True, how='left')
        else:
             df_g['00878'] = np.nan
        st.sidebar.success("Local File Loaded")

if df_g is not None and not df_g.empty:
    min_d, max_d = df_g.index.min(), df_g.index.max()
    
    if pd.isna(min_d) or pd.isna(max_d):
        st.error("資料索引異常 (NaT)，請檢查資料來源。")
    else:
        # Streamlit date_input expects date objects, not timestamps
        min_d = min_d.date()
        max_d = max_d.date()
        
        # Ensure range is valid
        if min_d > max_d:
            st.error("資料日期範圍無效 (Start > End)")
        else:
            rng = st.sidebar.date_input("區間", [min_d, max_d], min_value=min_d, max_value=max_d)
            
            if len(rng) == 2:
                start_date, end_date = rng
                
                # Filter global df here
                mask = (df_g.index >= pd.to_datetime(start_date)) & (df_g.index <= pd.to_datetime(end_date))
                df_test_raw = df_g.loc[mask].copy()

                st.sidebar.markdown("---")
                
                # 頁面選擇
                page_mode = st.sidebar.radio(
                    "📌 選擇模式",
                    ["📊 回測分析", "💰 實戰計算器"],
                    index=0
                )
                
                if page_mode == "📊 回測分析":
                    render_original_strategy_page(df_test_raw)
                else:
                    render_live_trading_page()

            else:
                st.info("請選擇完整的開始與結束日期")

elif df_g is not None and df_g.empty:
    st.warning("下載或讀取的資料為空，無法進行回測。")
else:
    st.info("資料載入中，您可先使用實戰計算器")
    render_live_trading_page()

