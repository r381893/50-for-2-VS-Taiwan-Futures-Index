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
# 0056 股息資料 (年配 → 2023年起改季配)
# =============================================================================
DIVIDEND_0056 = {
    # 年配期間 (2009-2022)
    '2009-10-28': 2.60,
    '2010-10-28': 2.20,
    '2011-10-26': 2.00,
    '2012-10-24': 1.75,
    '2013-10-23': 1.50,
    '2014-10-23': 1.80,
    '2015-10-27': 0.95,
    '2016-10-26': 1.30,
    '2017-10-26': 1.30,
    '2018-10-25': 1.45,
    '2019-10-23': 1.80,
    '2020-10-22': 2.50,
    '2021-10-22': 1.80,
    '2022-10-19': 2.10,
    # 季配期間 (2023-)  
    '2023-01-30': 1.80,  # 2022年度配息
    '2023-07-18': 1.00,
    '2023-10-19': 1.20,
    '2024-01-17': 0.70,
    '2024-04-18': 0.79,
    '2024-07-16': 1.07,
    '2024-10-17': 1.07,
    '2025-01-17': 0.80,  # 預估
}

def get_dividend_0056(date_str):
    """取得指定日期的 0056 股息"""
    return DIVIDEND_0056.get(date_str, 0)

def get_dividend_etf(date_str, etf_code):
    """根據 ETF 代號取得股息"""
    if etf_code == '00878':
        return DIVIDEND_00878.get(date_str, 0)
    elif etf_code == '0056':
        return DIVIDEND_0056.get(date_str, 0)
    return 0

# 預設值 (在 sidebar 選擇前使用)
ETF_CODE = '00878'
ETF_DIVIDEND = DIVIDEND_00878

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


st.set_page_config(page_title="台灣五十正2 資產再平衡避險回測", layout="wide")
st.title("台灣五十正2 資產再平衡避險回測")

# --- CSS Styling (Modernized with Dark Mode) ---
st.markdown("""
<style>
    /* ===== CSS Variables for Theme ===== */
    :root {
        --bg-primary: #ffffff;
        --bg-secondary: #f8f9fa;
        --bg-card: rgba(255, 255, 255, 0.85);
        --text-primary: #1a1a2e;
        --text-secondary: #666666;
        --border-color: rgba(0, 0, 0, 0.08);
        --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.06);
        --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.08);
        --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.12);
        --accent-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --accent-red: #e53935;
        --accent-green: #43a047;
        --accent-blue: #1e88e5;
        --glass-blur: blur(10px);
    }
    
    /* Dark Mode Variables */
    [data-theme="dark"], .dark {
        --bg-primary: #0e1117;
        --bg-secondary: #1a1a2e;
        --bg-card: rgba(30, 30, 46, 0.85);
        --text-primary: #e8e8e8;
        --text-secondary: #a0a0a0;
        --border-color: rgba(255, 255, 255, 0.08);
    }
    
    /* ===== Base Typography ===== */
    html, body, [class*="css"] { 
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft JhengHei', sans-serif;
    }
    
    /* ===== Modern Metric Card ===== */
    .metric-card {
        background: var(--bg-card);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 24px;
        box-shadow: var(--shadow-md);
        text-align: center;
        margin-bottom: 12px;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }
    .metric-label { 
        font-size: 0.85rem; 
        color: var(--text-secondary); 
        margin-bottom: 8px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value { 
        font-size: 2rem; 
        font-weight: 700; 
        color: var(--text-primary);
        line-height: 1.2;
    }
    .metric-delta { 
        font-size: 0.9rem; 
        margin-top: 8px;
        font-weight: 500;
    }
    .delta-pos { color: var(--accent-red); }
    .delta-neg { color: var(--accent-green); }
    .delta-neutral { color: var(--text-secondary); font-size: 0.8rem; }
    
    /* ===== Accent Card Variants ===== */
    .metric-card-accent {
        background: var(--accent-gradient);
        color: white;
    }
    .metric-card-accent .metric-label,
    .metric-card-accent .metric-value { color: white; }
    
    /* ===== Colored Card Variants ===== */
    /* 藍色 - 股票/做多部位 */
    .metric-card-blue {
        background: linear-gradient(135deg, rgba(33, 150, 243, 0.08) 0%, rgba(33, 150, 243, 0.02) 100%);
        border-left: 4px solid #2196F3;
    }
    .metric-card-blue .metric-value { color: #1565C0; }
    
    /* 橙色 - 避險/警示 */
    .metric-card-orange {
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.08) 0%, rgba(255, 152, 0, 0.02) 100%);
        border-left: 4px solid #FF9800;
    }
    .metric-card-orange .metric-value { color: #E65100; }
    
    /* 紅色 - 獲利 (台股傳統) */
    .metric-card-red {
        background: linear-gradient(135deg, rgba(244, 67, 54, 0.08) 0%, rgba(244, 67, 54, 0.02) 100%);
        border-left: 4px solid #F44336;
    }
    .metric-card-red .metric-value { color: #C62828; }
    
    /* 綠色 - 虧損 (台股傳統) */
    .metric-card-green {
        background: linear-gradient(135deg, rgba(76, 175, 80, 0.08) 0%, rgba(76, 175, 80, 0.02) 100%);
        border-left: 4px solid #4CAF50;
    }
    .metric-card-green .metric-value { color: #2E7D32; }
    
    /* 紫色 - 總覽/重要數據 */
    .metric-card-purple {
        background: linear-gradient(135deg, rgba(156, 39, 176, 0.08) 0%, rgba(156, 39, 176, 0.02) 100%);
        border-left: 4px solid #9C27B0;
    }
    .metric-card-purple .metric-value { color: #7B1FA2; }
    
    /* ===== Modern Tabs ===== */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px;
        background: var(--bg-secondary);
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] { 
        height: auto;
        min-height: 48px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        padding: 12px 20px;
        font-weight: 600;
        color: var(--text-secondary);
        border: none;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(0, 0, 0, 0.05);
        color: var(--text-primary);
    }
    .stTabs [aria-selected="true"] { 
        background: var(--accent-gradient) !important;
        color: white !important;
        box-shadow: var(--shadow-sm);
    }
    
    /* ===== Sidebar Styling ===== */
    section[data-testid="stSidebar"] {
        background: var(--bg-secondary);
    }
    section[data-testid="stSidebar"] .stExpander {
        background: var(--bg-card);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        margin-bottom: 8px;
    }
    
    /* ===== Expander Styling ===== */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: var(--text-primary);
    }
    
    /* ===== Info Cards ===== */
    .info-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0;
        border-left: 4px solid var(--accent-blue);
    }
    .warning-card {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0;
        border-left: 4px solid #ff9800;
    }
    .success-card {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 12px 0;
        border-left: 4px solid var(--accent-green);
    }
    
    /* ===== Trade Card Styling ===== */
    .trade-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 10px;
        transition: all 0.2s ease;
    }
    .trade-card:hover {
        border-color: rgba(102, 126, 234, 0.3);
        box-shadow: var(--shadow-sm);
    }
    
    /* ===== Button Styling ===== */
    .stButton > button[kind="primary"] {
        background: var(--accent-gradient);
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 12px 24px;
        transition: all 0.2s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }
    
    /* ===== DataFrames ===== */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* ===== Dividers ===== */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border-color), transparent);
        margin: 24px 0;
    }
</style>
""", unsafe_allow_html=True)

