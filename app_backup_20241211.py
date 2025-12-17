import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import yfinance as yf
import json

# =============================================================================
# 00878 ?¡æ¯è³‡æ? (å­????
# =============================================================================
# è³‡æ?ä¾†æ?ï¼šæ­·å¹´è‚¡?©å???
# 00878 ?šå¸¸??2??5??8??11???¤æ¯
DIVIDEND_00878 = {
    # ?¼å?: 'YYYY-MM-DD': ?¡åˆ©?‘é? (????
    # 2020å¹?(ä¸Šå?å¹?
    '2020-11-17': 0.05,  # Q4
    
    # 2021å¹?
    '2021-02-22': 0.15,  # Q1
    '2021-05-18': 0.30,  # Q2
    '2021-08-17': 0.35,  # Q3
    '2021-11-16': 0.35,  # Q4
    
    # 2022å¹?
    '2022-02-17': 0.32,  # Q1
    '2022-05-17': 0.28,  # Q2
    '2022-08-16': 0.28,  # Q3
    '2022-11-16': 0.27,  # Q4
    
    # 2023å¹?
    '2023-02-17': 0.35,  # Q1
    '2023-05-17': 0.35,  # Q2
    '2023-08-16': 0.35,  # Q3
    '2023-11-16': 0.35,  # Q4
    
    # 2024å¹?
    '2024-02-27': 0.40,  # Q1
    '2024-05-17': 0.51,  # Q2
    '2024-08-16': 0.55,  # Q3
    '2024-11-18': 0.64,  # Q4
    
    # 2025å¹?
    '2025-02-18': 0.56,  # Q1
    '2025-05-16': 0.37,  # Q2 (?ä¼°)
    '2025-08-15': 0.37,  # Q3 (?ä¼°)
}

def get_dividend_00878(date_str):
    """
    ?–å??‡å??¥æ???00878 ?¡æ¯
    
    Args:
        date_str: ?¥æ?å­—ä¸² 'YYYY-MM-DD'
    
    Returns:
        ?¡æ¯?‘é? (å¦‚æ?è©²æ—¥?ºé™¤?¯æ—¥) ??0
    """
    return DIVIDEND_00878.get(date_str, 0)

st.set_page_config(page_title="?°ç£äº”å?æ­? & å°å° Backtest", layout="wide")
st.title("?°ç£äº”å?æ­? (00631L) & å°å°??ç­–ç•¥?æ¸¬å¹³å°")

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

# =============================================================================
# ç­–ç•¥1: ?Ÿè²¨?¿éšªç­–ç•¥ (00631L + å°å°?¿éšª)
# =============================================================================
# ?ç??¥é?è¼¯èªª?ã€?
# 1. ?šå??¨ä?ï¼šè²·?²ä¸¦?æ? 00631L (?°ç£50æ­?)ï¼Œç?ç­‰æ–¼ 2 ?å¤§?¤æ???
# 2. ?¿éšª?¨ä?ï¼šç•¶å¤§ç›¤è·Œç ´?‡ç??‚ï??šç©ºå°å°?Ÿè²¨ä¾†å?æ²–é¢¨??
# 3. è¨Šè??¤æ–·ï¼šæ???< MA ???šç©º?¿éšª | ?‡æ•¸ > MA ??å¹³å€‰ç©º??
# 4. ??•¸è¨ˆç?ï¼?
#    - å®Œå…¨?¿éšªæ¨¡å?ï¼šç©º?®å£??= 00631Lå¸‚å€¼Ã? / (?‡æ•¸?50)
#    - ç©æ¥µ?šç©ºæ¨¡å?ï¼šç›¡?¯èƒ½?šç©ºï¼ˆå?ä¿è??‘é??¶ï?
# 5. ?å¹³è¡¡ï?æ¯æ??æ–°èª¿æ•´?šå?/?šç©ºè³‡é?æ¯”ä?
# 
# ?å??¸èªª?ã€?
# - ma_period: ?‡ç??±æ? (å»ºè­° 10-20)
# - long_allocation_pct: ?šå?è³‡é?æ¯”ä? (ä¾‹å? 0.9 = 90% è²?00631L)
# - short_allocation_pct: ?šç©ºä¿è??‘æ?ä¾?(ä¾‹å? 0.1 = 10%)
# - margin_per_contract: å°å°ä¿è???(ç´?85,000 TWD/??
# 
# ?æ??¬è?ç®—ã€?
# - ?‹ç?è²? cost_fee (æ¯å£ï¼Œç? 40 TWD)
# - äº¤æ?ç¨? cost_tax ? ?ˆç??¹å€?(?¬å?ä¹‹ä?)
# - æ»‘åƒ¹: cost_slippage ? 50 TWD (?‡è¨­ 1 é»?
# =============================================================================
def run_backtest_original(df_data, ma_period, initial_capital, long_allocation_pct, short_allocation_pct, 
                          margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
                          cost_fee, cost_tax, cost_slippage, include_costs):
    """
    ?Ÿè²¨?¿éšªç­–ç•¥?æ¸¬
    
    Args:
        df_data: ?…å« TAIEX ??00631L ?¹æ ¼??DataFrame
        ma_period: ?‡ç??±æ?
        initial_capital: ?å?è³‡é?
        long_allocation_pct: ?šå?è³‡é?æ¯”ä?
        short_allocation_pct: ?šç©ºä¿è??‘æ?ä¾?
        margin_per_contract: æ¯å£ä¿è???
        hedge_mode: ?¿éšªæ¨¡å? ("å®Œå…¨?¿éšª" ??"ç©æ¥µ?šç©º")
        do_rebalance: ?¯å¦æ¯æ??å¹³è¡?
        rebalance_long_target: ?å¹³è¡¡ç›®æ¨™æ?ä¾?
        cost_fee: ?‹ç?è²???
        cost_tax: äº¤æ?ç¨…ç?
        cost_slippage: æ»‘åƒ¹é»æ•¸
        include_costs: ?¯å¦è¨ˆå…¥?æœ¬
    
    Returns:
        df: ?«æ??¥æ??Šç? DataFrame
        trades: äº¤æ?ç´€?„å?è¡?
        total_long_pnl: ?šå?ç¸½æ???
        total_short_pnl: ?šç©ºç¸½æ???
        total_cost: ç¸½äº¤?“æ???
    """
    df = df_data.copy()
    
    # è¨ˆç?ç§»å?å¹³å?ç·?
    df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
    
    # è¨ˆç?è¨Šè? (shift(1) ç¢ºä??¨æ˜¨å¤©è??Ÿäº¤?“ä?å¤?
    # Position = 1 è¡¨ç¤º?€è¦é¿??(?‡æ•¸ä½æ–¼?‡ç?)
    df['Position'] = (df['TAIEX'] < df['MA']).shift(1).fillna(0)
    
    # ?å??–è???
    long_capital = initial_capital * long_allocation_pct    # ?šå?è³‡é?
    short_capital = initial_capital * short_allocation_pct  # ?šç©ºä¿è???
    
    long_equity_arr, short_equity_arr, total_equity_arr = [], [], []
    trades = []
    
    total_long_pnl = 0   # ?šå?ç´¯è??ç?
    total_short_pnl = 0  # ?šç©ºç´¯è??ç?
    total_cost = 0       # ç´¯è?äº¤æ??æœ¬
    
    current_short_capital = short_capital
    
    # è²·é€?00631L
    initial_price_00631L = df['00631L'].iloc[0]
    shares_00631L = long_capital / initial_price_00631L
    
    in_trade = False  # ?¯å¦?æ?ç©ºå–®
    entry_date, entry_price, entry_capital, entry_long_equity = None, 0, 0, 0
    last_month = df.index[0].month
    
    for i in range(len(df)):
        date = df.index[i]
        price_00631L = df['00631L'].iloc[i]
        price_taiex = df['TAIEX'].iloc[i]
        position = df['Position'].iloc[i]
        
        # è¨ˆç??¶æ—¥?šå?å¸‚å€?
        long_equity = shares_00631L * price_00631L
        
        # è¨ˆç?æ¯æ—¥?ç?
        if i > 0:
            prev_price = df['00631L'].iloc[i-1]
            # ?šå??ç? = ?¡æ•¸ ? ?¹å·®
            total_long_pnl += shares_00631L * (price_00631L - prev_price)
            
            prev_taiex = df['TAIEX'].iloc[i-1]
            
            # å¦‚æ??æ?ç©ºå–®ï¼Œè?ç®—ç©º?®æ???
            if position == 1:
                safe_margin = 3.0  # å®‰å…¨ä¿è??‘å€æ•¸
                max_contracts = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
                
                if hedge_mode == "å®Œå…¨?¿éšª (Neutral Hedge)":
                    # ?ä¿®æ­?€‘ä½¿?¨ç•¶?¥åƒ¹?¼è?ç®—ç›®æ¨™å£?¸ï??Œé??¨æ—¥?¹æ ¼
                    tg_notional = long_equity * 2  # ?®æ??ç¾©?‘é? = 00631Lå¸‚å€?? 2 (? ç‚ºæ­?)
                    tg_contracts = int(round(tg_notional / (price_taiex * 50)))  # ä¿®æ­£ï¼šä½¿?¨ç•¶?¥åƒ¹??
                    actual_contracts = min(tg_contracts, max_contracts)
                else:
                    actual_contracts = max_contracts
                
                # ç©ºå–®?ç? = ??•¸ ? é»å·® ? 50 ? (-1) (?šç©ºè³ºéŒ¢?¹å??¸å?)
                diff = price_taiex - prev_taiex
                short_pnl = actual_contracts * diff * 50 * (-1)
                current_short_capital += short_pnl
                total_short_pnl += short_pnl
        
        # è¨Šè?è®Šå??‚è??†é€²å‡º??
        prev_pos = df['Position'].iloc[i-1] if i > 0 else 0
        if position != prev_pos:
            safe_margin = 3.0
            max_c = int(current_short_capital / (safe_margin * margin_per_contract)) if margin_per_contract > 0 else 0
            
            if hedge_mode == "å®Œå…¨?¿éšª (Neutral Hedge)":
                tg_c = int(round((long_equity * 2) / (price_taiex * 50)))
                act_c = min(tg_c, max_c)
            else:
                act_c = max_c
            
            # è¨ˆç?äº¤æ??æœ¬
            contracts = act_c
            if contracts > 0 and include_costs:
                fee = contracts * cost_fee                    # ?‹ç?è²?
                tax = price_taiex * 50 * contracts * cost_tax # äº¤æ?ç¨?
                slip = contracts * cost_slippage * 50         # æ»‘åƒ¹
                tc = fee + tax + slip
                current_short_capital -= tc
                total_cost += tc
            
            # è¨˜é?äº¤æ?
            if position == 1 and not in_trade:
                # ?‹ç©º??
                in_trade = True
                entry_date = date
                entry_price = price_taiex
                entry_capital = current_short_capital
                entry_long_equity = long_equity
                
            elif position == 0 and in_trade:
                # å¹³å€‰ç©º??
                in_trade = False
                exit_price = price_taiex
                pts = entry_price - exit_price  # è³ºç?é»æ•¸ (?²å ´-?ºå ´ï¼Œå??ºå?ç©?
                
                # è¨ˆç?å¯¦é?äº¤æ?ç¸¾æ?
                max_ce = int(entry_capital / (3.0 * margin_per_contract)) if margin_per_contract > 0 else 0
                if hedge_mode == "å®Œå…¨?¿éšª (Neutral Hedge)":
                    tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
                    act_ce = min(tg_ce, max_ce)
                else:
                    act_ce = max_ce
                
                prof_twd = pts * 50 * act_ce  # ?²åˆ©?‘é?
                entry_notional = act_ce * entry_price * 50
                eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
                ret = (entry_price - exit_price) / entry_price
                
                trades.append({
                    '?²å ´?¥æ?': entry_date, '?²å ´?‡æ•¸': entry_price,
                    '?ºå ´?¥æ?': date, '?ºå ´?‡æ•¸': exit_price,
                    '?¿éšª??•¸': act_ce, '?²åˆ©é»æ•¸': pts,
                    '?²åˆ©?‘é? (TWD)': prof_twd, '?±é…¬??: ret * eff_lev
                })

        short_equity = current_short_capital
        total_equity = long_equity + short_equity
        
        # æ¯æ??å¹³è¡?
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
        
    # ?•ç??ªå¹³?‰éƒ¨ä½?
    if in_trade:
        now_price = df['TAIEX'].iloc[-1]
        pts = entry_price - now_price
        
        max_ce = int(entry_capital / (3.0 * margin_per_contract)) if margin_per_contract > 0 else 0
        if hedge_mode == "å®Œå…¨?¿éšª (Neutral Hedge)":
            tg_ce = int(round((entry_long_equity * 2) / (entry_price * 50)))
            act_ce = min(tg_ce, max_ce)
        else:
            act_ce = max_ce
        
        prof_twd = pts * 50 * act_ce
        entry_notional = act_ce * entry_price * 50
        eff_lev = entry_notional / entry_capital if entry_capital > 0 else 0
        ret = (entry_price - now_price) / entry_price
        
        trades.append({
            '?²å ´?¥æ?': entry_date, '?²å ´?‡æ•¸': entry_price,
            '?ºå ´?¥æ?': df.index[-1], '?ºå ´?‡æ•¸': now_price,
            '?¿éšª??•¸': act_ce, '?²åˆ©é»æ•¸': pts,
            '?²åˆ©?‘é? (TWD)': prof_twd, '?±é…¬??: ret * eff_lev, '?™è¨»': '?å€‰ä¸­'
        })
        
    df['Long_Equity'] = long_equity_arr
    df['Short_Equity'] = short_equity_arr
    df['Total_Equity'] = total_equity_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, trades, total_long_pnl, total_short_pnl, total_cost

