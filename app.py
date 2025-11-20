import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import yfinance as yf

st.set_page_config(page_title="台灣五十正2 & 微台 Backtest", layout="wide")

st.title("台灣五十正2 (00631L) & 微台指 (Micro Tai) 策略回測")

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
            df_00631L.reset_index(inplace=True)
            df_00631L = df_00631L[['Date', 'Close']]
            df_00631L.columns = ['Date', '00631L']
            
            # Download TAIEX (^TWII)
            df_taiex = yf.download("^TWII", start="2014-01-01", progress=False)
            df_taiex.reset_index(inplace=True)
            df_taiex = df_taiex[['Date', 'Close']]
            df_taiex.columns = ['Date', 'TAIEX']
            
            # Merge
            df = pd.merge(df_00631L, df_taiex, on='Date', how='inner')
            df.sort_values('Date', inplace=True)
            df.set_index('Date', inplace=True)
            
            st.sidebar.success(f"下載完成！資料日期：{df.index.min().date()} ~ {df.index.max().date()}")
            
        except Exception as e:
            st.sidebar.error(f"下載失敗: {e}")
            
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
    # Sidebar Parameters (Restored)
    initial_capital = st.sidebar.number_input("初始總資金 (TWD)", value=1000000, step=100000)
    ma_period = st.sidebar.number_input("加權指數均線週期 (MA)", value=13, step=1)

    # Strategy Allocation
    st.sidebar.subheader("資金分配與策略")
    long_allocation_pct = 0.5
    short_allocation_pct = 0.5
    st.sidebar.write(f"初始做多部位 (00631L): {long_allocation_pct*100}%")
    st.sidebar.write(f"初始做空部位 (微台): {short_allocation_pct*100}%")

    short_leverage = st.sidebar.slider("微台做空槓桿倍數 (最大資金倍數)", min_value=1.0, max_value=10.0, value=5.0, step=0.1, help="設定微台做空時的『最大』槓桿倍數。")

    hedge_mode = st.sidebar.radio(
        "避險策略模式",
        ("積極做空 (Aggressive)", "完全避險 (Neutral Hedge)"),
        help="積極做空：使用所有可用資金 x 槓桿倍數進行放空 (可能變成淨空單)。\n完全避險：僅放空與 00631L 曝險等值 (2倍市值) 的部位，追求市場中性。"
    )

    do_rebalance = st.sidebar.checkbox("啟用每月動態平衡 (Monthly Rebalancing)", value=True, help="每月初將資金重新分配，以解決資產增長後避險不足的問題。")

    if do_rebalance:
        rebalance_long_target = st.sidebar.slider("動態平衡：做多部位目標比例 (%)", min_value=10, max_value=90, value=70, step=5) / 100.0
        rebalance_short_target = 1.0 - rebalance_long_target
        st.sidebar.write(f"每月初將調整為：做多 {rebalance_long_target*100:.0f}% / 做空(現金) {rebalance_short_target*100:.0f}%")
    else:
        rebalance_long_target = 0.5
        rebalance_short_target = 0.5

    # Date Range Filter
    min_date = df.index.min()
    max_date = df.index.max()
    
    start_date, end_date = st.sidebar.date_input(
        "選擇回測日期範圍",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Filter data
    mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
    df_test = df.loc[mask].copy()
    
    if len(df_test) == 0:
        st.warning("選定範圍內無資料")
    else:
        # Calculate MA
        df_test['MA'] = df_test['TAIEX'].rolling(window=ma_period).mean()
        
        # --- Strategy Logic (Loop-based for Rebalancing) ---
        
        # Initialize columns
        df_test['Position'] = (df_test['TAIEX'] < df_test['MA']).shift(1).fillna(0) # 1 = Short, 0 = Flat
        
        # Define initial capitals for reference in Tabs
        long_capital = initial_capital * long_allocation_pct
        short_capital_initial = initial_capital * short_allocation_pct
        
        # Arrays to store results
        long_equity_arr = []
        short_equity_arr = []
        total_equity_arr = []
        
        # P&L Accumulators
        total_long_pnl = 0
        total_short_pnl = 0
        
        # Initial State
        current_long_capital = long_capital
        current_short_capital = short_capital_initial
        
        # Buy initial shares of 00631L
        initial_price_00631L = df_test['00631L'].iloc[0]
        shares_00631L = current_long_capital / initial_price_00631L
        
        last_month = df_test.index[0].month
        
        # Iterate
        for i in range(len(df_test)):
            date = df_test.index[i]
            price_00631L = df_test['00631L'].iloc[i]
            price_taiex = df_test['TAIEX'].iloc[i]
            position = df_test['Position'].iloc[i] # Position determined by yesterday's signal
            
            # 1. Calculate Equity BEFORE Rebalancing
            # Long Leg
            long_equity = shares_00631L * price_00631L
            
            if i > 0:
                # Long P&L (Daily)
                prev_price_00631L = df_test['00631L'].iloc[i-1]
                daily_long_pnl = shares_00631L * (price_00631L - prev_price_00631L)
                total_long_pnl += daily_long_pnl
                
                # Short Leg
                prev_taiex = df_test['TAIEX'].iloc[i-1]
                idx_ret = (price_taiex - prev_taiex) / prev_taiex
                
                # Short P&L
                if position == 1:
                    # Determine Notional Value based on Mode
                    max_short_notional = current_short_capital * short_leverage
                    
                    if hedge_mode == "完全避險 (Neutral Hedge)":
                        # Target: Long Equity * 2 (to offset 2x leverage of 00631L)
                        target_short_notional = long_equity * 2
                        # Cap at max capacity
                        actual_short_notional = min(target_short_notional, max_short_notional)
                    else:
                        # Aggressive: Use full capacity
                        actual_short_notional = max_short_notional
                    
                    # Profit = Notional * (-1 * idx_ret)
                    short_pnl = actual_short_notional * (-1 * idx_ret)
                    current_short_capital += short_pnl
                    total_short_pnl += short_pnl
            
            short_equity = current_short_capital
            total_equity = long_equity + short_equity
            
            # 2. Rebalancing (Start of Month)
            current_month = date.month
            if do_rebalance and i > 0 and current_month != last_month:
                # Rebalance to Target Ratio
                target_long = total_equity * rebalance_long_target
                target_short = total_equity * rebalance_short_target
                
                # Adjust Shares
                shares_00631L = target_long / price_00631L
                
                # Adjust Short Capital
                current_short_capital = target_short
                
                # Update Equities for record
                long_equity = target_long
                short_equity = target_short
            
            last_month = current_month
            
            # Store
            long_equity_arr.append(long_equity)
            short_equity_arr.append(short_equity)
            total_equity_arr.append(total_equity)
            
        # Assign back to DataFrame
        df_test['Long_Equity'] = long_equity_arr
        df_test['Short_Equity'] = short_equity_arr
        df_test['Total_Equity'] = total_equity_arr
        
        # Recalculate Short_Leg_Ret for downstream compatibility (approximate)
        df_test['Short_Leg_Ret'] = df_test['Short_Equity'].pct_change().fillna(0)

        # --- Tabs ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 總覽", "📈 績效分析", "📅 週期分析", "📋 交易明細", "🔭 最新訊號判斷"])

        # --- Tab 5: Latest Signal ---
        with tab5:
            st.subheader("🔭 最新市場狀態與操作建議")
            
            last_row = df_test.iloc[-1]
            last_date = df_test.index[-1]
            last_close = last_row['TAIEX']
            last_ma = last_row['MA']
            last_00631L = last_row['00631L']
            
            # Get CURRENT available short capital (from the end of backtest)
            current_short_equity = df_test['Short_Equity'].iloc[-1]
            current_long_equity = df_test['Long_Equity'].iloc[-1]
            
            # Determine Signal for "Tomorrow" (based on Today's Close)
            is_bearish = last_close < last_ma
            signal_text = "空方 (跌破均線)" if is_bearish else "多方 (站上均線)"
            action_text = "⚠️ 啟動避險 (做空微台)" if is_bearish else "✅ 僅持有做多部位 (00631L)"
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
                # Calculate current P&L
                curr_val_00631L = shares_00631L * last_00631L
                
                st.write(f"**持有股數**：{shares_00631L:,.0f} 股")
                st.write(f"**目前市值**：{curr_val_00631L:,.0f} TWD")
                st.write(f"**約當大盤曝險**：{curr_val_00631L * 2:,.0f} TWD (2倍槓桿)")
                st.caption("(因有每月動態平衡，累積獲利請參考總覽頁面)")
            
            # 2. Short Leg Status
            with col_s2:
                st.markdown("#### 🐻 微台 (做空避險部位)")
                
                # Current Holding Status (Today)
                is_holding_short = last_row['Position'] == 1
                
                if is_holding_short:
                    st.write("**目前狀態**：🔴 持有空單中")
                else:
                    st.write("**目前狀態**：⚪ 空手 (無避險)")
                
                st.markdown("---")
                st.markdown("**明日操作指引**")
                
                if is_bearish:
                    # Need to Hedge
                    # Use CURRENT Short Equity * Leverage
                    contracts_needed = (current_short_equity * short_leverage) / (last_close * 10)
                    st.write(f"**建議動作**：{'續抱空單' if is_holding_short else '建立空單'}")
                    st.write(f"**建議口數**：{contracts_needed:.2f} 口")
                    st.caption(f"(基於避險資金 {current_short_equity:,.0f} x 槓桿 {short_leverage}倍 / (指數 {last_close:,.0f} * 10))")
                else:
                    # No Hedge
                    st.write(f"**建議動作**：{'平倉空單 (若持有)' if is_holding_short else '維持空手'}")
                    st.write("**建議口數**：0 口")
        
        with tab1:
            st.subheader("回測結果總覽")
            
            # Summary Metrics
            final_equity = df_test['Total_Equity'].iloc[-1]
            total_ret = (final_equity - initial_capital) / initial_capital
            
            col1, col2, col3 = st.columns(3)
            col1.metric("期末總資產", f"{final_equity:,.0f}")
            col2.metric("總報酬率", f"{total_ret:.2%}")
            col3.metric("交易天數", f"{len(df_test)}")
            
            col4, col5 = st.columns(2)
            col4.metric("🐂 做多總獲利 (00631L)", f"{total_long_pnl:,.0f}", delta=f"{total_long_pnl/initial_capital:.1%}")
            col5.metric("🐻 做空總獲利 (微台)", f"{total_short_pnl:,.0f}", delta=f"{total_short_pnl/initial_capital:.1%}")
            
            # Equity Curve
            st.line_chart(df_test[['Total_Equity', 'Long_Equity', 'Short_Equity']])
            
            # Recent 100 Days Trend
            st.subheader("最近 100 日多空趨勢分析")
            df_recent = df_test.iloc[-100:].copy()
            
            # Count Long/Short days
            short_days = df_recent[df_recent['Position'] == 1].shape[0]
            long_days = 100 - short_days
            
            c1, c2 = st.columns(2)
            c1.metric("多方天數 (僅持有 00631L)", f"{long_days} 天")
            c2.metric("空方天數 (啟動避險)", f"{short_days} 天")
            
            # Bar Chart for Trend
            df_recent['Color'] = df_recent['Position'].apply(lambda x: 'green' if x == 1 else 'red')
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=df_recent.index,
                y=df_recent['TAIEX'],
                marker_color=df_recent['Color'],
                name='Trend'
            ))
            
            min_y = df_recent['TAIEX'].min() * 0.95
            max_y = df_recent['TAIEX'].max() * 1.05
            
            fig_trend.update_layout(
                title='最近 100 日加權指數多空趨勢 (紅=多方/綠=空方避險)',
                yaxis_range=[min_y, max_y],
                showlegend=False,
                xaxis_title="日期",
                yaxis_title="加權指數"
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # --- Tab 2: Performance Analysis ---
        with tab2:
            st.subheader("績效統計")
            
            # MDD Calculation (Total Equity)
            equity_curve = df_test['Total_Equity']
            running_max = equity_curve.cummax()
            drawdown = (equity_curve - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # MDD Calculation (Benchmark - TAIEX)
            taiex_curve = df_test['TAIEX']
            taiex_running_max = taiex_curve.cummax()
            taiex_drawdown = (taiex_curve - taiex_running_max) / taiex_running_max
            taiex_max_drawdown = taiex_drawdown.min()
            
            # Short Strategy Stats
            trades_stats = []
            in_trade = False
            entry_price = 0
            
            for date, row in df_test.iterrows():
                pos = row['Position']
                price = row['TAIEX']
                if pos == 1 and not in_trade:
                    in_trade = True
                    entry_price = price
                elif pos == 0 and in_trade:
                    in_trade = False
                    exit_price = price
                    ret = (entry_price - exit_price) / entry_price
                    trades_stats.append(ret * short_leverage) # Leveraged Return
            
            if in_trade:
                current_price = df_test['TAIEX'].iloc[-1]
                ret = (entry_price - current_price) / entry_price
                trades_stats.append(ret * short_leverage)
                
            trades_series = pd.Series(trades_stats)
            total_trades = len(trades_series)
            win_rate = (trades_series > 0).mean() if total_trades > 0 else 0
            avg_ret = trades_series.mean() if total_trades > 0 else 0
            max_win = trades_series.max() if total_trades > 0 else 0
            max_loss = trades_series.min() if total_trades > 0 else 0
            
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            col_p1.metric("策略最大回撤 (MDD)", f"{max_drawdown:.2%}")
            col_p2.metric("大盤最大回撤 (TAIEX)", f"{taiex_max_drawdown:.2%}")
            col_p3.metric("做空交易次數", f"{total_trades}")
            col_p4.metric("做空勝率", f"{win_rate:.2%}")
            
            col_p5, col_p6 = st.columns(2)
            col_p5.metric("做空最大單筆獲利", f"{max_win:.2%}")
            col_p6.metric("做空最大單筆虧損", f"{max_loss:.2%}")
            
            # Drawdown Chart
            st.subheader("回撤曲線 (Drawdown)")
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(x=drawdown.index, y=drawdown, fill='tozeroy', line=dict(color='red'), name='Drawdown'))
            fig_dd.update_layout(title='總資產回撤幅度', yaxis_title='回撤 %', hovermode="x unified")
            st.plotly_chart(fig_dd, use_container_width=True)

        # --- Tab 3: Period Analysis ---
        with tab3:
            st.subheader("年度報酬率與風險分析")
            
            df_test['Year'] = df_test.index.year
            
            # 1. Basic Return Stats
            yearly_stats = df_test.groupby('Year').agg({
                'Total_Equity': ['first', 'last'],
                'Long_Equity': ['first', 'last'],
                'Short_Equity': ['first', 'last']
            })
            
            yearly_ret = pd.DataFrame()
            yearly_ret['總資產報酬率'] = (yearly_stats['Total_Equity']['last'] - yearly_stats['Total_Equity']['first']) / yearly_stats['Total_Equity']['first']
            yearly_ret['00631L 報酬率'] = (yearly_stats['Long_Equity']['last'] - yearly_stats['Long_Equity']['first']) / yearly_stats['Long_Equity']['first']
            yearly_ret['微台做空 報酬率'] = (yearly_stats['Short_Equity']['last'] - yearly_stats['Short_Equity']['first']) / yearly_stats['Short_Equity']['first']
            
            # 2. Yearly MDD Calculation
            yearly_mdd_strategy = []
            yearly_mdd_taiex = []
            years = yearly_ret.index.tolist()
            
            for year in years:
                df_year = df_test[df_test['Year'] == year]
                
                # Strategy MDD
                eq = df_year['Total_Equity']
                dd = (eq - eq.cummax()) / eq.cummax()
                yearly_mdd_strategy.append(dd.min())
                
                # TAIEX MDD
                tx = df_year['TAIEX']
                dd_tx = (tx - tx.cummax()) / tx.cummax()
                yearly_mdd_taiex.append(dd_tx.min())
            
            yearly_ret['策略最大回撤 (MDD)'] = yearly_mdd_strategy
            yearly_ret['大盤最大回撤 (TAIEX)'] = yearly_mdd_taiex
            
            # Formatting
            st.dataframe(yearly_ret.style.format("{:.2%}"), use_container_width=True)
            
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
            
            col_t1, col_t2 = st.columns(2)
            
            with col_t1:
                st.markdown("### 🐂 00631L (做多)")
                st.info("策略：買進持有 (Buy & Hold)")
                
                curr_price_00631L = df_test['00631L'].iloc[-1]
                
                st.write(f"**目前持有股數**：{shares_00631L:,.0f}")
                st.write(f"**目前收盤價**：{curr_price_00631L:,.2f}")
                st.write(f"**做多部位權益**：{df_test['Long_Equity'].iloc[-1]:,.0f}")
                
            with col_t2:
                st.markdown("### 🐻 微台 (做空)")
                st.info("策略：跌破均線做空，站上均線平倉")
                
                trades = []
                in_trade = False
                entry_date = None
                entry_price = 0
                entry_capital = 0
                entry_long_equity = 0
                
                for i in range(len(df_test)):
                    date = df_test.index[i]
                    row = df_test.iloc[i]
                    pos = row['Position']
                    price = row['TAIEX']
                    
                    if pos == 1 and not in_trade:
                        in_trade = True
                        entry_date = date
                        entry_price = price
                        entry_capital = row['Short_Equity'] 
                        entry_long_equity = row['Long_Equity']
                    elif pos == 0 and in_trade:
                        in_trade = False
                        exit_date = date
                        exit_price = price
                        points_diff = entry_price - exit_price
                        ret = (entry_price - exit_price) / entry_price
                        
                        # Reconstruct Notional
                        max_short_notional = entry_capital * short_leverage
                        if hedge_mode == "完全避險 (Neutral Hedge)":
                            target_short_notional = entry_long_equity * 2
                            actual_short_notional = min(target_short_notional, max_short_notional)
                        else:
                            actual_short_notional = max_short_notional
                            
                        contracts = actual_short_notional / (entry_price * 10)
                        profit_twd = points_diff * 10 * contracts
                        
                        # Effective Leverage for this trade
                        eff_leverage = actual_short_notional / entry_capital if entry_capital > 0 else 0
                        
                        trades.append({
                            '進場日期': entry_date, '進場指數': entry_price,
                            '出場日期': exit_date, '出場指數': exit_price,
                            '避險口數': contracts, '獲利點數': points_diff,
                            '獲利金額 (TWD)': profit_twd, '報酬率': ret * eff_leverage
                        })
                
                if in_trade:
                    current_date = df_test.index[-1]
                    current_price = df_test['TAIEX'].iloc[-1]
                    points_diff = entry_price - current_price
                    ret = (entry_price - current_price) / entry_price
                    
                    max_short_notional = entry_capital * short_leverage
                    if hedge_mode == "完全避險 (Neutral Hedge)":
                        target_short_notional = entry_long_equity * 2
                        actual_short_notional = min(target_short_notional, max_short_notional)
                    else:
                        actual_short_notional = max_short_notional
                        
                    contracts = actual_short_notional / (entry_price * 10)
                    profit_twd = points_diff * 10 * contracts
                    eff_leverage = actual_short_notional / entry_capital if entry_capital > 0 else 0
                    
                    trades.append({
                        '進場日期': entry_date, '進場指數': entry_price,
                        '出場日期': current_date, '出場指數': current_price,
                        '避險口數': contracts, '獲利點數': points_diff,
                        '獲利金額 (TWD)': profit_twd, '報酬率': ret * eff_leverage, '備註': '持倉中'
                    })
                    
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
                else:
                    st.info("區間內無做空交易")

else:
    st.info("請上傳 00631L 和 加權指數 的 Excel 檔案，或確認目錄下是否有預設檔案。")
