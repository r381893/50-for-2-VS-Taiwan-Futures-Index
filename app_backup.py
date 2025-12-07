import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import yfinance as yf
import json


st.set_page_config(page_title="台灣五十正2 & 小台 Backtest", layout="wide")

st.title("台灣五十正2 (00631L) & 小台指 (Small Tai) 策略回測")

# --- CSS Styling ---
st.markdown("""
<style>
    /* Global Font */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft JhengHei', sans-serif;
    }
    
    /* Metric Card Style */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
        margin-bottom: 10px;
    }
    .dark-theme .metric-card {
        background-color: #262730;
        border: 1px solid #464b59;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #333;
    }
    .metric-delta {
        font-size: 0.9rem;
        margin-top: 5px;
    }
    .delta-pos { color: #d32f2f; } /* Red for Up */
    .delta-neg { color: #388e3c; } /* Green for Down */
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 5px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ff4b4b;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def metric_card(label, value, delta=None, delta_color="normal"):
    delta_html = ""
    if delta:
        if delta_color == "inverse":
            color_class = "delta-neg" if "-" not in str(delta) and float(str(delta).replace(',','').replace('%','')) > 0 else "delta-pos"
        else:
            # Normal: Red is Positive (Taiwan Stock), Green is Negative
            # Assuming input delta is string like "10%" or "-5%"
            is_positive = "-" not in str(delta) and float(str(delta).replace(',','').replace('%','')) != 0
            color_class = "delta-pos" if is_positive else "delta-neg"
            
        delta_html = f'<div class="metric-delta {color_class}">{delta}</div>'
        
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

# --- Core Backtest Function ---
def run_backtest(df_data, ma_period, initial_capital, long_allocation_pct, short_allocation_pct, 
                 margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
                 cost_fee, cost_tax, cost_slippage, include_costs):
    
    df = df_data.copy()
    
    # Calculate MA
    df['MA'] = df['TAIEX'].rolling(window=ma_period).mean()
    
    # Position Signal (1 = Short, 0 = Flat)
    df['Position'] = (df['TAIEX'] < df['MA']).shift(1).fillna(0)
    
    # Initialize variables
    long_capital = initial_capital * long_allocation_pct
    short_capital_initial = initial_capital * short_allocation_pct
    
    long_equity_arr = []
    short_equity_arr = []
    total_equity_arr = []
    
    total_long_pnl = 0
    total_short_pnl = 0
    total_cost = 0
    
    current_long_capital = long_capital
    current_short_capital = short_capital_initial
    
    # Buy initial shares of 00631L
    initial_price_00631L = df['00631L'].iloc[0]
    shares_00631L = current_long_capital / initial_price_00631L
    
    last_month = df.index[0].month
    
    trades = []
    in_trade = False
    entry_price = 0
    entry_date = None
    entry_capital = 0
    entry_long_equity = 0
    
    for i in range(len(df)):
        date = df.index[i]
        price_00631L = df['00631L'].iloc[i]
        price_taiex = df['TAIEX'].iloc[i]
        position = df['Position'].iloc[i]
        
        # --- 1. Long Leg P&L ---
        long_equity = shares_00631L * price_00631L
        
        if i > 0:
            prev_price_00631L = df['00631L'].iloc[i-1]
            daily_long_pnl = shares_00631L * (price_00631L - prev_price_00631L)
            total_long_pnl += daily_long_pnl
            
            # --- 2. Short Leg P&L ---
            prev_taiex = df['TAIEX'].iloc[i-1]
            idx_ret = (price_taiex - prev_taiex) / prev_taiex
            
            if position == 1:
                # Determine Contracts based on Margin
                # Logic: Contracts = Floor(Short Capital / Margin per Contract)
                # Note: We use the capital at the START of the trade or rebalance to determine contracts?
                # To be dynamic, we should use current capital. But usually contracts are fixed until rebalance or signal change.
                # For this backtest, let's assume we adjust contracts daily? No, that's high friction.
                # Let's assume we hold the contracts determined at entry or rebalance.
                # BUT, the previous logic was calculating notional daily.
                # To keep it simple and consistent with "Dynamic Balancing" concept in the prompt:
                # "Use the remaining percentage... calculate how many contracts... calculate risk"
                # If we strictly follow "Short Account has 30%", then:
                
                # We need to know how many contracts we are holding TODAY.
                # Let's assume we re-calculate contracts only on Signal Change or Rebalance?
                # Or do we simply calculate: max_contracts = current_short_capital // margin_per_contract
                # If we do it daily, it means we are compounding/de-compounding daily.
                # Let's stick to: Calculate contracts based on current capital daily (approximating daily re-adjustment or simply tracking the theoretical exposure)
                # However, real trading doesn't adjust daily.
                # Let's use the logic: Contracts are determined at ENTRY.
                # And if "Monthly Rebalance" is ON, we re-adjust contracts at month start.
                
                # Wait, the previous code calculated `actual_short_notional` every day based on `current_short_capital`.
                # That implies daily compounding/adjustment.
                # Let's stick to that for consistency, but use integer contracts.
                
                # Risk Control: Ensure Risk Indicator >= 300% (Equity >= 3 * Margin)
                # Max Contracts = Equity / (3 * Margin)
                safe_margin_factor = 3.0
                max_contracts = int(current_short_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
                
                if hedge_mode == "完全避險 (Neutral Hedge)":
                    # Target Notional = Long Equity * 2
                    # Target Contracts = Target Notional / (Price * 50)
                    target_notional = long_equity * 2
                    target_contracts = int(round(target_notional / (prev_taiex * 50))) # Use round to be closer to target
                    actual_contracts = min(target_contracts, max_contracts)
                else:
                    actual_contracts = max_contracts
                
                # Calculate P&L
                # P&L = Contracts * Points * 50
                # Points = Change in Index
                # But wait, if we change contracts daily, we need to account for cost?
                # The previous code didn't charge cost for daily adjustment, only for signal change.
                # Let's assume the "Contracts" variable for P&L calculation is based on the position held from previous day.
                
                # To avoid complexity of daily re-sizing costs, let's assume we hold the contracts determined at Entry (or Rebalance).
                # But the user said "Calculate risk indicator...".
                
                # Let's simplify:
                # We use the `current_short_capital` to determine capability.
                # But for P&L, we should use the contracts we *actually* hold.
                # Which means we need to track `held_contracts`.
                
                # Refined Logic:
                # 1. On Signal Entry: Calculate contracts = Capital // Margin. Open position.
                # 2. On Monthly Rebalance: Close and Re-open (re-calc contracts).
                # 3. Daily: P&L = held_contracts * (Price_diff) * 50.
                
                # However, implementing "held_contracts" state requires more change.
                # The previous code was: `short_pnl = actual_short_notional * (-1 * idx_ret)`
                # This is "Continuous Compounding" (Daily Rebalancing).
                # If I change to "Integer Contracts", I should probably stick to the "Daily Re-eval" for the backtest loop to be simple,
                # OR properly implement state.
                # Given the user's request "Use 85000 to hedge... calculate how many contracts",
                # it sounds like they want to see the discrete contract number.
                
                # Let's try to be robust:
                # If we are IN A TRADE (Position=1), we have `current_contracts`.
                # We only update `current_contracts` if we Rebalance.
                pass # Logic handled below in the loop structure
            
            # We need to handle the P&L *before* we decide new contracts for tomorrow?
            # No, we calculate P&L based on *yesterday's* decision.
            
            # Let's look at how `trades` are recorded. They use `entry_capital`.
            # Let's stick to the previous structure but replace Notional with Contracts.
            
            # RE-DESIGNING THE LOOP FOR INTEGER CONTRACTS
            # This is a bit of a change from the "Continuous" model.
            
            # Let's use a simplified approach that mimics the previous one but with steps:
            # Daily P&L is based on the "Effective Notional" of the contracts we *would* hold.
            # max_contracts = int(current_short_capital / margin_per_contract)
            # actual_notional = max_contracts * prev_taiex * 50
            # short_pnl = actual_notional * (-1 * idx_ret)
            
            # This effectively simulates daily rebalancing of contracts (without cost).
            # It's a fair approximation for a "Strategy Backtest" unless we want to be very strict about costs.
            # The previous code `actual_short_notional = min(..., ...)` also implied daily adjustment.
            
            # Risk Control: Ensure Risk Indicator >= 300%
            safe_margin_factor = 3.0
            max_contracts = int(current_short_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
            
            if hedge_mode == "完全避險 (Neutral Hedge)":
                target_notional = long_equity * 2
                # Use prev_taiex to determine contracts needed at start of day
                target_contracts = int(round(target_notional / (prev_taiex * 50)))
                actual_contracts = min(target_contracts, max_contracts)
            else:
                actual_contracts = max_contracts
            
            # Calculate P&L for this day
            # P&L = Contracts * (Price - Prev_Price) * 50 * (-1)
            # Short: (Prev - Curr) * 50 * Contracts
            daily_points_change = price_taiex - prev_taiex
            short_pnl = actual_contracts * daily_points_change * 50 * (-1)
            
            if position == 1:
                current_short_capital += short_pnl
                total_short_pnl += short_pnl
        
        # --- 3. Transaction Costs & Trade Recording ---
        # Check for Position Change
        prev_pos = df['Position'].iloc[i-1] if i > 0 else 0
        
        if position != prev_pos:
            # Calculate Contracts for Cost
            # We need to know how many contracts we are opening/closing.
            # For simplicity in this "Daily Rebalance" approximation, we charge cost on the *current* target contracts.
            
            # Risk Control: Ensure Risk Indicator >= 300%
            safe_margin_factor = 3.0
            max_contracts = int(current_short_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
            
            if hedge_mode == "完全避險 (Neutral Hedge)":
                target_notional = long_equity * 2
                target_contracts = int(round(target_notional / (price_taiex * 50)))
                actual_contracts = min(target_contracts, max_contracts)
            else:
                actual_contracts = max_contracts
            
            contracts = actual_contracts
            
            if contracts > 0 and include_costs:
                trade_tax = price_taiex * 50 * contracts * cost_tax
                trade_fee = contracts * cost_fee
                trade_slippage = contracts * cost_slippage * 50
                
                this_trade_cost = trade_tax + trade_fee + trade_slippage
                current_short_capital -= this_trade_cost
                total_cost += this_trade_cost
            else:
                this_trade_cost = 0
            
            # Trade Record Logic
            if position == 1 and not in_trade: # Entry
                in_trade = True
                entry_date = date
                entry_price = price_taiex
                entry_capital = current_short_capital # Post-cost
                entry_long_equity = long_equity
                
            elif position == 0 and in_trade: # Exit
                in_trade = False
                exit_price = price_taiex
                points_diff = entry_price - exit_price
                ret = (entry_price - exit_price) / entry_price
                
                # Re-calc contracts for record (Entry Snapshot)
                # Re-calc contracts for record (Entry Snapshot)
                safe_margin_factor = 3.0
                max_contracts_entry = int(entry_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
                if hedge_mode == "完全避險 (Neutral Hedge)":
                    target_notional_entry = entry_long_equity * 2
                    target_contracts_entry = int(round(target_notional_entry / (entry_price * 50)))
                    actual_contracts_entry = min(target_contracts_entry, max_contracts_entry)
                else:
                    actual_contracts_entry = max_contracts_entry
                
                contracts_entry = actual_contracts_entry
                profit_twd = points_diff * 50 * contracts_entry
                
                # Effective Leverage = Notional / Capital
                entry_notional = contracts_entry * entry_price * 50
                eff_leverage = entry_notional / entry_capital if entry_capital > 0 else 0
                
                trades.append({
                    '進場日期': entry_date, '進場指數': entry_price,
                    '出場日期': date, '出場指數': exit_price,
                    '避險口數': contracts_entry, '獲利點數': points_diff,
                    '獲利金額 (TWD)': profit_twd, '報酬率': ret * eff_leverage
                })

        short_equity = current_short_capital
        total_equity = long_equity + short_equity
        
        # --- 4. Rebalancing ---
        current_month = date.month
        if do_rebalance and i > 0 and current_month != last_month:
            target_long = total_equity * rebalance_long_target
            target_short = total_equity * (1 - rebalance_long_target)
            
            shares_00631L = target_long / price_00631L
            current_short_capital = target_short
            
            long_equity = target_long
            short_equity = target_short
        
        last_month = current_month
        
        long_equity_arr.append(long_equity)
        short_equity_arr.append(short_equity)
        total_equity_arr.append(total_equity)
        
    # Handle Open Trade at End
    if in_trade:
        current_date = df.index[-1]
        current_price = df['TAIEX'].iloc[-1]
        points_diff = entry_price - current_price
        ret = (entry_price - current_price) / entry_price
        
        safe_margin_factor = 3.0
        max_contracts_entry = int(entry_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
        if hedge_mode == "完全避險 (Neutral Hedge)":
            target_notional_entry = entry_long_equity * 2
            target_contracts_entry = int(round(target_notional_entry / (entry_price * 50)))
            actual_contracts_entry = min(target_contracts_entry, max_contracts_entry)
        else:
            actual_contracts_entry = max_contracts_entry
            
        contracts_entry = actual_contracts_entry
        profit_twd = points_diff * 50 * contracts_entry
        
        entry_notional = contracts_entry * entry_price * 50
        eff_leverage = entry_notional / entry_capital if entry_capital > 0 else 0
        
        trades.append({
            '進場日期': entry_date, '進場指數': entry_price,
            '出場日期': current_date, '出場指數': current_price,
            '避險口數': contracts_entry, '獲利點數': points_diff,
            '獲利金額 (TWD)': profit_twd, '報酬率': ret * eff_leverage, '備註': '持倉中'
        })

    df['Long_Equity'] = long_equity_arr
    df['Short_Equity'] = short_equity_arr
    df['Total_Equity'] = total_equity_arr
    
    # Benchmark (Buy & Hold 00631L)
    df['Benchmark'] = (df['00631L'] / df['00631L'].iloc[0]) * initial_capital
    
    return df, trades, total_long_pnl, total_short_pnl, total_cost


# Sidebar Configuration
st.sidebar.header("參數設定")

# Data Source Selection
data_source = st.sidebar.selectbox(
    "資料來源",
    ("自動下載 (Yahoo Finance)", "本地檔案 (Excel/CSV)"),
    index=0
)

df = None

try:
    if data_source == "自動下載 (Yahoo Finance)":
        st.sidebar.info("正在從 Yahoo Finance 下載最新資料...")
        try:
            # Download 00631L
            df_00631L = yf.download("00631L.TW", start="2014-01-01", progress=False)
            
            if df_00631L.empty:
                raise Exception("Yahoo Finance 回傳空資料 (可能被限制存取)")

            # Fix for new yfinance structure (MultiIndex columns)
            if isinstance(df_00631L.columns, pd.MultiIndex):
                # If columns are MultiIndex, try to drop the Ticker level
                df_00631L.columns = df_00631L.columns.droplevel(1)
            
            df_00631L.reset_index(inplace=True)
            df_00631L = df_00631L[['Date', 'Close']]
            df_00631L.columns = ['Date', '00631L']
            
            # Download TAIEX (^TWII)
            df_taiex = yf.download("^TWII", start="2014-01-01", progress=False)

            if df_taiex.empty:
                raise Exception("Yahoo Finance 回傳空資料 (可能被限制存取)")

            if isinstance(df_taiex.columns, pd.MultiIndex):
                df_taiex.columns = df_taiex.columns.droplevel(1)

            df_taiex.reset_index(inplace=True)
            df_taiex = df_taiex[['Date', 'Close']]
            df_taiex.columns = ['Date', 'TAIEX']
            
            # Merge
            df = pd.merge(df_00631L, df_taiex, on='Date', how='inner')
            df.sort_values('Date', inplace=True)
            df.set_index('Date', inplace=True)
            
            st.sidebar.success(f"下載完成！資料日期：{df.index.min().date()} ~ {df.index.max().date()}")
            
        except Exception as e:
            st.error(f"下載失敗: {e}")
            st.warning("Yahoo Finance 可能對您的 IP 進行了速率限制 (Rate Limit)。請稍後再試，或切換至「本地檔案」模式。")
            if os.path.exists("00631L_2015-2025.xlsx") and os.path.exists("加權指數資料.xlsx"):
                st.info("💡 偵測到目錄下有本地資料，建議切換至「本地檔案」模式使用。")
            st.stop()
            
    else: # Local File
        # Check for local files
        default_00631L = "00631L_2015-2025.xlsx"
        default_taiex = "加權指數資料.xlsx"

        has_local_files = os.path.exists(default_00631L) and os.path.exists(default_taiex)

        if has_local_files:
            st.sidebar.success(f"已偵測到本地檔案: {default_00631L}, {default_taiex}")
            use_local = st.sidebar.checkbox("使用預設本地檔案", value=True)
        else:
            use_local = False

        if not use_local:
            uploaded_file_00631L = st.sidebar.file_uploader("上傳 00631L 檔案", type=["xlsx", "xls", "csv"])
            uploaded_file_taiex = st.sidebar.file_uploader("上傳 加權指數 檔案", type=["xlsx", "xls", "csv"])
        else:
            uploaded_file_00631L = None
            uploaded_file_taiex = None
            
        if use_local:
            df_00631L = pd.read_excel(default_00631L)
            df_taiex = pd.read_excel(default_taiex)
        elif uploaded_file_00631L and uploaded_file_taiex:
            # Load 00631L
            if uploaded_file_00631L.name.endswith('.csv'):
                df_00631L = pd.read_csv(uploaded_file_00631L)
            else:
                df_00631L = pd.read_excel(uploaded_file_00631L)
                
            # Load TAIEX
            if uploaded_file_taiex.name.endswith('.csv'):
                df_taiex = pd.read_csv(uploaded_file_taiex)
            else:
                df_taiex = pd.read_excel(uploaded_file_taiex)
        else:
            df_00631L = None
            df_taiex = None
        
        if df_00631L is not None and df_taiex is not None:
            # Preprocess and Merge
            def find_date_col(d):
                for col in d.columns:
                    if 'date' in str(col).lower() or '日期' in str(col):
                        return col
                return d.columns[0]
                
            date_col_1 = find_date_col(df_00631L)
            date_col_2 = find_date_col(df_taiex)
            
            df_00631L[date_col_1] = pd.to_datetime(df_00631L[date_col_1])
            df_taiex[date_col_2] = pd.to_datetime(df_taiex[date_col_2])
            
            def find_close_col(d):
                for col in d.columns:
                    if 'close' in str(col).lower() or '收盤' in str(col) or '價' in str(col):
                        return col
                return d.columns[1]
                
            price_col_1 = find_close_col(df_00631L)
            price_col_2 = find_close_col(df_taiex)
            
            df_00631L = df_00631L[[date_col_1, price_col_1]].rename(columns={date_col_1: 'Date', price_col_1: '00631L'})
            df_taiex = df_taiex[[date_col_2, price_col_2]].rename(columns={date_col_2: 'Date', price_col_2: 'TAIEX'})
            
            df = pd.merge(df_00631L, df_taiex, on='Date', how='inner')
            df.sort_values('Date', inplace=True)
            df.set_index('Date', inplace=True)

except Exception as e:
    st.error(f"讀取檔案時發生錯誤: {e}")

if df is not None:
    # Sidebar Parameters
    initial_capital = st.sidebar.number_input("初始總資金 (TWD)", value=1000000, step=100000)
    if 'ma_period' not in st.session_state:
        st.session_state['ma_period'] = 13

    ma_period = st.sidebar.number_input("加權指數均線週期 (MA)", value=st.session_state['ma_period'], step=1, key='ma_input')
    
    # Sync session state if changed manually
    if ma_period != st.session_state['ma_period']:
        st.session_state['ma_period'] = ma_period

    # Strategy Allocation
    st.sidebar.subheader("資金分配與策略")
    
    do_rebalance = st.sidebar.checkbox("啟用每月動態平衡 (Monthly Rebalancing)", value=True, help="每月初將資金重新分配，以解決資產增長後避險不足的問題。")

    if do_rebalance:
        rebalance_long_target = st.sidebar.slider("動態平衡：做多部位目標比例 (%)", min_value=10, max_value=100, value=90, step=5) / 100.0
        long_allocation_pct = rebalance_long_target # Sync initial with target
    else:
        rebalance_long_target = 0.5
        long_allocation_pct = 0.5

    short_allocation_pct = 1 - long_allocation_pct
    st.sidebar.write(f"初始做多部位 (00631L): {long_allocation_pct*100:.0f}%")
    st.sidebar.write(f"初始做空部位 (小台): {short_allocation_pct*100:.0f}%")

    # Removed short_leverage slider
    
    margin_per_contract = st.sidebar.number_input("小台單口保證金 (TWD)", value=85000, step=1000)

    hedge_mode = st.sidebar.radio(
        "避險策略模式",
        ("積極做空 (Aggressive)", "完全避險 (Neutral Hedge)"),
        index=1, # Default to Neutral
        help="積極做空：使用可用做空資金，但限制風險指標不低於 300%。\n完全避險：口數上限為對沖 00631L 曝險 (2倍市值)，且受風險指標 300% 限制。"
    )

    # do_rebalance moved up
    
    # Transaction Costs
    st.sidebar.subheader("交易成本設定")
    cost_fee = st.sidebar.number_input("單邊手續費 (TWD/口)", value=40, step=10)
    cost_tax = st.sidebar.number_input("交易稅率", value=0.00002, step=0.00001, format="%.5f")
    cost_slippage = st.sidebar.number_input("滑價 (點數)", value=1, step=1)
    include_costs = st.sidebar.checkbox("是否計入交易成本", value=True)
    
    # st.sidebar.subheader("風險控管設定") 
    # Moved margin_per_contract up

    # Date Range Filter
    if df.empty:
        st.warning("⚠️ 載入的資料為空，請檢查資料來源或日期範圍。")
        st.stop()
    else:
        min_date = df.index.min()
        max_date = df.index.max()
        
        if pd.isna(min_date) or pd.isna(max_date):
            st.error("⚠️ 資料日期格式錯誤 (NaT)，無法進行回測。")
            st.stop()
        else:
            start_date, end_date = st.sidebar.date_input(
                "選擇回測日期範圍",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
    
    # Filter data
    mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
    df_test_raw = df.loc[mask].copy()
    
    if len(df_test_raw) == 0:
        st.warning("選定範圍內無資料")
    else:
        # --- Run Backtest ---
        df_test, trades, total_long_pnl, total_short_pnl, total_cost = run_backtest(
            df_test_raw, ma_period, initial_capital, long_allocation_pct, short_allocation_pct,
            margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
            cost_fee, cost_tax, cost_slippage, include_costs
        )
        
        # --- Tabs ---
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 總覽", "📈 績效分析", "📅 週期分析", "📋 交易明細", "🔭 最新訊號判斷", "🎯 參數敏感度", "🎮 真實操作模擬"])

        # --- Tab 5: Latest Signal ---
        with tab5:
            st.subheader("🔭 最新市場狀態與操作建議")
            
            last_row = df_test.iloc[-1]
            last_date = df_test.index[-1]
            last_close = last_row['TAIEX']
            last_ma = last_row['MA']
            last_00631L = last_row['00631L']
            
            current_short_equity = df_test['Short_Equity'].iloc[-1]
            shares_00631L = df_test['Long_Equity'].iloc[-1] / last_00631L # Approx shares
            
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
            
            st.subheader("💰 目前部位損益試算")
            
            col_s1, col_s2 = st.columns(2)
            
            # 1. 00631L Status
            with col_s1:
                st.markdown("#### 🐂 00631L (做多部位)")
                curr_val_00631L = df_test['Long_Equity'].iloc[-1]
                st.write(f"**目前市值**：{curr_val_00631L:,.0f} TWD")
                st.write(f"**約當大盤曝險**：{curr_val_00631L * 2:,.0f} TWD (2倍槓桿)")
            
            # 2. Short Leg Status
            with col_s2:
                st.markdown("#### 🐻 小台 (做空避險部位)")
                
                is_holding_short = last_row['Position'] == 1
                
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
                    
                    # Find Entry
                    current_trade_entry_index = -1
                    for i in range(len(df_test)-1, -1, -1):
                        if df_test['Position'].iloc[i] == 0:
                            current_trade_entry_index = i + 1
                            break
                    if current_trade_entry_index == -1: current_trade_entry_index = 0
                    
                    entry_row = df_test.iloc[current_trade_entry_index]
                    entry_date = df_test.index[current_trade_entry_index]
                    entry_price = entry_row['TAIEX']
                    entry_short_capital = entry_row['Short_Equity']
                    entry_long_equity = entry_row['Long_Equity']
                    entry_price_00631L = entry_row['00631L']
                    
                    # Calculate Contracts
                    safe_margin_factor = 3.0
                    max_contracts = int(entry_short_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
                    if hedge_mode == "完全避險 (Neutral Hedge)":
                        target_notional = entry_long_equity * 2
                        target_contracts = int(round(target_notional / (entry_price * 50)))
                        actual_contracts = min(target_contracts, max_contracts)
                    else:
                        actual_contracts = max_contracts
                        
                    contracts = actual_contracts
                    
                    # Current Short P&L
                    points_diff = entry_price - last_close
                    profit_twd = points_diff * 50 * contracts
                    ret = (entry_price - last_close) / entry_price
                    
                    entry_notional = contracts * entry_price * 50
                    eff_leverage = entry_notional / entry_short_capital if entry_short_capital > 0 else 0
                    roi = ret * eff_leverage
                    
                    # Current 00631L P&L
                    ret_00631L = (last_00631L - entry_price_00631L) / entry_price_00631L
                    profit_00631L_period = entry_long_equity * ret_00631L
                    
                    net_pnl = profit_twd + profit_00631L_period
                    
                    st.markdown("---")
                    st.subheader("⚖️ 避險成效分析 (本次空單持有期間)")
                    
                    col_h1, col_h2, col_h3 = st.columns(3)
                    
                    with col_h1:
                        st.markdown("#### 🐻 小台 (空單)")
                        st.write(f"**進場日期**：{entry_date.strftime('%Y-%m-%d')}")
                        st.write(f"**避險口數**：{contracts} 口")
                        st.metric("進場指數", f"{entry_price:,.0f}")
                        st.metric("目前指數", f"{last_close:,.0f}", delta=f"{last_close - entry_price:,.0f}", delta_color="inverse")
                        st.metric("空單損益 (TWD)", f"{profit_twd:,.0f}", delta=f"{roi:.2%}")
                        
                        # Risk Indicator
                        st.markdown("---")
                        st.markdown("#### ⚠️ 風險指標 (Risk Indicator)")
                        
                        current_short_equity_val = df_test['Short_Equity'].iloc[-1]
                        required_margin = contracts * margin_per_contract
                        if required_margin > 0:
                            risk_ratio = current_short_equity_val / required_margin
                        else:
                            risk_ratio = 999 # Safe
                            
                        risk_color = "red" if risk_ratio < 3.0 else "green"
                        risk_icon = "🚨" if risk_ratio < 3.0 else "✅"
                        
                        # Vertical Stack for better visibility
                        st.metric("做空帳戶資金 (權益數)", f"{current_short_equity_val:,.0f}")
                        st.metric("所需保證金", f"{required_margin:,.0f}", help=f"口數 {contracts} x 保證金 {margin_per_contract:,.0f}")
                        
                        # Risk Ratio
                        st.markdown(f"**風險指標 (目標 > 300%)**")
                        st.markdown(f"<div style='background-color:#f0f2f6;padding:10px;border-radius:5px;text-align:center;'><span style='color:{risk_color};font-size:2em;font-weight:bold'>{risk_ratio:.0%} {risk_icon}</span></div>", unsafe_allow_html=True)
                    
                    with col_h2:
                        st.markdown("#### 🐂 00631L (多單)")
                        st.write(f"**對照期間**：同左")
                        st.metric("進場價格", f"{entry_price_00631L:.2f}")
                        st.metric("目前價格", f"{last_00631L:.2f}", delta=f"{last_00631L - entry_price_00631L:.2f}")
                        st.metric("多單損益 (預估)", f"{profit_00631L_period:,.0f}", delta=f"{ret_00631L:.2%}")
                        
                    with col_h3:
                        st.markdown("#### 💰 總合損益 (Net)")
                        if net_pnl > 0:
                            status_text = "✅ 避險/獲利成功"
                            status_color = "red"
                        else:
                            status_text = "🔻 總合虧損"
                            status_color = "green"
                        st.markdown(f"**狀態**：<span style='color:{status_color};font-weight:bold;font-size:1.2em'>{status_text}</span>", unsafe_allow_html=True)
                        st.metric("總合損益 (TWD)", f"{net_pnl:,.0f}", delta=f"{net_pnl/initial_capital:.2%} (佔初始資金)")

                else:
                    st.write("**目前狀態**：⚪ 空手 (無避險)")
                    st.write(f"**明日操作指引**：{'續抱空單' if is_bearish else '維持空手'}")

        with tab1:
            st.subheader("回測結果總覽")
            
            final_equity = df_test['Total_Equity'].iloc[-1]
            total_ret = (final_equity - initial_capital) / initial_capital
            benchmark_ret = (df_test['Benchmark'].iloc[-1] - initial_capital) / initial_capital
            
            col1, col2, col3 = st.columns(3)
            with col1: metric_card("期末總資產", f"{final_equity:,.0f}")
            with col2: metric_card("總報酬率", f"{total_ret:.2%}", delta=f"{total_ret:.2%}")
            with col3: metric_card("交易天數", f"{len(df_test)}")
            
            col4, col5, col6 = st.columns(3)
            with col4: metric_card("🐂 做多總獲利", f"{total_long_pnl:,.0f}", delta=f"{total_long_pnl/initial_capital:.1%}")
            with col5: metric_card("🐻 做空總獲利", f"{total_short_pnl:,.0f}", delta=f"{total_short_pnl/initial_capital:.1%}")
            with col6: metric_card("💸 總交易成本", f"{total_cost:,.0f}", delta=f"-{total_cost/initial_capital:.1%}", delta_color="inverse")
            
            # Equity Curve
            st.subheader("資產曲線")
            fig_equity = go.Figure()
            fig_equity.add_trace(go.Scatter(x=df_test.index, y=df_test['Total_Equity'], mode='lines', name='總資產 (策略)', line=dict(width=3, color='#d32f2f')))
            fig_equity.add_trace(go.Scatter(x=df_test.index, y=df_test['Benchmark'], mode='lines', name='Buy & Hold 00631L (對照)', line=dict(width=3, color='#9e9e9e')))
            fig_equity.add_trace(go.Scatter(x=df_test.index, y=df_test['Long_Equity'], mode='lines', name='做多部位', line=dict(width=1.5, dash='dot')))
            fig_equity.add_trace(go.Scatter(x=df_test.index, y=df_test['Short_Equity'], mode='lines', name='做空部位', line=dict(width=1.5, dash='dot')))
            
            fig_equity.update_layout(
                title='策略 vs. 純買進持有 (00631L)',
                xaxis_title='日期',
                yaxis_title='金額 (TWD)',
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white",
                height=600
            )
            st.plotly_chart(fig_equity, use_container_width=True)
            
            # Trend Chart
            st.subheader("最近 100 日多空趨勢分析")
            df_recent = df_test.iloc[-100:].copy()
            df_recent['Color'] = df_recent['Position'].apply(lambda x: 'green' if x == 1 else 'red')
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=df_recent.index,
                y=df_recent['TAIEX'],
                marker_color=df_recent['Color'],
                name='趨勢'
            ))
            min_y = df_recent['TAIEX'].min() * 0.95
            max_y = df_recent['TAIEX'].max() * 1.05
            fig_trend.update_layout(
                title='最近 100 日加權指數多空趨勢 (紅=多方/綠=空方避險)',
                yaxis_range=[min_y, max_y],
                showlegend=False,
                xaxis_title="日期",
                yaxis_title="加權指數",
                template="plotly_white"
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        with tab2:
            st.subheader("績效統計")
            
            # MDD (Strategy)
            equity_curve = df_test['Total_Equity']
            drawdown = (equity_curve - equity_curve.cummax()) / equity_curve.cummax()
            max_drawdown = drawdown.min()
            
            # MDD (Benchmark - No Hedge)
            benchmark_curve = df_test['Benchmark']
            benchmark_drawdown = (benchmark_curve - benchmark_curve.cummax()) / benchmark_curve.cummax()
            benchmark_max_drawdown = benchmark_drawdown.min()
            
            taiex_curve = df_test['TAIEX']
            taiex_drawdown = (taiex_curve - taiex_curve.cummax()) / taiex_curve.cummax()
            taiex_max_drawdown = taiex_drawdown.min()
            
            # Trade Stats
            if trades:
                df_trades_stats = pd.DataFrame(trades)
                win_rate = (df_trades_stats['獲利金額 (TWD)'] > 0).mean()
                avg_profit = df_trades_stats['獲利金額 (TWD)'].mean()
                total_trades_count = len(df_trades_stats)
            else:
                win_rate = 0
                avg_profit = 0
                total_trades_count = 0
            
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            with col_p1: metric_card("策略最大回撤 (含避險)", f"{max_drawdown:.2%}", delta_color="inverse")
            with col_p2: metric_card("未避險最大回撤 (00631L)", f"{benchmark_max_drawdown:.2%}", delta=f"{benchmark_max_drawdown - max_drawdown:.2%}", delta_color="inverse")
            with col_p3: metric_card("做空交易次數", f"{total_trades_count}")
            with col_p4: metric_card("做空勝率", f"{win_rate:.2%}")
            
            st.subheader("回撤曲線 (Drawdown)")
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(x=drawdown.index, y=drawdown, fill='tozeroy', line=dict(color='red'), name='策略回撤 (含避險)'))
            fig_dd.add_trace(go.Scatter(x=benchmark_drawdown.index, y=benchmark_drawdown, line=dict(color='gray', dash='dot'), name='未避險回撤 (00631L)'))
            
            fig_dd.update_layout(
                title='總資產回撤幅度比較', 
                yaxis_title='回撤 %', 
                hovermode="x unified", 
                template="plotly_white",
                yaxis=dict(tickformat=".0%"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_dd, use_container_width=True)

        with tab3:
            st.subheader("年度報酬率與風險分析")
            df_test['Year'] = df_test.index.year
            
            yearly_stats = df_test.groupby('Year').agg({
                'Total_Equity': ['first', 'last'],
                'Benchmark': ['first', 'last']
            })
            
            yearly_ret = pd.DataFrame()
            yearly_ret['年化報酬率'] = ((yearly_stats['Total_Equity']['last'] - yearly_stats['Total_Equity']['first']) / yearly_stats['Total_Equity']['first']) * 100
            yearly_ret['Benchmark 報酬率'] = ((yearly_stats['Benchmark']['last'] - yearly_stats['Benchmark']['first']) / yearly_stats['Benchmark']['first']) * 100
            yearly_ret['超額報酬 (Alpha)'] = yearly_ret['年化報酬率'] - yearly_ret['Benchmark 報酬率']
            
            # Yearly MDD
            yearly_mdd = []
            for year in yearly_ret.index:
                df_year = df_test[df_test['Year'] == year]
                eq = df_year['Total_Equity']
                dd = (eq - eq.cummax()) / eq.cummax()
                yearly_mdd.append(dd.min() * 100)
            yearly_ret['策略最大回撤 (MDD)'] = yearly_mdd
            
            # Add Average Row
            avg_row = yearly_ret.mean()
            yearly_ret.loc['平均值 (Avg)'] = avg_row
            
            def highlight_average(row):
                if row.name == '平均值 (Avg)':
                    return ['background-color: #fff8e1; color: #bf360c; font-weight: bold'] * len(row)
                return [''] * len(row)
            
            st.dataframe(
                yearly_ret.style.apply(highlight_average, axis=1).format("{:.2f} %"),
                use_container_width=True,
                column_config={
                    "年化報酬率": st.column_config.NumberColumn(format="%.2f %%"),
                    "Benchmark 報酬率": st.column_config.NumberColumn(format="%.2f %%"),
                    "超額報酬 (Alpha)": st.column_config.NumberColumn(format="%.2f %%"),
                    "策略最大回撤 (MDD)": st.column_config.ProgressColumn(format="%.2f %%", min_value=-100, max_value=0),
                }
            )
            
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-size: 0.9em; color: #555;">
            <b>指標說明：</b>
            <ul style="margin-bottom: 0;">
                <li><b>年化報酬率</b>: 策略在該年度的總投資報酬率 (Total Return)</li>
                <li><b>Benchmark 報酬率</b>: 單純買進持有 00631L (Buy & Hold) 的年度報酬率</li>
                <li><b>超額報酬 (Alpha)</b>: 策略報酬率減去 Benchmark 報酬率的差額，正值代表跑贏大盤</li>
                <li><b>策略最大回撤 (MDD)</b>: 該年度策略資產從最高點回落的最大幅度 (風險指標)</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.subheader("月度報酬率分析 (總資產)")
            df_test['Month'] = df_test.index.to_period('M')
            monthly_stats = df_test.groupby('Month')['Total_Equity'].agg(['first', 'last'])
            monthly_stats['Return'] = (monthly_stats['last'] - monthly_stats['first']) / monthly_stats['first']
            monthly_stats['Year'] = monthly_stats.index.year
            monthly_stats['Month_Num'] = monthly_stats.index.month
            pivot_ret = monthly_stats.pivot(index='Year', columns='Month_Num', values='Return')
            pivot_ret.columns = [f"{i}月" for i in range(1, 13)]
            
            def color_ret(val):
                if pd.isna(val): return ''
                color = 'red' if val > 0 else 'green'
                return f'color: {color}'
                
            st.dataframe(pivot_ret.style.format("{:.2%}").map(color_ret), use_container_width=True)

        with tab4:
            st.subheader("📋 交易明細")
            if trades:
                df_trades = pd.DataFrame(trades)
                df_trades['進場日期'] = df_trades['進場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
                df_trades['出場日期'] = df_trades['出場日期'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x)
                
                def color_pnl(val):
                    color = 'red' if val > 0 else 'green'
                    return f'color: {color}'
                
                st.dataframe(df_trades.style.applymap(color_pnl, subset=['獲利金額 (TWD)', '報酬率'])
                             .format({'進場指數': '{:,.0f}', '出場指數': '{:,.0f}', '避險口數': '{:.2f}', 
                                      '獲利點數': '{:,.0f}', '獲利金額 (TWD)': '{:,.0f}', '報酬率': '{:.2%}'}),
                             use_container_width=True)
                
                # Annual Short P&L Summary
                st.divider()
                st.subheader("📅 每年做空避險損益統計")
                
                df_trades_raw = pd.DataFrame(trades)
                df_trades_raw['Year'] = pd.to_datetime(df_trades_raw['出場日期']).dt.year
                annual_short_pnl = df_trades_raw.groupby('Year')['獲利金額 (TWD)'].sum().reset_index()
                annual_short_pnl.columns = ['年份', '做空總損益 (TWD)']
                
                # Add Trade Count per year
                annual_counts = df_trades_raw.groupby('Year').size().reset_index(name='交易次數')
                annual_counts.columns = ['年份', '交易次數'] # Rename explicitly
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
                
                csv_equity = df_test.to_csv().encode('utf-8-sig')
                col_ex2.download_button(
                    label="下載每日資產權益 (CSV)",
                    data=csv_equity,
                    file_name='daily_equity.csv',
                    mime='text/csv',
                )
            else:
                st.info("區間內無做空交易")

        with tab6:
            st.subheader("🎯 參數敏感度分析 (MA Sensitivity)")
            
            # Show Date Range Context
            if not df_test_raw.empty:
                sa_start_date = df_test_raw.index.min().date()
                sa_end_date = df_test_raw.index.max().date()
                sa_days = (sa_end_date - sa_start_date).days
                sa_years = sa_days / 365.25
                st.info(f"此功能將測試不同均線週期對策略績效的影響。\n\n**目前回測區間**：{sa_start_date} ~ {sa_end_date} (約 {sa_years:.1f} 年)")
            else:
                st.info("此功能將測試不同均線週期對策略績效的影響。")
            
            col_sa1, col_sa2 = st.columns(2)
            ma_start = col_sa1.number_input("MA 起始", value=5, step=1)
            ma_end = col_sa2.number_input("MA 結束", value=60, step=1)
            ma_step = st.slider("間隔 (Step)", 1, 10, 2)
            
            if st.button("開始分析"):
                progress_bar = st.progress(0)
                results = []
                ma_range = range(ma_start, ma_end + 1, ma_step)
                total_steps = len(ma_range)
                
                for idx, ma in enumerate(ma_range):
                    # Run Backtest (Silent)
                    _df, _trades, _lp, _sp, _cost = run_backtest(
                        df_test_raw, ma, initial_capital, long_allocation_pct, short_allocation_pct,
                        margin_per_contract, hedge_mode, do_rebalance, rebalance_long_target,
                        cost_fee, cost_tax, cost_slippage, include_costs
                    )
                    
                    final_eq = _df['Total_Equity'].iloc[-1]
                    ret = (final_eq - initial_capital) / initial_capital
                    
                    eq_curve = _df['Total_Equity']
                    mdd = ((eq_curve - eq_curve.cummax()) / eq_curve.cummax()).min()
                    
                    results.append({
                        'MA': ma,
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
                benchmark_start = df_test_raw['00631L'].iloc[0]
                benchmark_end = df_test_raw['00631L'].iloc[-1]
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

        with tab7:
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
                real_shares_00631L = st.number_input("目前 00631L 持有股數 (Shares)", value=default_settings["shares_00631L"], step=1000)
                real_short_capital = st.number_input("目前 期貨保證金專戶餘額 (權益數 TWD)", value=default_settings["short_capital"], step=10000)
                real_held_contracts = st.number_input("目前 持有小台口數 (空單)", value=default_settings["held_contracts"], step=1)
                
                # Save Settings Button (Implicit or Explicit? Let's do auto-save on change if possible, but Streamlit re-runs. 
                # Let's save at the end of the script or just save now)
                current_settings = {
                    "shares_00631L": real_shares_00631L,
                    "short_capital": real_short_capital,
                    "held_contracts": real_held_contracts
                }
                if current_settings != default_settings:
                    with open(SETTINGS_FILE, "w") as f:
                        json.dump(current_settings, f)
                
                st.markdown("#### 2. 確認市場數據 (預設為最新)")
                sim_last_close = st.number_input("加權指數收盤價", value=float(last_close), step=10.0)
                sim_ma = st.number_input(f"目前 {ma_period}MA", value=float(last_ma), step=10.0)
                
                # Auto-calc Value
                sim_price_00631L = last_00631L # Use latest from data
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
                sim_max_contracts = int(real_short_capital / (safe_margin_factor * margin_per_contract)) if margin_per_contract > 0 else 0
                
                if sim_is_bearish:
                    if hedge_mode == "完全避險 (Neutral Hedge)":
                        sim_target_notional = real_long_value * 2
                        sim_target_contracts_raw = int(round(sim_target_notional / (sim_last_close * 50)))
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
                
                st.metric("建議操作", action_msg, help=action_desc)
                st.write(f"**目標口數**：{sim_target_contracts} 口")
                st.write(f"**策略邏輯**：{hedge_reason}")
                
                st.divider()
                
                # Risk Preview
                st.markdown("#### ⚠️ 調整後風險預估")
                sim_required_margin = sim_target_contracts * margin_per_contract
                if sim_required_margin > 0:
                    sim_risk_ratio = real_short_capital / sim_required_margin
                else:
                    sim_risk_ratio = 999
                
                sim_risk_color = "red" if sim_risk_ratio < 3.0 else "green"
                st.metric("預估風險指標", f"{sim_risk_ratio:.0%}", delta="目標 > 300%")
                if sim_risk_ratio < 3.0 and sim_target_contracts > 0:
                    st.warning("⚠️ 注意：即使調整後，風險指標仍低於 300%，建議補錢或減少口數。")
                elif sim_target_contracts == 0:
                    st.success("目前無部位，無風險。")
                else:
                    st.success("風險指標安全。")

else:
    st.info("請上傳 00631L 和 加權指數 的 Excel 檔案，或確認目錄下是否有預設檔案。")