# =============================================================================
# ç­–ç•¥2: è³‡ç”¢å¹³è¡¡ç­–ç•¥ (00631L + ?¾é?å®šæ??å¹³è¡?
# =============================================================================
# ?ç??¥é?è¼¯èªª?ã€?
# 1. å°‡è??‘å??ç‚º X% 00631L + (100-X)% ?¾é?
# 2. æ¯æ??æª¢?¥é?ç½®æ?ä¾‹ï??¥å??¢ç›®æ¨™å??å¹³è¡?
# 3. ?å¹³è¡¡é?è¼¯ï?è³??è²·ä?ï¼Œç¶­?ç›®æ¨™é?ç½?
# 
# ?å„ªé»ã€?
# - ?ªå?è³??è²·ä?ï¼Œé?ä½è¿½æ¼²æ®ºè·Œé¢¨??
# - ä¿ç??¾é?ç·©è?ï¼Œé?ä½æ•´é«”æ³¢??
# 
# ?ç¼ºé»ã€?
# - å¤šé ­å¸‚å ´ä¸­ç¾?‘éƒ¨ä½æ?ç´¯è¡¨??
# - æ¯æ¬¡?å¹³è¡¡é?ä»˜äº¤?“æ???
# 
# ?æ??¬è?ç®—ã€?
# - ?¡ç¥¨?‹ç?è²? 0.1425% ? 0.6 (?˜æ‰£å¾? 
# - è­‰äº¤ç¨? 0.1% (è³?‡º??
# =============================================================================
def run_backtest_rebalance(df_data, initial_capital, target_00631_pct):
    """
    è³‡ç”¢å¹³è¡¡ç­–ç•¥?æ¸¬
    
    Args:
        df_data: ?…å« 00631L ?¹æ ¼??DataFrame
        initial_capital: ?å?è³‡é?
        target_00631_pct: ?®æ? 00631L ?ç½®æ¯”ä? (0.0-1.0)
    
    Returns:
        df: ?«æ??¥æ??Šç? DataFrame
        log: ?å¹³è¡¡ç???
        total_cost: ç¸½äº¤?“æ???
    """
    df = df_data.copy()
    
    # ?å??ç½®
    cash = initial_capital * (1 - target_00631_pct)     # ?¾é??¨ä?
    alloc_00631 = initial_capital * target_00631_pct   # ?¡ç¥¨?¨ä?
    shares = alloc_00631 / df['00631L'].iloc[0]        # ?¡æ•¸
    
    # ?æœ¬?ƒæ•¸ (?ä¿®æ­?€‘æ­£ç¢ºè?ç®—æ???
    # ?‹ç?è²?0.1425% ? 0.6 ?˜æ‰£ + è­‰äº¤ç¨?0.1% (è³?‡º)
    buy_cost_rate = 0.001425 * 0.6         # è²·å…¥?æœ¬ (?ªæ??‹ç?è²?
    sell_cost_rate = 0.001425 * 0.6 + 0.001  # è³?‡º?æœ¬ (?‹ç?è²?+ è­‰äº¤ç¨?
    
    eq_arr, cash_arr = [], []
    log = []
    last_month = df.index[0].month
    total_cost_accum = 0  # ?ä¿®æ­?€‘è¿½è¹¤ç´¯ç©æ???
    
    # è¨˜é??å?å»ºå€?
    initial_cost = alloc_00631 * buy_cost_rate
    total_cost_accum += initial_cost
    
    log.append({
        '?¥æ?': df.index[0].strftime('%Y-%m-%d'),
        '?•ä?': 'å»ºå€?,
        '?äº¤??: f"{df['00631L'].iloc[0]:.2f}",
        '?¡æ•¸è®Šå?': int(shares),
        '?æ??¡æ•¸': int(shares),
        '?¾é?é¤˜é?': int(cash),
        'ç¸½è???: int(initial_capital),
        'äº¤æ??æœ¬': int(initial_cost)  # ?ä¿®æ­?€‘å??¥æ??¬æ?ä½?
    })
    
    for i in range(len(df)):
        price = df['00631L'].iloc[i]
        val = shares * price  # ?¡ç¥¨å¸‚å€?
        tot = val + cash      # ç¸½è???
        
        curr_month = df.index[i].month
        
        # æ¯æ??æª¢?¥æ˜¯?¦é?è¦å?å¹³è¡¡
        if i > 0 and curr_month != last_month:
            tgt_val = tot * target_00631_pct  # ?®æ??¡ç¥¨å¸‚å€?
            diff = tgt_val - val              # å·®é?
            
            # ?ªæ?å·®é?è¶…é? 1000 ?åŸ·è¡Œå?å¹³è¡¡ (?¿å??åº¦äº¤æ?)
            if abs(diff) > 1000:
                # ?ä¿®æ­?€‘æ ¹?šè²·??è³?‡º?†åˆ¥è¨ˆç??æœ¬
                if diff > 0:
                    # è²·å…¥?¡ç¥¨
                    cost = abs(diff) * buy_cost_rate
                else:
                    # è³?‡º?¡ç¥¨
                    cost = abs(diff) * sell_cost_rate
                
                shares_diff = diff / price
                shares += shares_diff
                cash -= (diff + cost)
                total_cost_accum += cost  # ?ä¿®æ­?€‘ç´¯è¨ˆæ???
                
                log.append({
                    '?¥æ?': df.index[i].strftime('%Y-%m-%d'),
                    '?•ä?': '?å¹³è¡?(è²?' if diff > 0 else '?å¹³è¡?(è³?',
                    '?äº¤??: f"{price:.2f}",
                    '?¡æ•¸è®Šå?': int(shares_diff),
                    '?æ??¡æ•¸': int(shares),
                    '?¾é?é¤˜é?': int(cash),
                    'ç¸½è???: int(tot),
                    'äº¤æ??æœ¬': int(cost)  # ?ä¿®æ­?€‘ç??„æ?æ¬¡æ???
                })
        
        last_month = curr_month
        eq_arr.append(shares * price + cash)
        cash_arr.append(cash)
        
    df['Total_Equity'] = eq_arr
    df['Cash'] = cash_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    # ?ä¿®æ­?€‘æ­£ç¢ºå??³ç´¯ç©æ???
    return df, pd.DataFrame(log), total_cost_accum

# =============================================================================
# ç­–ç•¥3: ç´”æ?è²¨ç???(?šå?/è¶¨å‹¢/æ³¢æ®µ)
# =============================================================================
# ?ç??¥é?è¼¯èªª?ã€?
# 1. Long-Only (ç´”å?å¤?ï¼šæ°¸? å?å¤šæ?è²¨ï?äº«å?æ§“æ¡¿?ˆæ?
# 2. Trend (è¶¨å‹¢)ï¼šæ???> MA ?šå?ï¼Œæ???< MA ?šç©º
# 3. Long-MA (æ³¢æ®µ?šå?)ï¼šæ???> MA ?šå?ï¼Œæ???< MA ç©ºæ?
# 
# ?é€†åƒ¹å·?æ®–åˆ©?‡èªª?ã€?
# - ?°æ??Ÿå??æ??¡æ¯ï¼Œé€šå¸¸?ˆç¾?Œé€†åƒ¹å·®ã€??Ÿè²¨ä½æ–¼?¾è²¨)
# - ?šå??Ÿè²¨ï¼šéš¨?—åˆ°?Ÿæ—¥?¥è?ï¼Œæ??Œæ”¶?‚ã€è³º?–éš±?«æ”¶??
# - ?šç©º?Ÿè²¨ï¼šé??Œæ”¯ä»˜ã€é€†åƒ¹å·®æ???(å¯¦é?ä¸Šæ˜¯?±åƒ¹è¼ƒä?ï¼Œç?ç®—æ??§éŒ¢)
# - å¹´å?ç´?4% (ä¾å??´ç?æ³è???
# 
# ?ä¿®æ­???®ã€?
# - ?šç©º?‚é€†åƒ¹å·®ç‚º?æœ¬ (ä¸æ˜¯?¶ç?)
# - å¢å?èª¿æ•´?€æª»ï??¿å?æ¯æ—¥å¾®èª¿? æ??åº¦äº¤æ?
# 
# ?æ??¬è?ç®—ã€?
# - ?‹ç?è²? cost_fee (ç´?40 TWD/??
# - äº¤æ?ç¨? cost_tax ? ?ˆç??¹å€?
# - æ»‘åƒ¹: cost_slippage ? 50 TWD
# =============================================================================
def run_backtest_futures_simple(df_data, initial_capital, leverage, mode, ma_period, 
                                 dividend_yield=0.04, cost_fee=40, cost_tax=2e-5, 
                                 cost_slippage=1, ignore_short_yield=False,
                                 adjustment_threshold=0.1):  # ?æ–°å¢ã€‘èª¿?´é?æª»å???
    """
    ç´”æ?è²¨ç??¥å?æ¸?
    
    Args:
        df_data: ?…å« TAIEX ??00631L ?¹æ ¼??DataFrame
        initial_capital: ?å?è³‡é?
        leverage: æ§“æ¡¿?æ•¸
        mode: ç­–ç•¥æ¨¡å? ('Long-Only', 'Trend', 'Long-MA')
        ma_period: ?‡ç??±æ?
        dividend_yield: å¹´å??†åƒ¹å·®ç? (?è¨­ 4%)
        cost_fee: ?‹ç?è²???
        cost_tax: äº¤æ?ç¨…ç?
        cost_slippage: æ»‘åƒ¹é»æ•¸
        ignore_short_yield: ?šç©º?‚æ˜¯?¦å¿½?¥æ??©ç??æœ¬ (æ¸¬è©¦??
        adjustment_threshold: èª¿æ•´?€æª?(0.1 = ??•¸?å·®è¶…é? 10% ?èª¿??
    
    Returns:
        df: ?«æ??¥æ??Šç? DataFrame
        log: äº¤æ?ç´€??
        total_cost: ç¸½äº¤?“æ???
    """
    df = df_data.copy()
    
    # è¨ˆç?è¨Šè?
    if mode == 'Trend':
        # è¶¨å‹¢ç­–ç•¥ï¼šæ???> MA ?šå?(+1)ï¼Œæ???< MA ?šç©º(-1)
        df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
        df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, -1)
        df['Signal'] = df['Signal'].shift(1).fillna(0)  # ?¨æ˜¨å¤©è??Ÿäº¤?“ä?å¤?
        
    elif mode == 'Long-MA':
        # æ³¢æ®µ?šå?ç­–ç•¥ï¼šæ???> MA ?šå?(+1)ï¼Œæ???< MA ç©ºæ?(0)
        df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
        df['Signal'] = np.where(df['TAIEX'] > df['MA'], 1, 0)
        df['Signal'] = df['Signal'].shift(1).fillna(0)
        
    else:
        # ç´”å?å¤šç??¥ï?æ°¸é??šå?
        df['Signal'] = 1
        
    # ?å??–è???
    cash = initial_capital           # æ¬Šç? (?«å·²å¯¦ç¾?ç?)
    held_contracts = 0               # ?®å??æ???•¸
    
    cash_arr = []                    # æ¯æ—¥æ¬Šç?ç´€??
    log = []                         # äº¤æ?ç´€??
    total_cost_accum = 0             # ç´¯è?äº¤æ??æœ¬
    
    # ?¥å?æ®–åˆ©??
    daily_yield_rate = dividend_yield / 252.0
    
    avg_entry = 0  # å¹³å??²å ´?æœ¬
    
    for i in range(len(df)):
        price = df['TAIEX'].iloc[i]
        date = df.index[i]
        signal = df['Signal'].iloc[i]
        
        # ============================================================
        # æ­¥é?1: è¨ˆç??¨æ—¥?å€‰ç??ç?
        # ============================================================
        if i > 0:
            prev_price = df['TAIEX'].iloc[i-1]
            
            # ?¹å·®?ç?
            price_pnl = (price - prev_price) * held_contracts * 50
            
            # ?†åƒ¹å·®æ???
            # ?ä¿®æ­?€‘å?ç©ºæ??†åƒ¹å·®æ˜¯?æœ¬ï¼Œä??¯æ”¶??
            yield_points = prev_price * daily_yield_rate
            if held_contracts > 0:
                # ?šå?ï¼šè³º?–é€†åƒ¹å·®æ”¶??
                yield_pnl = held_contracts * yield_points * 50
            elif held_contracts < 0:
                # ?ä¿®æ­?€‘å?ç©ºï??¯ä??†åƒ¹å·®æ???(è² ç?)
                if ignore_short_yield:
                    yield_pnl = 0  # æ¸¬è©¦æ¨¡å?ï¼šå¿½?¥æ­¤?æœ¬
                else:
                    yield_pnl = held_contracts * yield_points * 50  # è² å£??? æ­?”¶??= è² æ???
            else:
                yield_pnl = 0
            
            total_pnl = price_pnl + yield_pnl
            cash += total_pnl
            
        # ============================================================
        # æ­¥é?2: è¨ˆç??®æ???•¸
        # ============================================================
        target_contracts = 0
        
        if mode == 'Long-Only':
            target_notional = cash * leverage
            target_contracts = int(round(target_notional / (price * 50)))
            
        elif mode == 'Trend' or mode == 'Long-MA':
            if signal == 1:      # ?šå?è¨Šè?
                target_notional = cash * leverage
                target_contracts = int(round(target_notional / (price * 50)))
            elif signal == -1:   # ?šç©ºè¨Šè?
                target_notional = cash * leverage
                target_contracts = -int(round(target_notional / (price * 50)))
            else:                # ç©ºæ?è¨Šè?
                target_contracts = 0
        
        # ============================================================
        # æ­¥é?3: ?¤æ–·?¯å¦?€è¦èª¿?´éƒ¨ä½?
        # ============================================================
        # ?æ–°å¢ã€‘èª¿?´é?æª»é?è¼¯ï??¿å??åº¦äº¤æ?
        need_adjust = False
        
        if held_contracts == 0 and target_contracts != 0:
            # å¾ç©º?‹åˆ°?‰éƒ¨ä½???å¿…é?èª¿æ•´
            need_adjust = True
        elif target_contracts == 0 and held_contracts != 0:
            # å¾æ??¨ä??°ç©º????å¿…é?èª¿æ•´
            need_adjust = True
        elif held_contracts != 0 and target_contracts != 0:
            # ?Œæ–¹?‘ä???•¸ä¸å?
            if held_contracts * target_contracts < 0:
                # ?æ? ??å¿…é?èª¿æ•´
                need_adjust = True
            else:
                # ?Œæ–¹?‘ï?æª¢æŸ¥?å·®?¯å¦è¶…é??€æª?
                deviation = abs(target_contracts - held_contracts) / abs(held_contracts)
                if deviation > adjustment_threshold:
                    need_adjust = True
        
        # ============================================================
        # æ­¥é?4: ?·è?äº¤æ?
        # ============================================================
        if need_adjust:
            diff = target_contracts - held_contracts
            
            # è¨ˆç?äº¤æ??æœ¬
            cost = abs(diff) * (cost_fee + cost_tax * price * 50 + cost_slippage * 50)
            cash -= cost
            total_cost_accum += cost
            
            # è¨ˆç?å·²å¯¦?¾æ???(?¨æ–¼ log)
            realized_pnl = 0
            if held_contracts != 0:
                if held_contracts * target_contracts < 0:  # ?æ?
                    closed_qty = abs(held_contracts)
                elif target_contracts == 0:  # ?¨éƒ¨å¹³å€?
                    closed_qty = abs(held_contracts)
                elif abs(target_contracts) < abs(held_contracts):  # æ¸›ç¢¼
                    closed_qty = abs(diff)
                else:
                    closed_qty = 0
                
                if closed_qty > 0:
                    direction = 1 if held_contracts > 0 else -1
                    realized_pnl = (price - avg_entry) * closed_qty * 50 * direction
            
            # ?´æ–°å¹³å??æœ¬
            if target_contracts != 0:
                if held_contracts == 0 or (held_contracts * target_contracts < 0):
                    avg_entry = price  # ?°å»º?‰æ??æ?
                elif abs(target_contracts) > abs(held_contracts):
                    # ? ç¢¼ï¼šå?æ¬Šå¹³?‡æ???
                    old_vol = abs(held_contracts)
                    added_vol = abs(diff)
                    avg_entry = (old_vol * avg_entry + added_vol * price) / (old_vol + added_vol)
            
            # ?´æ–°?å€?
            prev_contracts = held_contracts
            held_contracts = target_contracts
            
            # æ±ºå??•ä?æ¨™ç±¤
            if prev_contracts == 0:
                action = '?°å€?(å¤?' if target_contracts > 0 else '?°å€?(ç©?'
            elif target_contracts == 0:
                action = 'å¹³å€?
            elif prev_contracts * target_contracts < 0:
                action = '?æ? (å¤?' if target_contracts > 0 else '?æ? (ç©?'
            elif abs(target_contracts) > abs(prev_contracts):
                action = '? ç¢¼ (å¤?' if target_contracts > 0 else '? ç¢¼ (ç©?'
            else:
                action = 'æ¸›ç¢¼ (å¤?' if target_contracts > 0 else 'æ¸›ç¢¼ (ç©?'
            
            log.append({
                '?¥æ?': date.strftime('%Y-%m-%d'),
                '?•ä?': action,
                '?‡æ•¸': int(price),
                '?®æ???•¸': int(target_contracts),
                'è®Šå???•¸': int(diff),
                '?äº¤?‡åƒ¹': int(price),
                '?æ??æœ¬': int(avg_entry),
                'äº¤æ??æœ¬': int(cost),
                '?¬ç??ç?': int(realized_pnl) if realized_pnl != 0 else 0,
                'å¸³æˆ¶æ¬Šç?': int(cash)
            })
            
        cash_arr.append(cash)
        
    df['Total_Equity'] = cash_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, pd.DataFrame(log), total_cost_accum