def metric_card(label, value, delta=None, delta_color="normal", color=None):
    """
    顯示指標卡片
    color: None (預設) / 'blue' (股票) / 'orange' (避險) / 'red' (獲利) / 'green' (虧損) / 'purple' (重要)
    """
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
    
    # 決定卡片顏色類別
    card_class = "metric-card"
    if color:
        card_class = f"metric-card metric-card-{color}"
    
    st.markdown(f'<div class="{card_class}"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{delta_html}</div>', unsafe_allow_html=True)

# --- 1. Original Backtest Function (Unchanged Logic) ---
def run_backtest_original(df_data, ma_period, initial_capital, long_allocation_pct, short_allocation_pct, 
                          margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
                          cost_fee, cost_tax, cost_slippage, include_costs, safe_margin=3.0):
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
                # Contracts - 根據避險模式決定是否做空
                if hedge_mode == "不做空 (純再平衡)":
                    # 不做空模式：無避險口數
                    actual_contracts = 0
                else:
                    # 做空避險模式：計算避險需求口數 (Delta Neutral)
                    max_contracts = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
                    tg_notional = long_equity * 2
                    tg_contracts = int(round(tg_notional / (prev_taiex * 50)))
                    actual_contracts = min(tg_contracts, max_contracts)
                    
                diff = price_taiex - prev_taiex
                short_pnl = actual_contracts * diff * 50 * (-1)
                current_short_capital += short_pnl
                total_short_pnl += short_pnl
        
        # Costs & Trades
        prev_pos = df['Position'].iloc[i-1] if i > 0 else 0
        if position != prev_pos:
            # 根據避險模式決定口數
            if hedge_mode == "不做空 (純再平衡)":
                act_c = 0
            else:
                # 做空避險模式
                max_c = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
                tg_c = int(round((long_equity * 2) / (price_taiex * 50)))
                act_c = min(tg_c, max_c)
                
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
                
                # 記錄進場時的均線狀態（用於平倉時顯示）
                entry_ma_val = df['MA'].iloc[i]
                entry_signal_status = '⚠️ 低於均線' if entry_price < entry_ma_val else '✅ 高於均線'
            elif position == 0 and in_trade:
                in_trade = False
                exit_price = price_taiex
                pts = entry_price - exit_price
                
                # Re-calc entries logic for record
                if hedge_mode == "不做空 (純再平衡)":
                    act_ce = 0
                else:
                    # 做空避險模式
                    max_ce = int(entry_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
                    tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
                    act_ce = min(tg_ce, max_ce)
                
                prof_twd = pts * 50 * act_ce
                entry_notional = act_ce * entry_price * 50
                eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
                ret = (entry_price - exit_price) / entry_price
                
                # 獲取出場時的均線狀態
                ma_val_exit = df['MA'].iloc[i]
                exit_signal_status = '⚠️ 低於均線' if exit_price < ma_val_exit else '✅ 高於均線'
                
                # 只在有做空模式下記錄平倉交易
                if hedge_mode != "不做空 (純再平衡)":
                    trades.append({
                        '交易類型': '🔴 平倉',
                        '進場訊號': entry_signal_status,
                        '進場日期': entry_date, '進場指數': int(entry_price),
                        '進場均線': int(entry_ma_val) if not pd.isna(entry_ma_val) else '-',
                        '出場訊號': exit_signal_status,
                        '出場日期': date, '出場指數': int(exit_price),
                        '出場均線': int(ma_val_exit) if not pd.isna(ma_val_exit) else '-',
                        '避險口數': int(act_ce), '獲利點數': int(pts),
                        '獲利金額 (TWD)': int(prof_twd), '報酬率': round(ret * eff_lev, 4)
                    })

        short_equity = current_short_capital
        total_equity = long_equity + short_equity
        
        # Rebalance
        curr_month = date.month
        if do_rebalance and i > 0 and curr_month != last_month:
            old_long = long_equity
            old_short = short_equity
            t_long = total_equity * rebalance_long_target
            t_short = total_equity * (1 - rebalance_long_target)
            shares_00631L = t_long / price_00631L
            current_short_capital = t_short
            long_equity = t_long
            short_equity = t_short
            
            # 記錄再平衡交易
            ma_val_reb = df['MA'].iloc[i]
            signal_status_reb = '⚠️ 低於均線' if price_taiex < ma_val_reb else '✅ 高於均線'
            trades.append({
                '交易類型': '⚖️ 再平衡',
                '訊號狀態': signal_status_reb,
                '進場日期': date, '進場指數': int(price_taiex),
                '均線值': int(ma_val_reb) if not pd.isna(ma_val_reb) else '-',
                '出場日期': '-', '出場指數': '-',
                '避險口數': 0, '獲利點數': 0,
                '獲利金額 (TWD)': 0, '報酬率': 0,
                '備註': f'做多: {old_long:,.0f}→{t_long:,.0f} | 做空: {old_short:,.0f}→{t_short:,.0f}'
            })
            
        last_month = curr_month
        
        long_equity_arr.append(long_equity)
        short_equity_arr.append(short_equity)
        total_equity_arr.append(total_equity)
        
    # 處理持倉中的交易（尚未平倉）
    if in_trade:
        now_price = df['TAIEX'].iloc[-1]
        pts = entry_price - now_price
        
        if hedge_mode == "不做空 (純再平衡)":
            act_ce = 0
        else:
            # 做空避險模式
            max_ce = int(entry_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
            tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
            act_ce = min(tg_ce, max_ce)
        
        prof_twd = pts * 50 * act_ce
        entry_notional = act_ce * entry_price * 50
        eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
        ret = (entry_price - now_price) / entry_price
        
        # 獲取當前均線狀態
        current_ma = df['MA'].iloc[-1]
        current_signal = '⚠️ 低於均線' if now_price < current_ma else '✅ 高於均線'
        
        # 只在有做空模式下記錄持倉中交易
        if hedge_mode != "不做空 (純再平衡)":
            trades.append({
                '交易類型': '⏳ 持倉中',
                '進場訊號': entry_signal_status,
                '進場日期': entry_date, '進場指數': int(entry_price),
                '進場均線': int(entry_ma_val) if not pd.isna(entry_ma_val) else '-',
                '出場訊號': current_signal,
                '出場日期': df.index[-1], '出場指數': int(now_price),
                '出場均線': int(current_ma) if not pd.isna(current_ma) else '-',
                '避險口數': int(act_ce), '獲利點數': int(pts),
                '獲利金額 (TWD)': int(prof_twd), '報酬率': round(ret * eff_lev, 4),
                '備註': '未實現損益'
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
            # 使用動態選擇的 ETF 股息資料
            date_str = date.strftime('%Y-%m-%d')
            if shares_00878 > 0 and date_str in ETF_DIVIDEND:
                dividend_per_share = ETF_DIVIDEND[date_str]
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
            
            # 00878 Dividend Income (使用動態選擇的 ETF)
            date_str = date.strftime('%Y-%m-%d')
            if shares_00878 > 0 and date_str in ETF_DIVIDEND:
                dividend_per_share = ETF_DIVIDEND[date_str]
                dividend_income = shares_00878 * dividend_per_share
                cash += dividend_income  # 股利進現金
                total_dividend_received += dividend_income
            
            # Accumulate component PnL
            total_futures_pnl += fut_pnl
            total_00878_pnl += stock_pnl
            
            cash += fut_pnl  # Futures PnL settles to cash
            
            # Check for liquidation
            # 策略8的關鍵：跌破均線會主動平倉，所以需要用「即時信號」判斷
            # 如果當天價格 < MA，策略會在稍後的 rebalance 中平倉，不應該算爆倉
            current_ma = df['MA'].iloc[i]
            realtime_should_flat = (not pd.isna(current_ma) and price_taiex < current_ma)
            
            required_margin = abs(held_contracts) * margin_per_contract
            # 只有當「即時信號仍為做多」且「現金不足」時才爆倉
            if held_contracts != 0 and not realtime_should_flat and cash < required_margin * 0.25:
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
                # Flat: 期貨平倉 + 00878 也賣掉，全部保留現金等待
                target_contracts = 0
                final_00878_val = 0  # 空手時不買 00878
                note = f"空手 (全現金等待)"
            
            # 3. Execute Futures Rebalance
            held_contracts = target_contracts
            
            diff_contracts = held_contracts - prev_contracts
            if diff_contracts != 0:
                f_cost = abs(diff_contracts) * (cost_fee + cost_tax * price_taiex * 50 + cost_slippage * 50)
                cash -= f_cost
                total_cost_accum += f_cost
            
            # 4. Execute 00878 Rebalance 
            # 重要：信號變化時也要調整 00878（尤其是空手時要全賣）
            should_rebal_00878 = monthly_rebal or signal_changed
            
            if should_rebal_00878:
                if final_00878_val > 0 and not pd.isna(price_00878):
                    # 做多：計算目標持股
                    current_equity_after_futures = cash + (prev_shares * price_00878 if not pd.isna(price_00878) else 0)
                    shares_00878 = final_00878_val / price_00878
                    cash = current_equity_after_futures - (shares_00878 * price_00878)
                elif final_00878_val == 0 and prev_shares > 0:
                    # 空手：賣掉所有 00878
                    if not pd.isna(price_00878):
                        cash += prev_shares * price_00878
                    shares_00878 = 0
                
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
        
        # Check for dividend payment (使用動態選擇的 ETF)
        if has_bought and date_str in ETF_DIVIDEND:
            dividend_per_share = ETF_DIVIDEND[date_str]
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

def render_original_strategy_page(df):
    # === 側欄參數設定 (使用 Expander 整理) ===
    
    # 🎯 核心參數 (永遠可見)
    st.sidebar.markdown("### 🎯 核心參數")
    initial_capital = st.sidebar.number_input("初始總資金 (TWD)", value=1000000, step=100000)
    
    if 'ma_period' not in st.session_state: st.session_state['ma_period'] = 13
    ma_period = st.sidebar.number_input("均線週期 (MA)", value=st.session_state['ma_period'], step=1, key='ma_input_orig')
    if ma_period != st.session_state['ma_period']: st.session_state['ma_period'] = ma_period
    
    # 📊 資金配置 (Expander)
    with st.sidebar.expander("📊 資金配置", expanded=True):
        do_rebalance = st.checkbox("啟用每月動態平衡", value=True)
        
        # 先選擇避險模式 (簡化為 2 個選項)
        hedge_mode = st.radio("避險模式", ("不做空 (純再平衡)", "做空避險"), index=0)
        
        # 根據避險模式決定資金配置
        if do_rebalance:
            if hedge_mode == "不做空 (純再平衡)":
                # 不做空模式：股票 + 現金，純再平衡
                rebalance_long_target = st.slider("做多部位目標比例 (%)", 10, 100, 80, 5) / 100.0
                long_alloc = rebalance_long_target
                st.info("📌 純再平衡：維持股票/現金比例，不做空期貨")
            else:
                # 做空模式：允許用戶自訂比例
                rebalance_long_target = st.slider("做多部位目標比例 (%)", 10, 95, 80, 5) / 100.0
                long_alloc = rebalance_long_target
        else:
            rebalance_long_target, long_alloc = 0.5, 0.5
            
        short_alloc = 1 - long_alloc
        
        # 根據模式顯示不同的說明
        if hedge_mode == "不做空 (純再平衡)":
            st.caption(f"做多: {long_alloc:.0%} | 保留現金: {short_alloc:.0%}")
        else:
            st.caption(f"做多: {long_alloc:.0%} | 做空現金: {short_alloc:.0%}")
    
    # ⚙️ 進階設定 (Expander - 預設收合)
    with st.sidebar.expander("⚙️ 進階設定", expanded=False):
        margin = st.number_input("小台保證金", 85000, step=1000)
        safe_margin = st.slider(
            "安全倍數 (保證金緩衝)", 
            min_value=1.0, max_value=5.0, value=3.0, step=0.5,
            help="數值越低，可開越多口避險，但爆倉風險越高。建議 2.0~3.0"
        )
        st.markdown("**交易成本**")
        fee = st.number_input("手續費 (每口)", 40)
        tax = st.number_input("交易稅率", 0.00002, format="%.5f")
        slip = st.number_input("滑價 (點)", 1)
        inc_cost = st.checkbox("計入交易成本", True)
    
    # Run
    df_res, trades, lp, sp, cost = run_backtest_original(
        df, ma_period, initial_capital, long_alloc, short_alloc, margin,
        hedge_mode, do_rebalance, rebalance_long_target, fee, tax, slip, inc_cost, safe_margin
    )
    
    # === Tabs 重組 (5 → 4) ===
    # 合併邏輯:
    # - 總覽: 保留
    # - 績效分析: 合併 績效統計 + 週期分析 + 參數敏感度
    # - 交易明細: 保留
    # - 訊號與模擬: 合併 訊號判斷 + 真實操作模擬
    
    t1, t2, t3, t4 = st.tabs([
        "📊 總覽", 
        "📈 績效分析", 
        "📋 交易明細", 
        "🔭 訊號與模擬"
    ])
    
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
        st.subheader("📈 績效統計")
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
        
        # 回撤曲線
        figd = go.Figure()
        figd.add_trace(go.Scatter(x=dd.index, y=dd, fill='tozeroy', line=dict(color='red'), name='策略回撤'))
        figd.add_trace(go.Scatter(x=ben_dd.index, y=ben_dd, line=dict(color='gray', dash='dot'), name='00631L回撤'))
        figd.update_layout(title="回撤曲線 (Drawdown)", yaxis_title="回撤 %", hovermode="x unified", template="plotly_white", yaxis=dict(tickformat=".0%"), height=400)
        st.plotly_chart(figd, use_container_width=True)
        
        # === 年度/月度分析 (Expander) ===
        with st.expander("📅 年度 & 月度報酬分析", expanded=False):
            st.markdown("#### 年度報酬率與風險分析")
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
            
            avg = yret.mean()
            yret.loc['平均值 (Avg)'] = avg
            
            def hl_avg(row):
                if row.name == '平均值 (Avg)': return ['background-color: #fff8e1; color: #bf360c; font-weight: bold'] * len(row)
                return [''] * len(row)
                
            st.dataframe(yret.style.apply(hl_avg, axis=1).format("{:.2%}"), use_container_width=True)
            
            st.markdown("---")
            st.markdown("#### 月度報酬率熱力圖")
            df_res['Month'] = df_res.index.to_period('M')
            m_stats = df_res.groupby('Month')['Total_Equity'].agg(['first', 'last'])
            m_stats['Ret'] = (m_stats['last'] - m_stats['first']) / m_stats['first']
            m_stats['Y'] = m_stats.index.year
            m_stats['M'] = m_stats.index.month
            piv = m_stats.pivot(index='Y', columns='M', values='Ret')
            # 根據實際存在的月份動態命名欄位
            piv.columns = [f"{m}月" for m in piv.columns]
            
            def c_ret(v):
                if pd.isna(v): return ''
                c = 'red' if v > 0 else 'green'
                return f'color: {c}'
                
            st.dataframe(piv.style.format("{:.2%}").map(c_ret), use_container_width=True)
        
        # === 參數敏感度分析 (Expander) ===
        with st.expander("🎯 參數敏感度分析", expanded=False):
            st.info(f"測試不同均線週期對策略績效的影響")
            
            col_sa1, col_sa2 = st.columns(2)
            ma_start = col_sa1.number_input("MA 起始", value=5, step=1, key='sa_start')
            ma_end = col_sa2.number_input("MA 結束", value=80, step=1, key='sa_end')
            ma_step = st.slider("間隔 (Step)", 1, 10, 2, key='sa_step')
            
            if st.button("開始分析", key='btn_sensitivity'):
                progress_bar = st.progress(0)
                results = []
                ma_range = range(ma_start, ma_end + 1, ma_step)
                total_steps = len(ma_range)
                
                for idx, m in enumerate(ma_range):
                    _df, _trades, _lp, _sp, _cost = run_backtest_original(
                        df, m, initial_capital, long_alloc, short_alloc, margin, 
                        hedge_mode, do_rebalance, rebalance_long_target, fee, tax, slip, inc_cost, safe_margin
                    )
                    
                    final_eq = _df['Total_Equity'].iloc[-1]
                    ret = (final_eq - initial_capital) / initial_capital
                    eq_curve = _df['Total_Equity']
                    mdd_val = ((eq_curve - eq_curve.cummax()) / eq_curve.cummax()).min()
                    
                    results.append({'MA': m, 'Return': ret, 'MDD': mdd_val})
                    progress_bar.progress((idx + 1) / total_steps)
                
                df_sa = pd.DataFrame(results)
                best_row = df_sa.loc[df_sa['Return'].idxmax()]
                
                st.success(f"**最佳均線：MA {int(best_row['MA'])}**，報酬率：{best_row['Return']:.2%}")
                
                fig_sa = go.Figure()
                fig_sa.add_trace(go.Scatter(x=df_sa['MA'], y=df_sa['Return'], mode='lines+markers', name='累積報酬率'))
                fig_sa.update_layout(xaxis_title="均線天數", yaxis_title="報酬率", template="plotly_white")
                st.plotly_chart(fig_sa, use_container_width=True)
        
    # === t3: 交易明細 (原 t4 內容) ===
    with t3:
        st.subheader("📋 交易明細")
        if trades:
            df_trades = pd.DataFrame(trades)
            if '進場日期' in df_trades.columns:
                df_trades['進場日期'] = df_trades['進場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            if '出場日期' in df_trades.columns:
                df_trades['出場日期'] = df_trades['出場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            
            # 按日期排序
            df_trades = df_trades.sort_values(by='進場日期', ascending=True).reset_index(drop=True)
            
            # 統計資訊
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            trade_types = df_trades['交易類型'].value_counts() if '交易類型' in df_trades.columns else {}
            with col_stat1:
                n_close = trade_types.get('🔴 平倉', 0)
                st.metric("🔴 已平倉", f"{n_close} 筆")
            with col_stat2:
                n_rebal = trade_types.get('⚖️ 再平衡', 0)
                st.metric("⚖️ 再平衡", f"{n_rebal} 次")
            with col_stat3:
                n_open = trade_types.get('⏳ 持倉中', 0)
                st.metric("⏳ 持倉中", f"{n_open} 筆")
            
            st.divider()
            
            # 顏色樣式函數
            def color_trade_type(val):
                if pd.isna(val) or not isinstance(val, str):
                    return ''
                if '平倉' in val:
                    return 'background-color: #ffebee; color: #c62828'
                elif '持倉中' in val:
                    return 'background-color: #fff8e1; color: #f57c00'
                elif '再平衡' in val:
                    return 'background-color: #e3f2fd; color: #1565c0'
                return ''
            
            def color_pnl(val):
                if pd.isna(val) or isinstance(val, str):
                    return ''
                try:
                    v = float(val)
                    if v > 0:
                        return 'color: #c62828; font-weight: bold'  # 紅色獲利
                    elif v < 0:
                        return 'color: #2e7d32; font-weight: bold'  # 綠色虧損
                except:
                    pass
                return ''
            
            def color_signal(val):
                if pd.isna(val) or not isinstance(val, str):
                    return ''
                if '低於均線' in val:
                    return 'background-color: #fff3e0; color: #e65100'  # 橘色警告背景
                elif '高於均線' in val:
                    return 'background-color: #e8f5e9; color: #2e7d32'  # 綠色安全背景
                return ''
            
            # 安全格式化函數（處理混合類型欄位）
            def safe_format_number(val):
                if pd.isna(val) or isinstance(val, str):
                    return val if isinstance(val, str) else '-'
                try:
                    return f"{val:,.0f}"
                except:
                    return str(val)
            
            def safe_format_percent(val):
                if pd.isna(val) or isinstance(val, str):
                    return val if isinstance(val, str) else '-'
                try:
                    return f"{val:.2%}"
                except:
                    return str(val)
            
            # 建立樣式
            styled_df = df_trades.style
            
            if '交易類型' in df_trades.columns:
                styled_df = styled_df.map(color_trade_type, subset=['交易類型'])
            
            # 套用訊號顏色到進場訊號和出場訊號欄位
            signal_cols = [c for c in ['進場訊號', '出場訊號'] if c in df_trades.columns]
            if signal_cols:
                styled_df = styled_df.map(color_signal, subset=signal_cols)
            
            # 只對數值欄位套用顏色
            pnl_cols = [c for c in ['獲利金額 (TWD)', '報酬率', '獲利點數'] if c in df_trades.columns]
            if pnl_cols:
                styled_df = styled_df.map(color_pnl, subset=pnl_cols)
            
            # 使用安全格式化
            num_cols = [c for c in ['進場指數', '出場指數', '進場均線', '出場均線', '避險口數', '獲利點數', '獲利金額 (TWD)'] if c in df_trades.columns]
            if num_cols:
                styled_df = styled_df.format({c: safe_format_number for c in num_cols})
            
            if '報酬率' in df_trades.columns:
                styled_df = styled_df.format({'報酬率': safe_format_percent})
            
            st.dataframe(styled_df, use_container_width=True, height=500)
            
            # 年度統計 (Expander)
            with st.expander("📅 年度做空損益統計", expanded=False):
                df_trades_raw = pd.DataFrame(trades)
                if '出場日期' in df_trades_raw.columns:
                    # 只統計有實際出場日期的交易（排除 '-' 和再平衡記錄）
                    df_trades_valid = df_trades_raw[
                        (df_trades_raw['出場日期'] != '-') & 
                        (df_trades_raw['交易類型'] == '🔴 平倉')
                    ].copy()
                    
                    if len(df_trades_valid) > 0:
                        df_trades_valid['Year'] = pd.to_datetime(df_trades_valid['出場日期']).dt.year
                        annual_pnl = df_trades_valid.groupby('Year')['獲利金額 (TWD)'].sum().reset_index()
                        annual_pnl.columns = ['年份', '做空總損益 (TWD)']
                        annual_counts = df_trades_valid.groupby('Year').size().reset_index(name='交易次數')
                        annual_counts.columns = ['年份', '交易次數']
                        annual_summary = pd.merge(annual_pnl, annual_counts, on='年份')
                        annual_summary['平均單筆損益'] = annual_summary['做空總損益 (TWD)'] / annual_summary['交易次數']
                    
                        def color_annual(val):
                            return f"color: {'red' if val > 0 else 'green'}"
                        
                        st.dataframe(
                            annual_summary.style.map(color_annual, subset=['做空總損益 (TWD)', '平均單筆損益'])
                            .format({'年份': '{:d}', '做空總損益 (TWD)': '{:,.0f}', '平均單筆損益': '{:,.0f}'}),
                            use_container_width=True
                        )
                    else:
                        st.info("尚無已平倉的做空交易")
            
            # 匯出按鈕
            st.divider()
            col_ex1, col_ex2 = st.columns(2)
            csv_trades = df_trades.to_csv(index=False).encode('utf-8-sig')
            col_ex1.download_button("📥 下載交易明細 (CSV)", csv_trades, 'trades_record.csv', 'text/csv')
            csv_equity = df_res.to_csv().encode('utf-8-sig')
            col_ex2.download_button("📥 下載每日權益 (CSV)", csv_equity, 'daily_equity.csv', 'text/csv')
        else:
            st.info("區間內無做空交易")
    
    # === t4: 訊號與模擬 (合併 原t5 + 原t7) ===
    with t4:
        st.subheader("🔭 最新市場訊號")
        
        last_row = df_res.iloc[-1]
        last_date = df_res.index[-1]
        last_close = last_row['TAIEX']
        last_ma = last_row['MA']
        last_00631L = last_row['00631L'] if '00631L' in last_row else 0
        
        is_bearish = last_close < last_ma
        signal_text = "🔴 空方 (跌破均線)" if is_bearish else "🟢 多方 (站上均線)"
        action_text = "⚠️ 啟動避險 (做空小台)" if is_bearish else "✅ 僅持有做多部位"
        
        col_sig1, col_sig2, col_sig3 = st.columns(3)
        with col_sig1:
            metric_card("加權指數", f"{last_close:,.0f}", delta=f"MA{ma_period}: {last_ma:,.0f}", color="purple")
        with col_sig2:
            metric_card("00631L 價格", f"{last_00631L:.2f}", color="blue")
        with col_sig3:
            signal_color = "orange" if is_bearish else "green"
            metric_card("趨勢訊號", signal_text, color=signal_color)
        
        st.markdown(f"""
        **資料日期**：{last_date.strftime('%Y-%m-%d')}  
        **乖離率**：{((last_close - last_ma) / last_ma):.2%}  
        **操作建議**：{action_text}
        """)
        
        # === 我的持倉狀況 (主要顯示區) ===
        st.divider()
        st.subheader("💼 我的持倉狀況")
        
        # 讀取設定檔
        SETTINGS_FILE = "user_simulation_settings.json"
        
        def load_settings():
            try:
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except:
                pass
            return {"shares_00631L": 0, "cost_price_00631L": 20.0, "short_capital": 0, "held_contracts": 0, "hedge_entry_price": 0, "use_auto_calc": True}
        
        def save_settings(settings):
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        
        settings = load_settings()
        
        # 取得最新價格
        current_price_00631L = last_row['00631L'] if '00631L' in last_row else 0
        
        # === 自動計算模式 vs 手動輸入模式 ===
        use_auto_calc = st.checkbox("🔄 根據側邊欄配置自動計算持倉", value=settings.get("use_auto_calc", True), key="auto_calc_mode")
        
        if use_auto_calc:
            # 根據側邊欄的 initial_capital 和 long_alloc 自動模擬 (使用回測起始價)
            mode_text = {"不做空 (純再平衡)": "純再平衡", "做空避險": "做空避險"}
            st.info(f"📊 回測模擬：{initial_capital:,} TWD | {long_alloc:.0%}:{short_alloc:.0%} | {mode_text.get(hedge_mode, '')} | {'每月再平衡' if do_rebalance else '無再平衡'}")
            
            # 使用原始 df 資料進行模擬 (不是 df_res)
            sim_df = df.copy()
            sim_df['MA'] = sim_df['TAIEX'].rolling(ma_period).mean()
            
            sim_long_pct = long_alloc
            sim_short_pct = short_alloc
            start_price_00631L = sim_df['00631L'].iloc[0]
            start_taiex = sim_df['TAIEX'].iloc[0]
            sim_margin = margin
            sim_safe_margin = safe_margin
            
            # 驗證 00631L 起始價是否合理 (應該小於 1000)
            if start_price_00631L > 1000:
                st.warning(f"⚠️ 00631L 起始價異常 ({start_price_00631L:.2f})，可能資料有誤！請檢查資料來源。")
            
            # 初始股數計算 (使用回測起始價)
            initial_shares = (initial_capital * sim_long_pct) / start_price_00631L
            st.caption(f"🔧 00631L 起始價: {start_price_00631L:.2f} | 加權指數: {start_taiex:,.0f} | 初始股數: {initial_shares:,.0f} 股 ({initial_shares/1000:.1f} 張)")
            
            # 初始配置
            sim_shares = initial_shares
            sim_cash = initial_capital * sim_short_pct
            sim_contracts = 0  # 持有的空單口數
            sim_futures_pnl_total = 0  # 累計期貨損益
            last_taiex = sim_df['TAIEX'].iloc[0]
            last_month = sim_df.index[0].month
            
            for i in range(len(sim_df)):
                date = sim_df.index[i]
                price_00631L = sim_df['00631L'].iloc[i]
                price_taiex = sim_df['TAIEX'].iloc[i]
                ma_value = sim_df['MA'].iloc[i] if not pd.isna(sim_df['MA'].iloc[i]) else 0
                is_bearish_signal = price_taiex < ma_value if ma_value > 0 else False
                
                # 計算當前期貨未實現損益 (空單獲利 = 前日指數 - 今日指數)
                if sim_contracts > 0 and i > 0:
                    daily_futures_pnl = (last_taiex - price_taiex) * sim_contracts * 50
                    sim_futures_pnl_total += daily_futures_pnl
                    sim_cash += daily_futures_pnl  # 損益計入現金
                
                # 計算當前總資產
                long_value = sim_shares * price_00631L
                total_assets_now = long_value + sim_cash
                
                # 根據避險模式決定目標口數 (簡化為 2 種)
                if hedge_mode == "不做空 (純再平衡)":
                    target_contracts = 0
                else:  # 做空避險
                    if is_bearish_signal:
                        hedge_needed = int(round((long_value * 2) / (price_taiex * 50))) if price_taiex > 0 else 0
                        max_contracts = int(sim_cash / (sim_safe_margin * sim_margin)) if sim_margin > 0 else 0
                        target_contracts = min(hedge_needed, max_contracts)
                    else:
                        target_contracts = 0
                
                # 調整期貨部位
                if target_contracts != sim_contracts:
                    sim_contracts = target_contracts
                
                # 每月再平衡 (只調整股票和現金，不動期貨)
                curr_month = date.month
                if do_rebalance and i > 0 and curr_month != last_month:
                    # 計算不含期貨部位的資產
                    rebalance_base = long_value + sim_cash
                    target_long = rebalance_base * sim_long_pct
                    target_short = rebalance_base * sim_short_pct
                    sim_shares = target_long / price_00631L if price_00631L > 0 else sim_shares
                    sim_cash = target_short
                
                last_taiex = price_taiex
                last_month = curr_month
            
            # 最終結果
            shares_00631L = int(sim_shares)
            short_capital = int(sim_cash)
            cost_price = start_price_00631L
            held_contracts = sim_contracts
            hedge_entry_price = int(last_taiex) if sim_contracts > 0 else 0
            futures_total_pnl = int(sim_futures_pnl_total)
            
            # 顯示模擬結果
            final_value = shares_00631L * current_price_00631L + short_capital
            st.caption(f"📈 模擬結束: {shares_00631L:,} 股 ({shares_00631L/1000:.1f} 張) | 現金: {short_capital:,} | 期貨損益: {futures_total_pnl:+,}")
            
            # 儲存自動計算結果
            if st.button("💾 儲存自動計算結果", key="save_auto"):
                new_settings = {
                    "shares_00631L": shares_00631L,
                    "cost_price_00631L": cost_price,
                    "short_capital": short_capital,
                    "held_contracts": held_contracts,
                    "hedge_entry_price": hedge_entry_price,
                    "use_auto_calc": True
                }
                save_settings(new_settings)
                st.success("✅ 已儲存！")
        else:
            # === 手動輸入模式 ===
            with st.expander("⚙️ 編輯持倉設定", expanded=True):
                col_set1, col_set2 = st.columns(2)
                with col_set1:
                    new_shares = st.number_input(
                        "00631L 持股 (股)", 
                        min_value=0, max_value=1000000, 
                        value=int(settings.get("shares_00631L", 0)), 
                        step=1000,
                        key='edit_shares'
                    )
                    new_cost = st.number_input(
                        "00631L 成本價 (TWD)", 
                        min_value=0.0, max_value=1000.0, 
                        value=float(settings.get("cost_price_00631L", 20.0)), 
                        step=0.1,
                        format="%.2f",
                        key='edit_cost'
                    )
                with col_set2:
                    new_short_capital = st.number_input(
                        "做空用現金 (TWD)", 
                        min_value=0, max_value=100000000, 
                        value=int(settings.get("short_capital", 0)), 
                        step=10000,
                        key='edit_capital'
                    )
                    new_contracts = st.number_input(
                        "目前避險口數 (口)", 
                        min_value=0, max_value=1000, 
                        value=int(settings.get("held_contracts", 0)), 
                        step=1,
                        key='edit_contracts'
                    )
                
                new_hedge_entry = st.number_input(
                    "避險進場指數 (若有空單)", 
                    min_value=0, max_value=50000, 
                    value=int(settings.get("hedge_entry_price", 0)), 
                    step=100,
                    key='edit_hedge_entry'
                )
                
                if st.button("💾 儲存設定", type="primary"):
                    new_settings = {
                        "shares_00631L": new_shares,
                        "cost_price_00631L": new_cost,
                        "short_capital": new_short_capital,
                        "held_contracts": new_contracts,
                        "hedge_entry_price": new_hedge_entry,
                        "use_auto_calc": False
                    }
                    save_settings(new_settings)
                    st.success("✅ 設定已儲存！")
                    st.rerun()
            
            # 從設定檔讀取值
            shares_00631L = settings.get("shares_00631L", 0)
            cost_price = settings.get("cost_price_00631L", 20.0)
            short_capital = settings.get("short_capital", 0)
            held_contracts = settings.get("held_contracts", 0)
            hedge_entry_price = settings.get("hedge_entry_price", 0)
        
        # === 計算損益 ===
        # 00631L 損益
        long_market_value = shares_00631L * current_price_00631L
        long_cost_value = shares_00631L * cost_price
        long_unrealized_pnl = long_market_value - long_cost_value
        long_return_pct = (long_unrealized_pnl / long_cost_value * 100) if long_cost_value > 0 else 0
        
        # 避險損益 (如果有持倉)
        hedge_unrealized_pnl = 0
        if held_contracts > 0 and hedge_entry_price > 0:
            # 空單獲利 = (進場價 - 現價) * 口數 * 50
            hedge_unrealized_pnl = (hedge_entry_price - last_close) * held_contracts * 50
        
        # 總資產
        total_assets = long_market_value + short_capital + hedge_unrealized_pnl
        total_cost = long_cost_value + (settings.get("initial_short_capital", short_capital))
        
        # === 損益顯示 ===
        st.markdown("### 📈 00631L 持倉")
        
        # 驗證價格是否合理
        if cost_price > 1000 or current_price_00631L > 1000:
            st.error(f"⚠️ 價格數據異常！成本價: {cost_price:.2f}, 現價: {current_price_00631L:.2f}。00631L 價格應該在 10~400 之間，請檢查資料來源。")
        
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            metric_card("持有股數", f"{shares_00631L:,} 股", delta=f"約 {shares_00631L/1000:.1f} 張", color="blue")
        with col_p2:
            metric_card("成本價", f"{cost_price:.2f}", delta=f"現價: {current_price_00631L:.2f}", color="blue")
        with col_p3:
            metric_card("目前市值", f"{long_market_value:,.0f}", color="blue")
        with col_p4:
            pnl_color_card = "red" if long_unrealized_pnl > 0 else "green"
            pnl_emoji = "🔴" if long_unrealized_pnl > 0 else "🟢"
            metric_card("未實現損益", f"{pnl_emoji} {long_unrealized_pnl:+,.0f}", delta=f"{long_return_pct:+.1f}%", color=pnl_color_card)
        
        # === 避險部位區塊 (僅在做空模式時顯示) ===
        if hedge_mode != "不做空 (純再平衡)":
            st.markdown("### 🛡️ 避險部位")
            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            with col_h1:
                metric_card("做空用現金", f"{short_capital:,}", color="orange")
            with col_h2:
                contract_status = f"🔴 持有 {held_contracts} 口" if held_contracts > 0 else "⚪ 無持倉"
                metric_card("避險口數", contract_status, color="orange")
            with col_h3:
                if held_contracts > 0 and hedge_entry_price > 0:
                    metric_card("進場指數", f"{hedge_entry_price:,}", delta=f"現價: {last_close:,.0f}", color="orange")
                else:
                    metric_card("進場指數", "-", color="orange")
            with col_h4:
                if held_contracts > 0:
                    hedge_pnl_color = "red" if hedge_unrealized_pnl > 0 else "green"
                    hedge_emoji = "🔴" if hedge_unrealized_pnl > 0 else "🟢"
                    metric_card("避險損益", f"{hedge_emoji} {hedge_unrealized_pnl:+,.0f}", color=hedge_pnl_color)
                else:
                    metric_card("避險損益", "-", color="orange")
        
        st.markdown("### 💰 資產總覽")
        if hedge_mode == "不做空 (純再平衡)":
            # 純再平衡模式：簡化顯示，只顯示持股市值 + 現金
            total_assets_simple = long_market_value + short_capital
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                metric_card("總資產", f"{total_assets_simple:,.0f} TWD", color="purple")
            with col_t2:
                pnl_color_card = "red" if long_unrealized_pnl > 0 else "green"
                pnl_emoji = "🔴" if long_unrealized_pnl > 0 else "🟢"
                metric_card("未實現損益", f"{pnl_emoji} {long_unrealized_pnl:+,.0f}", color=pnl_color_card)
            with col_t3:
                metric_card("現金餘額", f"{short_capital:,.0f} TWD", color="blue")
        else:
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                metric_card("總資產", f"{total_assets:,.0f} TWD", color="purple")
            with col_t2:
                total_pnl = long_unrealized_pnl + hedge_unrealized_pnl
                pnl_color_card = "red" if total_pnl > 0 else "green"
                pnl_emoji = "🔴" if total_pnl > 0 else "🟢"
                metric_card("總未實現損益", f"{pnl_emoji} {total_pnl:+,.0f}", color=pnl_color_card)
            with col_t3:
                # 曝險計算
                exposure = long_market_value * 2  # 正2的曝險
                hedged_exposure = held_contracts * last_close * 50 if held_contracts > 0 else 0
                net_exposure = exposure - hedged_exposure
                metric_card("淨曝險", f"{net_exposure:,.0f}", delta=f"避險比例: {hedged_exposure/exposure*100:.1f}%" if exposure > 0 else "", color="orange")
        
        # === 資產配置與操作建議 (合併優化版面) ===
        st.divider()
        st.markdown("### ⚖️ 資產配置分析")
        
        # 計算目前配置比例
        current_long_pct = (long_market_value / total_assets * 100) if total_assets > 0 else 0
        current_short_pct = (short_capital / total_assets * 100) if total_assets > 0 else 0
        
        # 目標配置 (使用側邊欄設定的比例)
        target_long_pct = long_alloc * 100
        target_short_pct = short_alloc * 100
        target_long_value = total_assets * long_alloc
        target_short_value = total_assets * short_alloc
        
        # 需要調整的金額
        long_diff = target_long_value - long_market_value
        short_diff = target_short_value - short_capital
        
        # 視覺化配置比例
        col_bar1, col_bar2 = st.columns([4, 1])
        with col_bar1:
            # 用 HTML 製作配置比例條
            st.markdown(f"""
            <div style="display: flex; width: 100%; height: 40px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="width: {current_long_pct}%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px;">
                    00631L {current_long_pct:.1f}%
                </div>
                <div style="width: {current_short_pct}%; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px;">
                    {current_short_pct:.1f}%
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_bar2:
            if current_short_pct < 15:
                st.markdown("🔴 **偏離**")
            elif current_short_pct < 18:
                st.markdown("🟡 **尚可**")
            else:
                st.markdown("🟢 **平衡**")
        
        # 再平衡資訊卡片
        with st.expander("📊 配置詳情與再平衡", expanded=False):
            st.caption("💡 **目前配置** = 今日實際比例（月中可能因市場波動而偏離）｜ **目標配置** = 下次再平衡應達到的比例")
            
            col_rb1, col_rb2 = st.columns(2)
            with col_rb1:
                st.markdown(f"""
                **📍 目前配置** *(今日實際)*
                | 項目 | 比例 | 金額 |
                |------|------|------|
                | 00631L | {current_long_pct:.1f}% | {long_market_value:,.0f} |
                | 做空現金 | {current_short_pct:.1f}% | {short_capital:,.0f} |
                """)
            with col_rb2:
                st.markdown(f"""
                **🎯 目標配置** *(再平衡後)*
                | 項目 | 比例 | 金額 |
                |------|------|------|
                | 00631L | {long_alloc:.0%} | {target_long_value:,.0f} |
                | 做空現金 | {short_alloc:.0%} | {target_short_value:,.0f} |
                """)
            
            # 再平衡建議
            if abs(short_diff) > 10000:
                if short_diff > 0:
                    st.warning(f"⚠️ 做空避險需增加資金 **{short_diff:,.0f} TWD** (賣出 {abs(long_diff)/current_price_00631L:,.0f} 股)")
                else:
                    st.info(f"ℹ️ 做空資金充足，可減少 {abs(short_diff):,.0f} TWD")
                
                if st.button("🔄 套用 80:20 再平衡", type="primary", use_container_width=True):
                    new_shares = int(target_long_value / current_price_00631L) if current_price_00631L > 0 else shares_00631L
                    new_short_capital = int(target_short_value)
                    new_settings = {
                        "shares_00631L": new_shares,
                        "cost_price_00631L": cost_price,
                        "short_capital": new_short_capital,
                        "held_contracts": held_contracts,
                        "hedge_entry_price": hedge_entry_price
                    }
                    save_settings(new_settings)
                    st.success(f"✅ 已更新！")
                    st.rerun()
            else:
                st.success("✅ 目前配置接近 80:20，無需調整")
        
        # === 操作建議 (卡片化) ===
        st.markdown("### 🎯 即時操作建議")
        
        effective_short_capital = short_capital
        safe_margin_factor = safe_margin if 'safe_margin' in dir() else 3.0
        sim_max_contracts = int(effective_short_capital / (safe_margin_factor * margin)) if margin > 0 else 0
        
        # 根據避險模式計算目標口數 (簡化為 2 種)
        if hedge_mode == "不做空 (純再平衡)":
            # 不做空模式: 無論多空訊號，都不建議開空單
            sim_target_contracts = 0
        elif is_bearish:
            # 做空避險模式: 計算避險需求
            sim_target_raw = int(round((long_market_value * 2) / (last_close * 50))) if last_close > 0 else 0
            sim_target_contracts = min(sim_target_raw, sim_max_contracts)
        else:
            sim_target_contracts = 0
        
        diff_contracts = sim_target_contracts - held_contracts
        
        # 單一卡片式操作建議
        if hedge_mode == "不做空 (純再平衡)":
            # 不做空模式的專屬卡片
            if is_bearish:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #1976d2;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">📊</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #1565c0;">空方訊號，但選擇不做空避險</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">純再平衡模式：持續持有 00631L，僅透過資產配置管理風險</div>
                        </div>
                    </div>
                </div>
                """
            else:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #43a047;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">🟢</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #2e7d32;">多方訊號，持續持有</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">純再平衡模式：定期調整資產配置即可</div>
                        </div>
                    </div>
                </div>
                """
        elif is_bearish:
            signal_color = "#ff6b6b"
            signal_icon = "🔴"
            signal_text = "空方訊號"
            
            if sim_max_contracts == 0:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #ff9800;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">⚠️</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #e65100;">空方訊號，但無可用資金</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">做空現金: {short_capital:,} TWD | 需要再平衡以取得避險資金</div>
                        </div>
                    </div>
                </div>
                """
            elif diff_contracts > 0:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #e53935;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">📉</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #c62828;">建議加空 {diff_contracts} 口</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">目標: {sim_target_contracts} 口 | 風險指標: {short_capital/(sim_target_contracts*margin)*100:.0f}%</div>
                        </div>
                    </div>
                </div>
                """
            elif diff_contracts < 0:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #43a047;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">📈</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #2e7d32;">建議回補 {abs(diff_contracts)} 口</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">目標: {sim_target_contracts} 口</div>
                        </div>
                    </div>
                </div>
                """
            else:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #1976d2;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">✅</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #1565c0;">維持現狀</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">持有 {held_contracts} 口空單</div>
                        </div>
                    </div>
                </div>
                """
        else:
            if held_contracts > 0:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #43a047;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">🟢</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #2e7d32;">多方訊號，建議回補 {held_contracts} 口</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">目前持有空單，但市場轉多</div>
                        </div>
                    </div>
                </div>
                """
            else:
                action_html = f"""
                <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); border-radius: 12px; padding: 20px; border-left: 4px solid #43a047;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 32px;">🟢</span>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #2e7d32;">多方訊號，無需避險</div>
                            <div style="font-size: 14px; color: #666; margin-top: 4px;">持續持有 00631L</div>
                        </div>
                    </div>
                </div>
                """
        
        st.markdown(action_html, unsafe_allow_html=True)
            
            
# --- Main Flow ---
st.sidebar.header("資料來源")
dt_src = st.sidebar.selectbox("Source", ["Yahoo Finance", "Local File"])

# 固定使用 00878 作為高股息 ETF
ETF_CODE = "00878"
ETF_DIVIDEND = DIVIDEND_00878

df_g = None
start_date, end_date = None, None

# Load Data
if dt_src == "Yahoo Finance":
    try:
        # Simple load
        d1 = yf.download("00631L.TW", start="2014-01-01", progress=False)
        d2 = yf.download("^TWII", start="2007-01-01", progress=False)  # 加權指數從2007開始下載
        if isinstance(d1.columns, pd.MultiIndex): d1.columns = d1.columns.droplevel(1)
        if isinstance(d2.columns, pd.MultiIndex): d2.columns = d2.columns.droplevel(1)
        d1 = d1[['Close']].rename(columns={'Close': '00631L'})
        d2 = d2[['Close']].rename(columns={'Close': 'TAIEX'})
        
        # Download 00878
        d3 = yf.download("00878.TW", start="2020-07-01", progress=False, auto_adjust=True)
        if isinstance(d3.columns, pd.MultiIndex): d3.columns = d3.columns.droplevel(1)
        d3 = d3[['Close']].rename(columns={'Close': '00878'})
        
        # Download 0056
        d4 = yf.download("0056.TW", start="2007-12-01", progress=False, auto_adjust=True)
        if isinstance(d4.columns, pd.MultiIndex): d4.columns = d4.columns.droplevel(1)
        d4 = d4[['Close']].rename(columns={'Close': '0056'})
        
        df_g = pd.merge(d1, d2, left_index=True, right_index=True)
        # Left join 00878 (it has shorter history)
        df_g = pd.merge(df_g, d3, left_index=True, right_index=True, how='left')
        # Left join 0056 (it has longer history)
        df_g = pd.merge(df_g, d4, left_index=True, right_index=True, how='left')
        
        # 創建動態 ETF 欄位 (用於策略)
        df_g['HIGH_DIV_ETF'] = df_g[ETF_CODE]
        
        st.sidebar.success(f"Yahoo Download OK (使用 {ETF_CODE})")
    except Exception as e:
        st.sidebar.error(f"Yahoo Error: {e}")
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
        subdir_00878 = os.path.join(subdir, file_00878) if subdir else file_00878
        
        def load_00878(filepath):
            """載入 00878.xlsx，支援無標題列格式"""
            try:
                d3 = pd.read_excel(filepath)
                # 檢查是否有標準欄位名稱
                cols_lower = [str(c).lower() for c in d3.columns]
                has_date_col = any('date' in c or '日期' in c for c in cols_lower)
                has_price_col = any('close' in c or '價' in c for c in cols_lower)
                
                if has_date_col and has_price_col:
                    # 標準格式，使用 cl 函數
                    return cl(d3, '00878')
                else:
                    # 無標題列格式：第一欄是日期，第二欄是價格
                    d3 = pd.read_excel(filepath, header=None, names=['Date', '00878'])
                    d3['Date'] = pd.to_datetime(d3['Date'])
                    d3 = d3.set_index('Date')
                    return d3
            except Exception as e:
                st.sidebar.warning(f"00878 載入失敗: {e}")
                return None
        
        if os.path.exists(file_00878):
            d3_loaded = load_00878(file_00878)
            if d3_loaded is not None:
                df_g = pd.merge(df_g, d3_loaded, left_index=True, right_index=True, how='left')
            else:
                df_g['00878'] = np.nan
        elif os.path.exists(subdir_00878):
            d3_loaded = load_00878(subdir_00878)
            if d3_loaded is not None:
                df_g = pd.merge(df_g, d3_loaded, left_index=True, right_index=True, how='left')
            else:
                df_g['00878'] = np.nan
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
                
                # 直接執行回測分析
                render_original_strategy_page(df_test_raw)

            else:
                st.info("請選擇完整的開始與結束日期")

elif df_g is not None and df_g.empty:
    st.warning("下載或讀取的資料為空，無法進行回測。")
else:
    st.info("資料載入中，請確認資料來源。")