# =============================================================================
# ç­–ç•¥4: ?Ÿè²¨ + 00878 ç­–ç•¥
# =============================================================================
# ?ç??¥é?è¼¯èªª?ã€?
# 1. ?¨æ?è²¨é??æ?æ¡¿æ???(ä¾‹å? 2 ?å¤§??
# 2. ?Ÿè²¨?ªé?å°‘é?ä¿è??‘ï??©é?è³‡é?è²·å…¥ 00878 (é«˜è‚¡??ETF)
# 3. æ¯æ??å¹³è¡¡ï?ç¶­æ??®æ?æ§“æ¡¿?Œé¢¨?ªæ?æ¨?
# 
# ?è??‘é?ç½®é?è¼¯ã€?
# - ?Ÿè²¨ä¿è??‘ï?ç´?85,000 TWD/??
# - é¢¨éšª?‡æ?ï¼šä??™ä?è­‰é???300% ?¾é? (?¿å?è¿½ç¹³)
# - ?©é?è³‡é?ï¼šè²·??00878 è³ºå??¡æ¯
# 
# ?å„ªé»ã€?
# - ?Œæ?äº«å?æ§“æ¡¿?±é…¬ + ?¡æ¯?¶å…¥
# - ?©ç”¨?Ÿè²¨?†åƒ¹å·®é?å¤–ç²??
# 
# ?ç¼ºé»?é¢¨éšª??
# - ?™é?é¢¨éšªï¼šæ?è²¨è™§??+ 00878 ?¹æ ¼ä¸‹è?
# - ä¿è??‘è¿½ç¹³é¢¨??
# - æ³¨æ?ï¼šç›®?æœªè¨ˆå…¥ 00878 ?¡æ¯
# =============================================================================
def run_backtest_futures_00878(df_data, initial_capital, leverage, margin_per_contract, target_risk_ratio=3.0, dividend_yield=0.04):
    """
    ?Ÿè²¨ + 00878 ç­–ç•¥?æ¸¬
    
    Args:
        df_data: ?…å« TAIEX ??00878 ?¹æ ¼??DataFrame
        initial_capital: ?å?è³‡é?
        leverage: ?Ÿè²¨æ§“æ¡¿?æ•¸ (1.0-4.0)
        margin_per_contract: æ¯å£ä¿è???(ç´?85,000 TWD)
        target_risk_ratio: é¢¨éšª?‡æ? (3.0 = ä¿ç? 300% ä¿è???
        dividend_yield: å¹´å??†åƒ¹å·®ç?
    
    Returns:
        df: ?«æ??¥æ??Šç? DataFrame
        rebalance_log: ?å¹³è¡¡ç???
        total_cost: ç¸½äº¤?“æ???
    """
    df = df_data.copy()
    
    # ?å??–è???
    equity = initial_capital
    cash = initial_capital
    shares_00878 = 0
    held_contracts = 0
    
    equity_arr = []
    cash_arr = []
    held_00878_val_arr = []
    rebalance_log = []
    total_cost_accum = 0
    
    last_month = df.index[0].month
    daily_yield_rate = dividend_yield / 252.0
    
    # ?æœ¬?ƒæ•¸
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
            yield_points = prev_taiex * daily_yield_rate
            yield_pnl = held_contracts * yield_points * 50
            
            fut_pnl = price_pnl + yield_pnl
            
            # 00878 PnL (?¹å·®)
            if shares_00878 > 0 and not pd.isna(price_00878) and not pd.isna(prev_00878):
                stock_pnl = shares_00878 * (price_00878 - prev_00878)
            else:
                stock_pnl = 0
            
            # ?æ–°å¢ã€?0878 ?¡æ¯?¶å…¥
            date_str = date.strftime('%Y-%m-%d')
            dividend_per_share = get_dividend_00878(date_str)
            if dividend_per_share > 0 and shares_00878 > 0:
                dividend_income = shares_00878 * dividend_per_share
                cash += dividend_income  # ?¡æ¯?¥å¸³?°ç¾??
                rebalance_log.append({
                    '?¥æ?': date_str,
                    'ç¸½è???: int(total_equity if 'total_equity' in dir() else equity),
                    '? æ??‡æ•¸': int(price_taiex),
                    '?®æ??éšª': 0,
                    '?Ÿè²¨??•¸': int(held_contracts),
                    '?Ÿè²¨è®Šå?': 0,
                    'ä¿ç??¾é?(?Ÿè²¨)': int(cash),
                    '00878?¡åƒ¹': f"{price_00878:.2f}" if not pd.isna(price_00878) else "N/A",
                    '00878?¡æ•¸': int(shares_00878),
                    '00878è®Šå?': 0,
                    '?™è¨»': f"?¡æ¯?¥å¸³ ${dividend_per_share:.2f}/?¡ï???${dividend_income:,.0f}"
                })
                
            equity += (fut_pnl + stock_pnl)
            cash += fut_pnl  # Futures PnL settles to cash
            
        # Recalculate Equity based on components
        current_00878_val = shares_00878 * price_00878 if (shares_00878 > 0 and not pd.isna(price_00878)) else 0
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
                note = "è³‡é?ä¸è¶³(?æ?æ¡?"
            else:
                # We have enough for margin.
                if total_equity < target_futures_cash:
                    # Not enough for 300% risk, but enough for margin.
                    # Put all in cash to be safe(r).
                    target_futures_cash = total_equity
                    target_00878_val = 0
                    note = "é¢¨éšª?‡æ?ä¸è¶³(?¨ç¾??"
                else:
                    # We have excess.
                    target_00878_val = total_equity - target_futures_cash
                    note = "æ­?¸¸å¹³è¡¡"
            
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
                '?¥æ?': date.strftime('%Y-%m-%d'),
                'ç¸½è???: int(total_equity),
                '? æ??‡æ•¸': int(price_taiex),
                '?®æ??éšª': int(target_notional),
                '?Ÿè²¨??•¸': int(held_contracts),
                '?Ÿè²¨è®Šå?': int(held_contracts - prev_contracts),
                'ä¿ç??¾é?(?Ÿè²¨)': int(cash),
                '00878?¡åƒ¹': f"{price_00878:.2f}" if not pd.isna(price_00878) else "N/A",
                '00878?¡æ•¸': int(shares_00878),
                '00878è®Šå?': int(shares_00878 - prev_shares),
                '?™è¨»': note
            })
        
        last_month = curr_month
        
        equity_arr.append(total_equity)
        cash_arr.append(cash)
        held_00878_val_arr.append(shares_00878 * price_00878 if not pd.isna(price_00878) else 0)
        
    df['Total_Equity'] = equity_arr
    df['Cash_Pos'] = cash_arr
    df['Stock_Pos'] = held_00878_val_arr
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, pd.DataFrame(rebalance_log), total_cost_accum


# --- 6. Pure 00878 Buy & Hold ---
def run_backtest_00878_only(df_data, initial_capital):
    df = df_data.copy()
    
    # Find first valid date for 00878
    first_valid_idx = df['00878'].first_valid_index()
    
    equity_arr = []
    log = []
    
    shares = 0
    cash = initial_capital
    has_bought = False
    total_cost_accum = 0
    
    for i in range(len(df)):
        date = df.index[i]
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
                '?¥æ?': date.strftime('%Y-%m-%d'),
                '?•ä?': 'è²·é€²æ???,
                '?¹æ ¼': f"{price:.2f}",
                '?¡æ•¸': shares,
                '?æœ¬': int(cost),
                '?©é??¾é?': int(cash)
            })
            
        # Calculate Equity
        if has_bought and not pd.isna(price):
            equity = shares * price + cash
        else:
            equity = initial_capital # Still holding cash
            
        equity_arr.append(equity)
        
    df['Total_Equity'] = equity_arr
    return df, pd.DataFrame(log), total_cost_accum

def render_original_strategy_page(df):
    # This logic matches lines 530+ of the backup, restored fully
    initial_capital = st.sidebar.number_input("?å?ç¸½è???(TWD)", value=1000000, step=100000)
    
    if 'ma_period' not in st.session_state: st.session_state['ma_period'] = 13
    ma_period = st.sidebar.number_input("? æ??‡æ•¸?‡ç??±æ? (MA)", value=st.session_state['ma_period'], step=1, key='ma_input_orig')
    if ma_period != st.session_state['ma_period']: st.session_state['ma_period'] = ma_period
    
    st.sidebar.subheader("è³‡é??†é??‡ç???)
    do_rebalance = st.sidebar.checkbox("?Ÿç”¨æ¯æ??•æ?å¹³è¡¡", value=True)
    if do_rebalance:
        rebalance_long_target = st.sidebar.slider("?•æ?å¹³è¡¡ï¼šå?å¤šéƒ¨ä½ç›®æ¨™æ?ä¾?(%)", 10, 100, 90, 5) / 100.0
        long_alloc = rebalance_long_target
    else:
        rebalance_long_target, long_alloc = 0.5, 0.5
        
    short_alloc = 1 - long_alloc
    st.sidebar.write(f"?å??šå?: {long_alloc:.0%} | ?å??šç©º: {short_alloc:.0%}")
    
    margin = st.sidebar.number_input("å°å°ä¿è???, 85000, step=1000)
    hedge_mode = st.sidebar.radio("?¿éšªæ¨¡å?", ("ç©æ¥µ?šç©º", "å®Œå…¨?¿éšª (Neutral Hedge)"), index=1)
    
    st.sidebar.subheader("äº¤æ??æœ¬è¨­å?")
    fee = st.sidebar.number_input("?‹ç?è²?, 40)
    tax = st.sidebar.number_input("äº¤æ?ç¨?, 0.00002, format="%.5f")
    slip = st.sidebar.number_input("æ»‘åƒ¹", 1)
    inc_cost = st.sidebar.checkbox("è¨ˆå…¥?æœ¬", True)
    
    # Run
    df_res, trades, lp, sp, cost = run_backtest_original(
        df, ma_period, initial_capital, long_alloc, short_alloc, margin,
        hedge_mode, do_rebalance, rebalance_long_target, fee, tax, slip, inc_cost
    )
    
    # Tabs - Restoring ALL 7 Tabs
    # Tabs - Restoring ALL Tabs + New Comparison Tab
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["?? ç¸½è¦½", "?? ç¸¾æ??†æ?", "?? ?±æ??†æ?", "?? äº¤æ??ç´°", "?”­ ?€?°è??Ÿåˆ¤??, "?¯ ?ƒæ•¸?æ?åº?, "?® ?Ÿå¯¦?ä?æ¨¡æ“¬", "?”ï? ç­–ç•¥ç¶œå?æ¯”è?"])
    
    with t1:
        st.subheader("?æ¸¬çµæ?ç¸½è¦½")
        
        fin = df_res['Total_Equity'].iloc[-1]
        ret = (fin - initial_capital) / initial_capital
        
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("?Ÿæœ«ç¸½è???, f"{fin:,.0f}")
        with c2: metric_card("ç¸½å ±?¬ç?", f"{ret:.2%}", delta=f"{ret:.2%}")
        with c3: metric_card("äº¤æ?å¤©æ•¸", f"{len(df_res)}")
        
        c4, c5, c6 = st.columns(3)
        with c4: metric_card("?šç?ç¸½ç²??, f"{lp:,.0f}", delta=f"{lp/initial_capital:.1%}")
        with c5: metric_card("?šç©ºç¸½ç²??, f"{sp:,.0f}", delta=f"{sp/initial_capital:.1%}")
        with c6: metric_card("ç¸½æ???, f"{cost:,.0f}", delta=f"-{cost/initial_capital:.1%}", delta_color="inverse")
        
        # Equity Curve
        st.subheader("è³‡ç”¢?²ç?")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Total_Equity'], mode='lines', name='ç¸½è???(ç­–ç•¥)', line=dict(color='#d32f2f', width=3)))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Benchmark'], mode='lines', name='Buy & Hold 00631L (å°ç…§)', line=dict(color='#9e9e9e', width=3)))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Long_Equity'], mode='lines', name='?šå??¨ä?', line=dict(width=1.5, dash='dot')))
        fig.add_trace(go.Scatter(x=df_res.index, y=df_res['Short_Equity'], mode='lines', name='?šç©º?¨ä?', line=dict(width=1.5, dash='dot')))
        
        fig.update_layout(title="ç­–ç•¥ vs. ç´”è²·?²æ???(00631L)", xaxis_title="?¥æ?", yaxis_title="?‘é? (TWD)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), template="plotly_white", height=600)
        st.plotly_chart(fig, use_container_width=True)
        
        # Trend 100
        st.subheader("?€è¿?100 ?¥å?ç©ºè¶¨?¢å???)
        dfr = df_res.iloc[-100:].copy()
        dfr['C'] = dfr['Position'].apply(lambda x: 'green' if x==1 else 'red')
        figt = go.Figure(go.Bar(x=dfr.index, y=dfr['TAIEX'], marker_color=dfr['C'], name='è¶¨å‹¢'))
        figt.update_layout(title="è¿?00?¥è¶¨??(ç´?å¤šæ–¹/ç¶?ç©ºæ–¹?¿éšª)", yaxis_range=[dfr['TAIEX'].min()*0.95, dfr['TAIEX'].max()*1.05], showlegend=False, xaxis_title="?¥æ?", yaxis_title="? æ??‡æ•¸", template="plotly_white")
        st.plotly_chart(figt, use_container_width=True)
        
    with t2:
        st.subheader("ç¸¾æ?çµ±è?")
        eq = df_res['Total_Equity']
        dd = (eq - eq.cummax()) / eq.cummax()
        mdd = dd.min()
        
        ben_eq = df_res['Benchmark']
        ben_dd = (ben_eq - ben_eq.cummax()) / ben_eq.cummax()
        ben_mdd = ben_dd.min()
        
        tr_cnt = len(trades)
        if trades:
            dft = pd.DataFrame(trades)
            win = dft['?²åˆ©?‘é? (TWD)'].gt(0).mean()
        else:
            win = 0
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("ç­–ç•¥?€å¤§å???(MDD)", f"{mdd:.2%}", delta_color="inverse")
        with c2: metric_card("å¤§ç›¤?€å¤§å???, f"{ben_mdd:.2%}", delta=f"{ben_mdd-mdd:.2%}", delta_color="inverse")
        with c3: metric_card("?šç©ºæ¬¡æ•¸", f"{tr_cnt}")
        with c4: metric_card("?šç©º?ç?", f"{win:.2%}")
        
        st.subheader("?æ’¤?²ç? (Drawdown)")
        figd = go.Figure()
        figd.add_trace(go.Scatter(x=dd.index, y=dd, fill='tozeroy', line=dict(color='red'), name='ç­–ç•¥?æ’¤'))
        figd.add_trace(go.Scatter(x=ben_dd.index, y=ben_dd, line=dict(color='gray', dash='dot'), name='00631L?æ’¤'))
        figd.update_layout(title="ç¸½è??¢å??¤å?åº?, yaxis_title="?æ’¤ %", hovermode="x unified", template="plotly_white", yaxis=dict(tickformat=".0%"))
        st.plotly_chart(figd, use_container_width=True)
        
    with t3:
        st.subheader("å¹´åº¦?±é…¬?‡è?é¢¨éšª?†æ?")
        df_res['Year'] = df_res.index.year
        yr = df_res.groupby('Year').agg({'Total_Equity':['first','last'], 'Benchmark':['first','last']})
        
        yret = pd.DataFrame()
        yret['å¹´å??±é…¬??] = (yr['Total_Equity']['last'] - yr['Total_Equity']['first']) / yr['Total_Equity']['first']
        yret['Benchmark ?±é…¬??] = (yr['Benchmark']['last'] - yr['Benchmark']['first']) / yr['Benchmark']['first']
        yret['è¶…é??±é…¬ (Alpha)'] = yret['å¹´å??±é…¬??] - yret['Benchmark ?±é…¬??]
        
        ymdd = []
        for year in yret.index:
            dy = df_res[df_res['Year'] == year]
            e = dy['Total_Equity']
            d = (e - e.cummax()) / e.cummax()
            ymdd.append(d.min())
        yret['ç­–ç•¥?€å¤§å???(MDD)'] = ymdd
        
        # Add Avg
        avg = yret.mean()
        yret.loc['å¹³å???(Avg)'] = avg
        
        def hl_avg(row):
            if row.name == 'å¹³å???(Avg)': return ['background-color: #fff8e1; color: #bf360c; font-weight: bold'] * len(row)
            return [''] * len(row)
            
        st.dataframe(yret.style.apply(hl_avg, axis=1).format("{:.2%}"), use_container_width=True)
        
        st.markdown("""
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-size: 0.9em; color: #555;">
        <b>?‡æ?èªªæ?ï¼?/b>
        <ul style="margin-bottom: 0;">
            <li><b>å¹´å??±é…¬??/b>: ç­–ç•¥?¨è©²å¹´åº¦?„ç¸½?•è??±é…¬??/li>
            <li><b>Benchmark ?±é…¬??/b>: ?®ç?è²·é€²æ???00631L ?„å¹´åº¦å ±?¬ç?</li>
            <li><b>è¶…é??±é…¬ (Alpha)</b>: ç­–ç•¥?±é…¬ - Benchmark ?±é…¬</li>
            <li><b>ç­–ç•¥?€å¤§å???(MDD)</b>: è©²å¹´åº¦è??¢æ?å¤§å??½å?åº?/li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.subheader("?ˆåº¦?±é…¬?‡å???(ç¸½è???")
        df_res['Month'] = df_res.index.to_period('M')
        m_stats = df_res.groupby('Month')['Total_Equity'].agg(['first', 'last'])
        m_stats['Ret'] = (m_stats['last'] - m_stats['first']) / m_stats['first']
        m_stats['Y'] = m_stats.index.year
        m_stats['M'] = m_stats.index.month
        piv = m_stats.pivot(index='Y', columns='M', values='Ret')
        piv.columns = [f"{i}?? for i in range(1, 13)]
        
        def c_ret(v):
            if pd.isna(v): return ''
            c = 'red' if v > 0 else 'green'
            return f'color: {c}'
            
        st.dataframe(piv.style.format("{:.2%}").map(c_ret), use_container_width=True)
        
    with t4:
        st.subheader("?? äº¤æ??ç´°")
        if trades:
            df_trades = pd.DataFrame(trades)
            # Check if columns exist before applying
            if '?²å ´?¥æ?' in df_trades.columns:
                df_trades['?²å ´?¥æ?'] = df_trades['?²å ´?¥æ?'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            if '?ºå ´?¥æ?' in df_trades.columns:
                df_trades['?ºå ´?¥æ?'] = df_trades['?ºå ´?¥æ?'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
            
            def color_pnl(val):
                if pd.isna(val) or isinstance(val, str): return ''
                color = 'red' if val > 0 else 'green'
                return f'color: {color}'
            
            # Safe styling
            st.dataframe(df_trades.style.applymap(color_pnl, subset=['?²åˆ©?‘é? (TWD)', '?±é…¬??])
                         .format({'?²å ´?‡æ•¸': '{:,.0f}', '?ºå ´?‡æ•¸': '{:,.0f}', '?¿éšª??•¸': '{:.2f}', 
                                  '?²åˆ©é»æ•¸': '{:,.0f}', '?²åˆ©?‘é? (TWD)': '{:,.0f}', '?±é…¬??: '{:.2%}'}),
                         use_container_width=True)
            
            # Annual Short P&L Summary
            st.divider()
            st.subheader("?? æ¯å¹´?šç©º?¿éšª?ç?çµ±è?")
            
            df_trades_raw = pd.DataFrame(trades)
            # Ensure '?ºå ´?¥æ?' is datetime
            if '?ºå ´?¥æ?' in df_trades_raw.columns:
                df_trades_raw['Year'] = pd.to_datetime(df_trades_raw['?ºå ´?¥æ?']).dt.year
                annual_short_pnl = df_trades_raw.groupby('Year')['?²åˆ©?‘é? (TWD)'].sum().reset_index()
                annual_short_pnl.columns = ['å¹´ä»½', '?šç©ºç¸½æ???(TWD)']
                
                # Add Trade Count per year
                annual_counts = df_trades_raw.groupby('Year').size().reset_index(name='äº¤æ?æ¬¡æ•¸')
                annual_counts.columns = ['å¹´ä»½', 'äº¤æ?æ¬¡æ•¸']
                annual_summary = pd.merge(annual_short_pnl, annual_counts, on='å¹´ä»½')
                
                # Calculate Average P&L per trade
                annual_summary['å¹³å??®ç??ç?'] = annual_summary['?šç©ºç¸½æ???(TWD)'] / annual_summary['äº¤æ?æ¬¡æ•¸']
                
                def color_annual_pnl(val):
                    color = 'red' if val > 0 else 'green'
                    return f'color: {color}'

                st.dataframe(
                    annual_summary.style.applymap(color_annual_pnl, subset=['?šç©ºç¸½æ???(TWD)', 'å¹³å??®ç??ç?'])
                    .format({'å¹´ä»½': '{:d}', '?šç©ºç¸½æ???(TWD)': '{:,.0f}', 'å¹³å??®ç??ç?': '{:,.0f}'}),
                    use_container_width=True,
                    column_config={
                        "å¹´ä»½": st.column_config.NumberColumn("å¹´ä»½", format="%d"),
                    }
                )
            
            # Export Buttons
            st.divider()
            st.subheader("?“¥ è³‡æ??¯å‡º")
            col_ex1, col_ex2 = st.columns(2)
            
            csv_trades = df_trades.to_csv(index=False).encode('utf-8-sig')
            col_ex1.download_button(
                label="ä¸‹è?äº¤æ??ç´° (CSV)",
                data=csv_trades,
                file_name='trades_record.csv',
                mime='text/csv',
            )
            
            csv_equity = df_res.to_csv().encode('utf-8-sig')
            col_ex2.download_button(
                label="ä¸‹è?æ¯æ—¥è³‡ç”¢æ¬Šç? (CSV)",
                data=csv_equity,
                file_name='daily_equity.csv',
                mime='text/csv',
            )
        else:
            st.info("?€?“å…§?¡å?ç©ºäº¤??)
            
    with t5:
        st.subheader("?”­ ?€?°å??´ç??‹è??ä?å»ºè­°")
        
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
        signal_text = "ç©ºæ–¹ (è·Œç ´?‡ç?)" if is_bearish else "å¤šæ–¹ (ç«™ä??‡ç?)"
        action_text = "? ï? ?Ÿå??¿éšª (?šç©ºå°å°)" if is_bearish else "???…æ??‰å?å¤šéƒ¨ä½?(00631L)"
        signal_color = "red" if not is_bearish else "green"
        
        st.markdown(f"""
        ### ?? è³‡æ??¥æ?ï¼š{last_date.strftime('%Y-%m-%d')}
        
        #### ?? å¸‚å ´?¸æ?
        - **? æ??‡æ•¸?¶ç›¤**ï¼š{last_close:,.0f}
        - **?‡ç? ({ma_period}MA)**ï¼š{last_ma:,.0f}
        - **ä¹–é›¢??*ï¼š{((last_close - last_ma) / last_ma):.2%}
        
        #### ?š¦ è¨Šè??¤æ–·
        - **?®å?è¶¨å‹¢**ï¼?span style="color:{signal_color};font-weight:bold;font-size:1.2em">{signal_text}</span>
        - **?ä?å»ºè­°**ï¼?span style="color:{signal_color};font-weight:bold;font-size:1.2em">{action_text}</span>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        st.subheader("?’° ?®å??¨ä??ç?è©¦ç? (?ºæ–¼?Ÿå¯¦æ¨¡æ“¬è¨­å?)")
        
        col_s1, col_s2 = st.columns(2)
        
        # 1. 00631L Status
        with col_s1:
            st.markdown("#### ?? 00631L (?šå??¨ä?)")
            
            # Use Real Settings if available
            if real_settings:
                user_shares = real_settings.get('shares_00631L', 0)
                curr_val_00631L = user_shares * last_00631L
                st.write(f"**?®å??æ??¡æ•¸**ï¼š{user_shares:,.0f} ??)
            else:
                curr_val_00631L = df_res['Long_Equity'].iloc[-1]
                st.write(f"**?®å?æ¨¡æ“¬å¸‚å€?*ï¼š{curr_val_00631L:,.0f} TWD (?æ¸¬è³‡é?)")

            st.write(f"**?®å?å¸‚å€?*ï¼š{curr_val_00631L:,.0f} TWD")
            st.write(f"**ç´„ç•¶å¤§ç›¤?éšª**ï¼š{curr_val_00631L * 2:,.0f} TWD (2?æ?æ¡?")
        
        # 2. Short Leg Status
        with col_s2:
            st.markdown("#### ?» å°å° (?šç©º?¿éšª?¨ä?)")
            
            if real_settings:
                # Real Mode
                held_contracts = real_settings.get('held_contracts', 0)
                is_holding_short = held_contracts > 0
                st.write(f"**?®å??æ???•¸**ï¼š{held_contracts} ??)
            else:
                # Sim Mode
                is_holding_short = last_row['Position'] == 1
                held_contracts = "æ¨¡æ“¬?¨ä?"

            if is_holding_short:
                st.write("**?®å??€??*ï¼šğ???æ?ç©ºå–®ä¸?)
                
                # Reason for holding short
                if last_close < last_ma:
                    diff_points = last_ma - last_close
                    st.markdown(f"?? **?æ??Ÿå?**ï¼šç›®?æ???({last_close:,.0f}) ä½æ–¼ {ma_period}MA ({last_ma:,.0f}) ??**{diff_points:,.0f}** é»?)
                    st.markdown(f"?? **å¾Œç??ä?**ï¼šç??±ç©º??)
                else:
                    diff_points = last_close - last_ma
                    st.markdown(f"? ï? **?æ??Ÿå?**ï¼šæ˜¨?¥æ”¶?¤è??´å?ç·?(?®å??‡æ•¸ {last_close:,.0f} å·²é??¼å?ç·?**{diff_points:,.0f}** é»ï?è½‰ç‚ºå¤šæ–¹è¨Šè?)")
                    st.markdown(f"?? **å¾Œç??ä?**ï¼šğ??**?‰å¹³?‰ç©º??* (è¨Šè?è½‰å?)")
                
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
                    st.markdown("#### ?–ï? ?¬æ¬¡ç©ºå–®?æ?ç¸¾æ? (?æ¸¬æ¨¡æ“¬)")
                    st.write(f"**?²å ´?¥æ?**ï¼š{entry_date.strftime('%Y-%m-%d')}")
                    st.metric("?²å ´?‡æ•¸", f"{entry_price:,.0f}")
                    st.metric("?®å??‡æ•¸", f"{last_close:,.0f}", delta=f"{last_close - entry_price:,.0f}", delta_color="inverse")
                else:
                     st.info("?Ÿå¯¦?¨ä??ç?è«‹å??ƒåˆ¸?†å ±?¹ï?æ­¤è??…æ?ä¾›ç??¥è??Ÿæ?å¼•ã€?)

            else:
                st.write("**?®å??€??*ï¼šâšª ç©ºæ? (?¡é¿??")
                st.write(f"**?æ—¥?ä??‡å?**ï¼š{'çºŒæŠ±ç©ºå–®' if is_bearish else 'ç¶­æ?ç©ºæ?'}")
        
    with t6:
        st.subheader("?¯ ?ƒæ•¸?æ?åº¦å???(MA Sensitivity)")
        
        # Date Context
        if not df.empty:
            sa_start_date = df.index.min().date()
            sa_end_date = df.index.max().date()
            sa_days = (sa_end_date - sa_start_date).days
            sa_years = sa_days / 365.25
            st.info(f"æ­¤å??½å?æ¸¬è©¦ä¸å??‡ç??±æ?å°ç??¥ç¸¾?ˆç?å½±éŸ¿?‚\n\n**?®å??æ¸¬?€??*ï¼š{sa_start_date} ~ {sa_end_date} (ç´?{sa_years:.1f} å¹?")
        
        col_sa1, col_sa2 = st.columns(2)
        ma_start = col_sa1.number_input("MA èµ·å?", value=5, step=1)
        ma_end = col_sa2.number_input("MA çµæ?", value=80, step=1)
        ma_step = st.slider("?“é? (Step)", 1, 10, 2)
        
        if st.button("?‹å??†æ?"):
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
            
            st.success(f"**?€ä½³å?ç·šå¤©?¸ï?{best_ma}**ï¼Œç´¯ç©å ±?¬ç?ï¼š{best_ret:.2%}")
            
            # Benchmark Return
            benchmark_start = df['00631L'].iloc[0]
            benchmark_end = df['00631L'].iloc[-1]
            benchmark_ret = (benchmark_end - benchmark_start) / benchmark_start
            
            st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <strong>?? ç¸¾æ?å°ç…§ï¼?/strong>
                <ul>
                    <li><strong>ç­–ç•¥?€ä½³å ±?¬ç?</strong>: {best_ret:.2%} (MA={best_ma})</li>
                    <li><strong>00631L (Buy & Hold) ?±é…¬??/strong>: {benchmark_ret:.2%}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"å¥—ç”¨?€ä½³å???(MA={best_ma})"):
                st.session_state['ma_period'] = best_ma
                st.rerun()
            
            # Visualization (Line Chart)
            st.subheader("ä¸å??‡ç?å¤©æ•¸ç´¯ç??±é…¬??)
            fig_sa_ret = go.Figure()
            fig_sa_ret.add_trace(go.Scatter(
                x=df_sa['MA'],
                y=df_sa['Return'],
                mode='lines+markers',
                name='ç´¯ç??±é…¬??,
                line=dict(width=3)
            ))
            fig_sa_ret.update_layout(
                xaxis_title="?‡ç?å¤©æ•¸", 
                yaxis_title="ç´¯ç??±é…¬??, 
                template="plotly_white",
                hovermode="x unified"
            )
            st.plotly_chart(fig_sa_ret, use_container_width=True)
            
            st.subheader("?? ç¸¾æ??ä??å???(Top 5)")
            top_5 = df_sa.sort_values('Return', ascending=False).head(5).reset_index(drop=True)
            top_5.index += 1 # Rank 1-based
            
            # Format as string percentage to ensure integer display
            top_5['Return_Str'] = top_5['Return'].apply(lambda x: f"{x:.0%}")

            st.dataframe(
                top_5[['MA', 'Return_Str']],
                use_container_width=True,
                column_config={
                    "MA": st.column_config.NumberColumn("?‡ç?å¤©æ•¸ (MA)", format="%d"),
                    "Return_Str": st.column_config.TextColumn("ç´¯ç??±é…¬??)
                }
            )
            
            st.markdown("---")
            st.markdown("""
            ### ?? ç¸½ç?ï¼šå?ä½•é¸?‡æ?ä½³å??¸ï?
            ?€ä½³ç??ƒæ•¸?šå¸¸??**?Œå ±?¬ç?é«?(é«˜å??€)??* ??**?Œå??¤é¢¨?ªä? (æ·ºæ°´?€)??* ?„äº¤?†ã€?
            *   ?¥æ??‹å??¸å ±?¬ç?æ¥µé?ï¼Œä??æ’¤ä¹Ÿæ¥µå¤§ï??¯èƒ½ä¸é©?ˆå??Ÿä?å¤ å¼·?„æ?è³‡äºº??
            *   å»ºè­°?¸æ?ä¸€??*ä½æ–¼ç©©å??„é??Ÿå?ä¸­é?**?„æ•¸?¼ï??Œä??¯æ¥µç«¯å€¼ï?ä»¥é¿?ã€Œé?åº¦æ“¬??(Overfitting)?ç?é¢¨éšª??
            """)
            
            st.success("?†æ?å®Œæ?ï¼?)
            
    with t7:
        st.subheader("?® ?Ÿå¯¦?ä?æ¨¡æ“¬ (Real-world Simulation)")
        st.info("?¨æ­¤è¼¸å…¥?¨ç›®?ç?å¯¦é?è³‡ç”¢?€æ³ï?ç³»çµ±å°‡æ ¹?šç??¥é?è¼¯æ?ä¾›æ?ä½œå»ºè­°ã€?)
        
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
            st.markdown("#### 1. è¼¸å…¥?®å?è³‡ç”¢?€æ³?)
            
            # Input Shares instead of Value
            real_shares_00631L = st.number_input("?®å? 00631L ?æ??¡æ•¸ (Shares)", value=int(default_settings["shares_00631L"]), step=1000)
            real_short_capital = st.number_input("?®å? ?Ÿè²¨ä¿è??‘å??¶é?é¡?(æ¬Šç???TWD)", value=int(default_settings["short_capital"]), step=10000)
            real_held_contracts = st.number_input("?®å? ?æ?å°å°??•¸ (ç©ºå–®)", value=int(default_settings["held_contracts"]), step=1)
            
            # Save Settings
            current_settings = {
                "shares_00631L": real_shares_00631L,
                "short_capital": real_short_capital,
                "held_contracts": real_held_contracts
            }
            if current_settings != default_settings:
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(current_settings, f)
            
            st.markdown("#### 2. ç¢ºè?å¸‚å ´?¸æ? (?è¨­?ºæ???")
            # Get last data from df_res
            last_row = df_res.iloc[-1]
            last_close_val = last_row['TAIEX']
            last_ma_val = last_row['MA']
            last_00631L_val = last_row['00631L']

            sim_last_close = st.number_input("? æ??‡æ•¸?¶ç›¤??, value=float(last_close_val), step=10.0)
            sim_ma = st.number_input(f"?®å? {ma_period}MA", value=float(last_ma_val), step=10.0)
            
            # Auto-calc Value
            sim_price_00631L = last_00631L_val 
            real_long_value = real_shares_00631L * sim_price_00631L
            st.info(f"?¹ï? 00631L ?®å??ƒè€ƒåƒ¹: {sim_price_00631L:.2f} | ?¨ç?å¸‚å€? {real_long_value:,.0f} TWD")
            
        with col_real_2:
            st.markdown("#### 3. ç­–ç•¥?‹ç?çµæ?")
            
            # Logic
            sim_is_bearish = sim_last_close < sim_ma
            sim_signal_text = "ç©ºæ–¹ (è·Œç ´?‡ç?)" if sim_is_bearish else "å¤šæ–¹ (ç«™ä??‡ç?)"
            sim_signal_color = "red" if not sim_is_bearish else "green"
            
            st.markdown(f"**?®å?è¨Šè?**ï¼?span style='color:{sim_signal_color};font-weight:bold'>{sim_signal_text}</span>", unsafe_allow_html=True)
            
            # Signal Details
            diff_points = sim_last_close - sim_ma
            if sim_is_bearish:
                st.caption(f"?? ?‡æ•¸ ({sim_last_close:,.0f}) ä½æ–¼ {ma_period}MA ({sim_ma:,.0f}) ??{abs(diff_points):,.0f} é»?)
            else:
                st.caption(f"?? ?‡æ•¸ ({sim_last_close:,.0f}) é«˜æ–¼ {ma_period}MA ({sim_ma:,.0f}) ??{abs(diff_points):,.0f} é»?)
            
            # Calculate Target Contracts
            # Risk Limit
            safe_margin_factor = 3.0
            # Use 'margin' from outer scope
            sim_max_contracts = int(real_short_capital / (safe_margin_factor * margin)) if margin > 0 else 0
            
            if sim_is_bearish:
                if hedge_mode == "å®Œå…¨?¿éšª (Neutral Hedge)":
                    sim_target_notional = real_long_value * 2
                    # Avoid divide by zero
                    if sim_last_close > 0:
                        sim_target_contracts_raw = int(round(sim_target_notional / (sim_last_close * 50)))
                    else:
                        sim_target_contracts_raw = 0
                    sim_target_contracts = min(sim_target_contracts_raw, sim_max_contracts)
                    hedge_reason = f"å°æ? 2?å???(?®æ? {sim_target_contracts_raw} ??ï¼Œå?è³‡é?/é¢¨éšª?åˆ¶"
                else: # Aggressive
                    sim_target_contracts = sim_max_contracts
                    hedge_reason = "ç©æ¥µ?šç©º (è³‡é??è¨±?€å¤§å£?¸ï?é¢¨éšª?‡æ? >= 300%)"
            else:
                sim_target_contracts = 0
                hedge_reason = "å¤šæ–¹è¶¨å‹¢ï¼Œä??€?¿éšª"
            
            # Action
            diff_contracts = sim_target_contracts - real_held_contracts
            
            if diff_contracts > 0:
                action_msg = f"?”´ ? ç©º {diff_contracts} ??
                action_desc = f"?®å??æ? {real_held_contracts} ????®æ? {sim_target_contracts} ??
            elif diff_contracts < 0:
                action_msg = f"?Ÿ¢ ?è? {abs(diff_contracts)} ??
                action_desc = f"?®å??æ? {real_held_contracts} ????®æ? {sim_target_contracts} ??
            else:
                action_msg = "??ç¶­æ??¾ç?"
                action_desc = f"?®å??æ? {real_held_contracts} ???ç¬¦å??®æ?"
            
            metric_card("å»ºè­°?ä?", action_msg, delta=f"?®æ?: {sim_target_contracts} ??({action_desc})")
            st.write(f"**ç­–ç•¥?è¼¯**ï¼š{hedge_reason}")
            
            st.divider()
            
            # Risk Preview
            st.markdown("#### ? ï? èª¿æ•´å¾Œé¢¨?ªé?ä¼?)
            sim_required_margin = sim_target_contracts * margin
            if sim_required_margin > 0:
                sim_risk_ratio = real_short_capital / sim_required_margin
            else:
                sim_risk_ratio = 999
            
            sim_risk_color = "red" if sim_risk_ratio < 3.0 else "green"
            # metric_card for Risk
            metric_card("?ä¼°é¢¨éšª?‡æ?", f"{sim_risk_ratio:.0%}", delta="?®æ? > 300%", delta_color="normal")
            
            if sim_risk_ratio < 3.0 and sim_target_contracts > 0:
                st.warning("? ï? æ³¨æ?ï¼šå³ä½¿èª¿?´å?ï¼Œé¢¨?ªæ?æ¨™ä?ä½æ–¼ 300%ï¼Œå»ºè­°è??¢æ?æ¸›å???•¸??)
            elif sim_target_contracts == 0:
                st.success("?®å??¡éƒ¨ä½ï??¡é¢¨?ªã€?)
            else:
                st.success("é¢¨éšª?‡æ?å®‰å…¨??)

    # New Tab: Comparison
    with t8:
        render_comparison_page(df)

# --- Render Function: New Strategy ---
# Removed Rebalance Page as requested

# --- Render Function: Comparison ---
def render_comparison_page(df):
    st.subheader("ç­–ç•¥ç¶œå?æ¯”è?")
    
    col1, col2 = st.columns(2)
    # Fix: Explicitly use value=... to avoid 2000000 being interpreted as min_value
    cap = col1.number_input("æ¯”è??å?è³‡é?", value=2000000, step=100000, min_value=100000)
    
    with st.expander("?ƒæ•¸è¨­å? (è³‡é??†é? & ç­–ç•¥è¨­å?)", expanded=True):
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.markdown("#### 1. ?Ÿè²¨?¿éšªç­–ç•¥")
            # Default 90% in 00631L, 10% in Cash for Futures
            f_long_pct = st.slider("00631L ?¨ä??æ?æ¯”ä? (%)", 50, 100, 90, 5, key='comp_f_long') / 100.0
            st.caption(f"?©é? {1-f_long_pct:.0%} è³‡é? ({cap*(1-f_long_pct):,.0f}) ä¿ç??¼æ?è²¨ä?è­‰é?å°ˆæˆ¶")
            
            st.divider()
            
            st.markdown("#### 2. è³‡ç”¢å¹³è¡¡ç­–ç•¥")
            # Default 50/50
            r_long_pct = st.slider("00631L ?®æ??ç½®æ¯”ä? (%)", 10, 90, 50, 5, key='comp_r_long') / 100.0
            st.caption(f"?ç½® {r_long_pct:.0%} ({cap*r_long_pct:,.0f}) ??00631Lï¼Œå…¶é¤?{1-r_long_pct:.0%} ?ºç¾??)

        with col_p2:
            st.markdown("#### 3. ç´”æ?è²¨ç???(?šå?/è¶¨å‹¢)")
            fut_lev = st.slider("?Ÿè²¨æ§“æ¡¿?æ•¸ (X)", 1.0, 5.0, 2.0, 0.5, key='comp_fut_lev')
            st.caption(f"?Ÿå?è³‡é? {cap:,.0f}ï¼Œç›®æ¨™æ???{cap*fut_lev:,.0f}")
            
            ma_trend = st.number_input("è¶¨å‹¢ç­–ç•¥?‡ç? (MA)", min_value=5, max_value=200, value=13, step=1, key='comp_ma_trend')
            st.caption(f"å¤§æ–¼ {ma_trend}MA ?šå?ï¼Œå??¼å??šç©º")
            
            st.divider()
            div_yield = st.slider("?ä¼°å¹´å??†åƒ¹å·?æ®–åˆ©??(%)", 0.0, 10.0, 4.0, 0.5, key='comp_div_yield') / 100.0
            st.caption(f"æ¨¡æ“¬?Ÿè²¨?†åƒ¹å·®å¸¶ä¾†ç?é¡å??¶ç? (?è¨­ 4%)")
            
            ignore_short_yield = st.checkbox("?šç©ºä¸è??†åƒ¹å·®æ???(æ¸¬è©¦??", value=False)
            
            st.divider()
            st.markdown("#### 7. ç´”æ?è²?(æ³¢æ®µ?šå?)")
            ma_long = st.number_input("æ³¢æ®µ?šå??‡ç? (MA)", min_value=5, max_value=200, value=13, step=1, key='comp_ma_long')
            st.caption(f"å¤§æ–¼ {ma_long}MA ?šå?ï¼Œè??´å?å¹³å€?(ä¸æ”¾ç©?")

        with st.expander("ç­–ç•¥ 5: ?Ÿè²¨ + 00878 (New)", expanded=True):
            st.markdown("#### 5. ?Ÿè²¨æ§“æ¡¿ + 00878 ?¾é?ç®¡ç?")
            st.caption("?©ç”¨?Ÿè²¨?”æ?æ§“æ¡¿?éšªï¼Œå‰©é¤˜ç¾?‘è²·??00878 ?˜æ¯")
            
            col_f8_1, col_f8_2 = st.columns(2)
            f8_lev = col_f8_1.slider("?Ÿè²¨æ§“æ¡¿ (X)", 1.0, 4.0, 2.0, 0.5, key='f8_lev')
            f8_risk = col_f8_2.number_input("?®æ?é¢¨éšª?‡æ? (%)", value=300, step=50, key='f8_risk') / 100.0
            
            st.info(f"?è¼¯ï¼šç›®æ¨?{f8_lev}?å¤§?¤æ??ªã€‚ä??™ã€Œä?è­‰é? x {f8_risk:.0%}?ä??¾é??¼æ?è²¨æˆ¶ï¼Œå…¶é¤˜è²·??00878??)

    if 'show_comparison' not in st.session_state:
        st.session_state['show_comparison'] = False

    if st.button("?‹å?æ¯”è?", type="primary"):
        st.session_state['show_comparison'] = True
        
    if st.session_state['show_comparison']:
        # 1. Futures (Uses user params)
        df_f, trades_f, _, _, cost_f = run_backtest_original(
            df, 13, cap, f_long_pct, 1-f_long_pct, 85000, 
            'å®Œå…¨?¿éšª (Neutral Hedge)', True, f_long_pct, 
            40, 2e-5, 1, True
        )
        
        # 2. Rebalance (Uses user params)
        df_r, log_r, cost_r = run_backtest_rebalance(df, cap, r_long_pct)
        
        # 3. Pure Futures Long
        df_fl, log_fl, cost_fl = run_backtest_futures_simple(df, cap, fut_lev, 'Long-Only', 0, dividend_yield=div_yield)
        
        # 4. Futures Trend
        df_ft, log_ft, cost_ft = run_backtest_futures_simple(df, cap, fut_lev, 'Trend', ma_trend, dividend_yield=div_yield, ignore_short_yield=ignore_short_yield)
        
        # 5. Futures + 00878
        df_f8, log_f8, cost_f8 = run_backtest_futures_00878(df, cap, f8_lev, 85000, f8_risk, dividend_yield=div_yield)
        
        # 6. Pure 00878 Buy & Hold
        df_8only, log_8only, cost_8only = run_backtest_00878_only(df, cap)
        
        # 7. Futures Long-MA
        df_fma, log_fma, cost_fma = run_backtest_futures_simple(df, cap, fut_lev, 'Long-MA', ma_long, dividend_yield=div_yield)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_f.index, y=df_f['Benchmark'], name='Buy&Hold 00631L', line=dict(color='gray', width=2)))
        fig.add_trace(go.Scatter(x=df_f.index, y=df_f['Total_Equity'], name=f'?Ÿè²¨?¿éšª (00631L {f_long_pct:.0%})', line=dict(color='red', width=2)))
        fig.add_trace(go.Scatter(x=df_r.index, y=df_r['Total_Equity'], name=f'è³‡ç”¢å¹³è¡¡ (00631L {r_long_pct:.0%})', line=dict(color='blue', width=2)))
        fig.add_trace(go.Scatter(x=df_fl.index, y=df_fl['Total_Equity'], name=f'ç´”æ?è²¨å?å¤?({fut_lev}x)', line=dict(color='orange', width=2, dash='dot')))
        fig.add_trace(go.Scatter(x=df_ft.index, y=df_ft['Total_Equity'], name=f'ç´”æ?è²¨è¶¨??({fut_lev}x) MA{ma_trend}', line=dict(color='purple', width=2, dash='dot')))
        fig.add_trace(go.Scatter(x=df_f8.index, y=df_f8['Total_Equity'], name=f'?Ÿè²¨({f8_lev}x) + 00878', line=dict(color='#00C853', width=3)))
        fig.add_trace(go.Scatter(x=df_8only.index, y=df_8only['Total_Equity'], name='Buy & Hold 00878', line=dict(color='#00897B', width=2)))
        fig.add_trace(go.Scatter(x=df_fma.index, y=df_fma['Total_Equity'], name=f'ç´”æ?è²¨æ³¢æ®?({fut_lev}x) MA{ma_long}', line=dict(color='#FFD600', width=2)))
        
        fig.update_layout(
            title='ç­–ç•¥ç¸¾æ??‡è??¢æ›²ç·šæ?è¼?(?«é€†åƒ¹å·®èª¿??',
            xaxis_title='?¥æ?',
            yaxis_title='ç¸½è???(TWD)',
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_white",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Calculate Long P&L and Short P&L for each strategy
        # Formula: ?å?è³‡é? + ?šå??ç? + ?šç©º?ç? - ?‹ç?è²?= ?Ÿæœ«ç¸½è???
        
        # Helper function for pure futures strategies (no separate long/short, just total P&L)
        def calc_futures_pnl(df_result, initial_capital, cost):
            """For pure futures strategies, total P&L = final - initial + cost"""
            final = df_result['Total_Equity'].iloc[-1]
            total_pnl = final - initial_capital + cost  # Add back cost since it was deducted
            return total_pnl, 0  # All is "long-like" for long strategies
        
        # Helper for trend strategy (has both long and short periods)
        def calc_trend_pnl(log_df):
            """Calculate long pnl and short pnl from trend strategy log"""
            if log_df is None or log_df.empty or '?¬ç??ç?' not in log_df.columns:
                return 0, 0
            
            long_pnl = 0
            short_pnl = 0
            
            for i, row in log_df.iterrows():
                pnl = row.get('?¬ç??ç?', 0)
                action = row.get('?•ä?', '')
                
                if pnl != 0:
                    # Check if it was a long or short position being closed
                    if 'å¤? in action or ('å¹³å€? in action and row.get('?®æ???•¸', 0) <= 0):
                        long_pnl += pnl
                    elif 'ç©? in action:
                        short_pnl += pnl
                    else:
                        # Default: if previous contracts > 0, it was long
                        long_pnl += pnl
            
            return long_pnl, short_pnl
        
        # 1. Buy&Hold 00631L - No trading
        long_pnl_bh = df_f['Benchmark'].iloc[-1] - cap
        short_pnl_bh = 0
        
        # 2. ?Ÿè²¨?¿éšªç­–ç•¥ - Already returned from run_backtest_original
        # Need to re-run to get the actual values
        df_f2, trades_f2, long_pnl_f, short_pnl_f, cost_f2 = run_backtest_original(
            df, 13, cap, f_long_pct, 1-f_long_pct, 85000, 
            'å®Œå…¨?¿éšª (Neutral Hedge)', True, f_long_pct, 
            40, 2e-5, 1, True
        )
        
        # 3. è³‡ç”¢å¹³è¡¡ç­–ç•¥ - Calculate from equity change
        long_pnl_r = df_r['Total_Equity'].iloc[-1] - cap + cost_r
        short_pnl_r = 0  # No short positions
        
        # 4. ç´”æ?è²¨å?å¤?- All is long
        long_pnl_fl = df_fl['Total_Equity'].iloc[-1] - cap + cost_fl
        short_pnl_fl = 0
        
        # 5. ç´”æ?è²¨è¶¨??- Has both long and short
        long_pnl_ft, short_pnl_ft = calc_trend_pnl(log_ft)
        # Adjust if numbers don't add up (due to unrealized or calculation differences)
        total_pnl_ft = df_ft['Total_Equity'].iloc[-1] - cap + cost_ft
        if long_pnl_ft + short_pnl_ft == 0:
            # Fallback: use total as "long" if can't separate
            long_pnl_ft = total_pnl_ft
            short_pnl_ft = 0
        
        # 6. ?Ÿè²¨ + 00878 - All is long-like
        long_pnl_f8 = df_f8['Total_Equity'].iloc[-1] - cap + cost_f8
        short_pnl_f8 = 0
        
        # 7. ?®ç??æ? 00878
        long_pnl_8only = df_8only['Total_Equity'].iloc[-1] - cap + cost_8only
        short_pnl_8only = 0
        
        # 8. ç´”æ?è²?(æ³¢æ®µ?šå?)
        long_pnl_fma = df_fma['Total_Equity'].iloc[-1] - cap + cost_fma
        short_pnl_fma = 0
        
        # Table
        data = []
        strategies = [
            ('Buy&Hold 00631L', '100% ?æ?', df_f['Benchmark'], 0, long_pnl_bh, short_pnl_bh), 
            ('?Ÿè²¨?¿éšªç­–ç•¥', f'00631L {f_long_pct:.0%} / ?¾é? {1-f_long_pct:.0%}', df_f['Total_Equity'], cost_f, long_pnl_f, short_pnl_f), 
            ('è³‡ç”¢å¹³è¡¡ç­–ç•¥', f'00631L {r_long_pct:.0%} / ?¾é? {1-r_long_pct:.0%}', df_r['Total_Equity'], cost_r, long_pnl_r, short_pnl_r),
            ('ç´”æ?è²¨å?å¤?, f'æ§“æ¡¿ {fut_lev}x / æ®–åˆ©??{div_yield:.1%}', df_fl['Total_Equity'], cost_fl, long_pnl_fl, short_pnl_fl),
            ('ç´”æ?è²¨è¶¨??(å¤šç©º)', f'æ§“æ¡¿ {fut_lev}x / MA{ma_trend} / æ®–åˆ©??{div_yield:.1%}', df_ft['Total_Equity'], cost_ft, long_pnl_ft, short_pnl_ft),
            ('?Ÿè²¨ + 00878', f'æ§“æ¡¿ {f8_lev}x / é¢¨éšª?‡æ? {f8_risk:.0%}', df_f8['Total_Equity'], cost_f8, long_pnl_f8, short_pnl_f8),
            ('?®ç??æ? 00878', '100% ?æ? (2020/7ä¸Šå?)', df_8only['Total_Equity'], cost_8only, long_pnl_8only, short_pnl_8only),
            ('ç´”æ?è²?(æ³¢æ®µ?šå?)', f'æ§“æ¡¿ {fut_lev}x / MA{ma_long}', df_fma['Total_Equity'], cost_fma, long_pnl_fma, short_pnl_fma)
        ]
        
        for name, param, d, cost, long_pnl, short_pnl in strategies:
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
            
            # Verify formula: ?å?è³‡é? + ?šå??ç? + ?šç©º?ç? - ?‹ç?è²?= ?Ÿæœ«ç¸½è???
            calculated = cap + long_pnl + short_pnl - cost
            
            data.append({
                'ret_value': ret,  # For sorting
                'ç­–ç•¥?ç¨±': name,
                '?ƒæ•¸è¨­å?': param,
                'ç¸½å ±?¬ç?': f"{ret:.2%}", 
                'å¹´å??±é…¬??(CAGR)': f"{cagr:.2%}",
                '?€å¤§å???(MDD)': f"{mdd:.2%}", 
                'ç¸½äº¤?“æ???: f"{cost:,.0f}",
                '?šå?ç¸½æ???: f"{long_pnl:,.0f}",
                '?šç©ºç¸½æ???: f"{short_pnl:,.0f}" if short_pnl != 0 else "-",
                '?Ÿæœ«ç¸½è???: f"{final_val:,.0f}"
            })
        
        # Sort by return rate (descending) and add ranking
        df_result = pd.DataFrame(data)
        df_result = df_result.sort_values('ret_value', ascending=False).reset_index(drop=True)
        df_result.insert(0, '?’å?', range(1, len(df_result) + 1))
        df_result = df_result.drop('ret_value', axis=1)  # Remove sorting column
        
        st.table(df_result)
        

        
        # --- Detailed Strategy View (Buy/Sell Points) ---
        st.subheader("?? ç­–ç•¥è²·è³£é»è©³??)
        
        # Map strategy names to their logs
        strategy_logs = {
            'ç´”æ?è²¨å?å¤?: log_fl,
            'ç´”æ?è²¨è¶¨??(å¤šç©º)': log_ft,
            'ç´”æ?è²?(æ³¢æ®µ?šå?)': log_fma,
            '?Ÿè²¨?¿éšªç­–ç•¥': pd.DataFrame(trades_f) if trades_f else pd.DataFrame(),
            'è³‡ç”¢å¹³è¡¡ç­–ç•¥': log_r,
            '?Ÿè²¨ + 00878': log_f8,
            '?®ç??æ? 00878': log_8only
        }
        
        selected_strategy = st.selectbox("?¸æ?è¦æŸ¥?‹è²·è³???„ç???, list(strategy_logs.keys()), index=1)
        
        if selected_strategy:
            detail_log = strategy_logs[selected_strategy]
            
            if not detail_log.empty:
                # Create Figure
                fig_detail = go.Figure()
                
                # 1. Base Price Line (TAIEX or 00878 depending on strategy)
                if '00878' in selected_strategy:
                    # For 00878 strategies, maybe show 00878 price? 
                    # But most actions are based on TAIEX or rebalancing.
                    # Let's show TAIEX for consistency, or 00878 for Pure 00878.
                    if selected_strategy == '?®ç??æ? 00878':
                        fig_detail.add_trace(go.Scatter(x=df.index, y=df['00878'], name='00878 ?¡åƒ¹', line=dict(color='gray', width=1)))
                        price_col = '?¹æ ¼'
                    else:
                        fig_detail.add_trace(go.Scatter(x=df.index, y=df['TAIEX'], name='? æ??‡æ•¸', line=dict(color='gray', width=1)))
                        price_col = '?‡æ•¸'
                else:
                    fig_detail.add_trace(go.Scatter(x=df.index, y=df['TAIEX'], name='? æ??‡æ•¸', line=dict(color='gray', width=1)))
                    price_col = '?‡æ•¸'
                    
                # 2. Add Markers
                # Filter actions
                # Common actions: ?°å€?(å¤?ç©?, å¹³å€? ?æ?, ? ç¢¼, æ¸›ç¢¼
                # Trades log (Strategy 1) has different format: ?²å ´?¥æ?, ?ºå ´?¥æ?...
                
                if selected_strategy == '?Ÿè²¨?¿éšªç­–ç•¥':
                    # Handle Strategy 1 (Trades format)
                    # Plot Entries
                    fig_detail.add_trace(go.Scatter(
                        x=detail_log['?²å ´?¥æ?'], 
                        y=detail_log['?²å ´?‡æ•¸'],
                        mode='markers',
                        name='?²å ´ (ç©ºå–®)',
                        marker=dict(symbol='triangle-down', size=10, color='red')
                    ))
                    # Plot Exits
                    fig_detail.add_trace(go.Scatter(
                        x=detail_log['?ºå ´?¥æ?'], 
                        y=detail_log['?ºå ´?‡æ•¸'],
                        mode='markers',
                        name='?ºå ´ (å¹³å€?',
                        marker=dict(symbol='x', size=8, color='black')
                    ))
                else:
                    # Handle Standard Logs
                    # Check if '?•ä?' column exists
                    if '?•ä?' in detail_log.columns:
                        # Define colors/symbols
                        # Long Entries: Green Triangle Up
                        # Short Entries: Red Triangle Down
                        # Close: Black X
                        # Reduce: Orange Circle
                        
                        # Helper to filter
                        def get_mask(keyword):
                            return detail_log['?•ä?'].str.contains(keyword, na=False)
                        
                        # Longs (New, Add, Reverse Long)
                        mask_long = get_mask('å¤?) & (get_mask('?°å€?) | get_mask('? ç¢¼') | get_mask('?æ?'))
                        if mask_long.any():
                            fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_long]['?¥æ?']),
                                y=detail_log[mask_long][price_col] if price_col in detail_log.columns else detail_log[mask_long]['?äº¤??],
                                mode='markers',
                                name='?šå?/? ç¢¼',
                                marker=dict(symbol='triangle-up', size=10, color='green')
                            ))
                            
                        # Shorts (New, Add, Reverse Short)
                        mask_short = get_mask('ç©?) & (get_mask('?°å€?) | get_mask('? ç¢¼') | get_mask('?æ?'))
                        if mask_short.any():
                            fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_short]['?¥æ?']),
                                y=detail_log[mask_short][price_col] if price_col in detail_log.columns else detail_log[mask_short]['?äº¤??],
                                mode='markers',
                                name='?šç©º/? ç¢¼',
                                marker=dict(symbol='triangle-down', size=10, color='red')
                            ))
                            
                        # Close
                        mask_close = get_mask('å¹³å€?)
                        if mask_close.any():
                            fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_close]['?¥æ?']),
                                y=detail_log[mask_close][price_col] if price_col in detail_log.columns else detail_log[mask_close]['?äº¤??],
                                mode='markers',
                                name='å¹³å€?,
                                marker=dict(symbol='x', size=8, color='black')
                            ))
                            
                        # Reduce
                        mask_reduce = get_mask('æ¸›ç¢¼')
                        if mask_reduce.any():
                            fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_reduce]['?¥æ?']),
                                y=detail_log[mask_reduce][price_col] if price_col in detail_log.columns else detail_log[mask_reduce]['?äº¤??],
                                mode='markers',
                                name='æ¸›ç¢¼',
                                marker=dict(symbol='circle', size=8, color='orange')
                            ))
                            
                        # Rebalance (Strategy 2)
                        mask_rebal = get_mask('?å¹³è¡?)
                        if mask_rebal.any():
                             fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_rebal]['?¥æ?']),
                                y=detail_log[mask_rebal]['?äº¤??], # 00631L Price
                                mode='markers',
                                name='?å¹³è¡?,
                                marker=dict(symbol='circle', size=6, color='blue')
                            ))
                            
                        # Buy & Hold (Strategy 6)
                        mask_buy = get_mask('è²·é€²æ???)
                        if mask_buy.any():
                             fig_detail.add_trace(go.Scatter(
                                x=pd.to_datetime(detail_log[mask_buy]['?¥æ?']),
                                y=detail_log[mask_buy]['?¹æ ¼'],
                                mode='markers',
                                name='è²·é€?,
                                marker=dict(symbol='triangle-up', size=12, color='green')
                            ))

                fig_detail.update_layout(
                    title=f'{selected_strategy} - è²·è³£é»å?ä½?,
                    xaxis_title='?¥æ?',
                    yaxis_title='?‡æ•¸ / ?¹æ ¼',
                    hovermode='closest',
                    template="plotly_white",
                    height=600,
                    # Add range slider for time selection
                    xaxis=dict(
                        rangeslider=dict(visible=True, thickness=0.05),
                        rangeselector=dict(
                            buttons=list([
                                dict(count=6, label="6?‹æ?", step="month", stepmode="backward"),
                                dict(count=1, label="1å¹?, step="year", stepmode="backward"),
                                dict(count=3, label="3å¹?, step="year", stepmode="backward"),
                                dict(count=5, label="5å¹?, step="year", stepmode="backward"),
                                dict(step="all", label="?¨éƒ¨")
                            ]),
                            bgcolor="lightgray",
                            activecolor="red",
                            font=dict(size=12),
                        ),
                        type="date",
                        tickformat="%Y-%m",  # Show Year-Month only
                        dtick="M6",  # Tick every 6 months
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                st.plotly_chart(fig_detail, use_container_width=True)
            else:
                st.info("æ­¤ç??¥ç„¡äº¤æ?ç´€??)

        st.subheader("?? ?„ç??¥è©³ç´°äº¤?“ç???)
        
        # æ¨???½æ•¸ï¼šæ ¹?šæ??Šæ?ä½è¨­å®šé???
        def style_pnl(df, pnl_col):
            """?ºæ??Šæ?ä½å?ä¸Šé??²ï??²åˆ©ç¶ è‰²?è™§?ç???""
            if df.empty or pnl_col not in df.columns:
                return df
            
            def highlight_row(row):
                try:
                    val = row[pnl_col]
                    if pd.isna(val) or val == 0:
                        return [''] * len(row)
                    elif val > 0:
                        return ['background-color: #d4edda'] * len(row)  # æ·ºç???
                    else:
                        return ['background-color: #f8d7da'] * len(row)  # æ·ºç???
                except:
                    return [''] * len(row)
            
            return df.style.apply(highlight_row, axis=1)
        
        with st.expander("1. ?Ÿè²¨?¿éšªç­–ç•¥ - äº¤æ??ç´°"):
            if trades_f:
                df_trades = pd.DataFrame(trades_f)
                st.dataframe(style_pnl(df_trades, '?²åˆ©?‘é? (TWD)'), use_container_width=True)
            else:
                st.info("?¡äº¤?“ç???)
                
        with st.expander("2. è³‡ç”¢å¹³è¡¡ç­–ç•¥ - ?å¹³è¡¡ç???):
            # è³‡ç”¢å¹³è¡¡æ²’æ??®ç??ç?ï¼Œä?å¥—ç”¨é¡è‰²
            st.dataframe(log_r, use_container_width=True)
            
        with st.expander("3. ç´”æ?è²¨å?å¤?- äº¤æ?ç´€??):
            st.dataframe(style_pnl(log_fl, '?¬ç??ç?'), use_container_width=True)
            
        with st.expander("4. ç´”æ?è²¨è¶¨??- äº¤æ?ç´€??):
            st.dataframe(style_pnl(log_ft, '?¬ç??ç?'), use_container_width=True)
            
        with st.expander("5. ?Ÿè²¨ + 00878 - è©³ç´°ç´€??):
            # 00878 ç­–ç•¥?¯å?å¹³è¡¡ç´€?„ï?ä¸å??¨é???
            st.dataframe(log_f8, use_container_width=True)
            
        with st.expander("6. ?®ç??æ? 00878 - äº¤æ?ç´€??):
            st.dataframe(log_8only, use_container_width=True)
            
        with st.expander("7. ç´”æ?è²?(æ³¢æ®µ?šå?) - äº¤æ?ç´€??):
            st.dataframe(style_pnl(log_fma, '?¬ç??ç?'), use_container_width=True)

        # =============================================================================
        # ç­–ç•¥?†æ??±å?
        # =============================================================================
        st.markdown("---")
        st.subheader("?? ç­–ç•¥?†æ??±å?")
        
        # ç­–ç•¥ç¸½è¦½
        with st.expander("?? ç­–ç•¥ç¸½è¦½", expanded=True):
            st.markdown("""
| é¡å? | ç­–ç•¥ | é¢¨éšªç­‰ç? | ?©å??•è?äº?|
|------|------|---------|-----------|
| ?”µ è¢«å??æ? | Buy&Hold 00631L | ä¸­é? | ?·æ??‹å??èƒ½?¿å?æ³¢å? |
| ?”µ è¢«å??æ? | ?®ç??æ? 00878 | ä½?| è¿½æ?ç©©å??¾é?æµ?|
| ?Ÿ¢ ?¿éšª/å¹³è¡¡ | ?Ÿè²¨?¿éšªç­–ç•¥ | ä¸?| ?³é?ä½?00631L æ³¢å? |
| ?Ÿ¢ ?¿éšª/å¹³è¡¡ | è³‡ç”¢å¹³è¡¡ç­–ç•¥ | ä¸­ä? | ä¿å??‹æ?è³‡äºº |
| ?”´ æ§“æ¡¿?Ÿè²¨ | ç´”æ?è²¨å?å¤?| é«?| ?Ÿæ??Ÿè²¨?é?é¢¨éšª?¿å? |
| ?”´ æ§“æ¡¿?Ÿè²¨ | ç´”æ?è²¨è¶¨??(å¤šç©º) | æ¥µé? | å°ˆæ¥­äº¤æ???|
| ?”´ æ§“æ¡¿?Ÿè²¨ | ç´”æ?è²?(æ³¢æ®µ?šå?) | é«?| ?³é?ä½æ?è²¨é¢¨??|
| ?Ÿ¡ æ··å?ç­–ç•¥ | ?Ÿè²¨ + 00878 | ä¸­é? | è¿½æ??é•·+?æ¯ |
            """)
        
        # ?„ç??¥è©³ç´°èªª??
        with st.expander("?? ?„ç??¥è©³ç´°èªª??):
            st.markdown("""
### 1. Buy&Hold 00631L
- **?è¼¯**: è²·é€²æ???00631Lï¼Œäº«?—ç? 2 ?å¤§?¤æ???
- **?ªé?**: ç°¡å–®?ç„¡äº¤æ??æœ¬?å??­æ?è¡¨ç¾ä½?
- **ç¼ºé?**: ç©ºé ­?‚è™§?å??ã€æ?ç®¡ç?è²?(~1%/å¹?

### 2. ?Ÿè²¨?¿éšªç­–ç•¥
- **?è¼¯**: ?æ? 00631L + ?‡ç?ä¸‹å??‚å?ç©ºæ?è²¨é¿??
- **è¨Šè?**: ?‡æ•¸ < MA ??å»ºç©º?®ï??‡æ•¸ > MA ??å¹³å€?
- **?ªé?**: ?ä??æ??å¤±?ä??™å??­æ”¶??

### 3. è³‡ç”¢å¹³è¡¡ç­–ç•¥
- **?è¼¯**: 70% 00631L + 30% ?¾é?ï¼Œæ??ˆå?å¹³è¡¡
- **?ªé?**: ?ªå?è³??è²·ä??é?ä½æ³¢??

### 4. ç´”æ?è²¨å?å¤?
- **?è¼¯**: 100% è³‡é??šå?å°å°?Ÿè²¨ + æ§“æ¡¿
- **?¹è‰²**: äº«å??†åƒ¹å·®æ”¶??(~4%/å¹?
- ? ï? 2 ?æ?æ¡¿æ?ï¼Œå¤§?¤è? 25% = è³‡é??°æ–¬

### 5. ç´”æ?è²¨è¶¨??(å¤šç©º)
- **?è¼¯**: ?‡æ•¸ > MA ???šå?ï¼›æ???< MA ???šç©º
- ? ï? ?šç©º?Ÿè²¨?€?¯ä??†åƒ¹å·®æ???

### 6. ç´”æ?è²?(æ³¢æ®µ?šå?)
- **?è¼¯**: ?‡æ•¸ > MA ???šå?ï¼›æ???< MA ??ç©ºæ?
- **?ªé?**: ?¿é?ä¸»è?ä¸‹è??ä??™ç¾??

### 7. ?Ÿè²¨ + 00878
- **?è¼¯**: ?Ÿè²¨?”æ?æ§“æ¡¿?éšª + ?’ç½®è³‡é?è²?00878
- **?¹è‰²**: æ§“æ¡¿ + ?¡æ¯?™é??¶ç?
- ??å·²è???00878 æ­·å²?æ¯

### 8. ?®ç??æ? 00878
- **?è¼¯**: 100% è²·é€²æ???00878 é«˜è‚¡??ETF
- **?¡æ¯æ®–åˆ©??*: ç´?5-6%/å¹?
            """)
        
        # é¢¨éšªæ¯”è?
        with st.expander("? ï? é¢¨éšªç­‰ç?æ¯”è?"):
            st.markdown("""
```
é¢¨éšªç­‰ç? (ä½???é«?

?®ç??æ? 00878
    ??
è³‡ç”¢å¹³è¡¡ç­–ç•¥
    ??
?Ÿè²¨?¿éšªç­–ç•¥
    ??
?Ÿè²¨ + 00878
    ??
Buy&Hold 00631L
    ??
ç´”æ?è²¨å?å¤?
    ??
ç´”æ?è²?(æ³¢æ®µ?šå?)
    ??
ç´”æ?è²¨è¶¨??(å¤šç©º)
```
            """)
            
        # ?è??é?
        with st.expander("?’¡ ?•è?æ³¨æ?äº‹é?"):
            st.warning("""
**?è??é?:**
1. **æ²’æ??€å¥½ç?ç­–ç•¥**ï¼Œåª?‰æ??©å??ªå·±?„ç???
2. **æ§“æ¡¿?¯é??¢å?**ï¼šæ”¾å¤§ç²?©ä??¾å¤§?§æ?
3. **?æ¸¬ ??å¯¦æˆ°**ï¼šæ??¹ã€æ?ç·’ã€é?å¤©é??½æ?å½±éŸ¿ç¸¾æ?
4. **å»ºè­°**ï¼šå?ä½é¢¨?ªç??¥é?å§‹ï??æ­¥èª¿æ•´
            """)

# --- Main Flow ---
st.sidebar.header("è³‡æ?ä¾†æ?")
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
    # Use default files if exist
    if os.path.exists("00631L_2015-2025.xlsx"):
        d1 = pd.read_excel("00631L_2015-2025.xlsx")
        d2 = pd.read_excel("? æ??‡æ•¸è³‡æ?.xlsx")
        # Quick clean
        def cl(d, n):
            d.columns = [str(x).lower() for x in d.columns]
            dc = [c for c in d if 'date' in c or '?¥æ?' in c][0]
            pc = [c for c in d if 'close' in c or '?? in c][0]
            d[dc] = pd.to_datetime(d[dc])
            return d[[dc, pc]].rename(columns={dc:'Date', pc:n}).set_index('Date')
        df_g = pd.merge(cl(d1, '00631L'), cl(d2, 'TAIEX'), left_index=True, right_index=True)
        
        # Try load 00878 from file if exists, else fill NaN
        if os.path.exists("00878.xlsx"):
             d3 = pd.read_excel("00878.xlsx")
             df_g = pd.merge(df_g, cl(d3, '00878'), left_index=True, right_index=True, how='left')
        else:
             df_g['00878'] = np.nan
        st.sidebar.success("Local File Loaded")

if df_g is not None and not df_g.empty:
    min_d, max_d = df_g.index.min(), df_g.index.max()
    
    if pd.isna(min_d) or pd.isna(max_d):
        st.error("è³‡æ?ç´¢å??°å¸¸ (NaT)ï¼Œè?æª¢æŸ¥è³‡æ?ä¾†æ???)
    else:
        # Streamlit date_input expects date objects, not timestamps
        min_d = min_d.date()
        max_d = max_d.date()
        
        # Ensure range is valid
        if min_d > max_d:
            st.error("è³‡æ??¥æ?ç¯„å??¡æ? (Start > End)")
        else:
            rng = st.sidebar.date_input("?€??, [min_d, max_d], min_value=min_d, max_value=max_d)
            
            if len(rng) == 2:
                start_date, end_date = rng
                
                # Filter global df here
                mask = (df_g.index >= pd.to_datetime(start_date)) & (df_g.index <= pd.to_datetime(end_date))
                df_test_raw = df_g.loc[mask].copy()

                st.sidebar.markdown("---")
                
                # Consolidate views - Directly render the main strategy page (which now includes Comparison as a tab)
                render_original_strategy_page(df_test_raw)

            else:
                st.info("è«‹é¸?‡å??´ç??‹å??‡ç??Ÿæ—¥??)

elif df_g is not None and df_g.empty:
    st.warning("ä¸‹è??–è??–ç?è³‡æ??ºç©ºï¼Œç„¡æ³•é€²è??æ¸¬??)
else:
    st.info("è«‹å?æº–å?è³‡æ?")

