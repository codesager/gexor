import datetime
import time
import pandas as pd
import streamlit as st

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="GEXOR — Gamma Exposure Research Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

from config import (
    ACCOUNT_ID, PUBLIC_SECRET_KEY, APP_PASSWORD,
    DEFAULT_STRIKE_WINDOW_PCT, DEFAULT_MIN_OI,
    INDEX_TICKERS, DEFAULT_INDEX_EXPIRATIONS_COUNT, DEFAULT_EQUITY_EXPIRATIONS_COUNT,
    PRESET_TICKERS, TRINITY_DEFAULT_TICKERS, COLORS
)
from api import PublicDotComClientWrapper
from api.mock_data import get_base_spot_price
from analytics import (
    calculate_gex_df,
    find_gex_key_levels,
    calculate_atm_straddle_move,
    calculate_pinning_score,
    analyze_gamma_regime,
    get_interest_zones_and_signals
)
from components import (
    create_gex_bar_chart,
    create_gex_heatmap,
    create_generic_heatmap,
    render_kpi_header,
    render_regime_banner,
    render_trade_recommendations_table,
    render_trinity_multi_ticker_view,
    render_heatmap_grid
)

# Custom CSS for Dark Glassmorphism Styling
st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {COLORS["background"]};
            color: {COLORS["text_primary"]};
        }}
        .metric-card {{
            background-color: {COLORS["card_bg"]};
            border: 1px solid {COLORS["card_border"]};
            border-radius: 8px;
            padding: 12px;
        }}
        div[data-testid="stMetricValue"] {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 12px;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: {COLORS["card_bg"]};
            border-radius: 6px;
            padding: 8px 16px;
            border: 1px solid {COLORS["card_border"]};
        }}
        .stTabs [aria-selected="true"] {{
            background-color: #1f6beb !important;
            color: white !important;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

from session_store import load_session, save_session, PERSISTENT_KEYS

# Load persistent session state and user preferences from disk
saved_session = load_session()
for k, v in saved_session.items():
    if k in PERSISTENT_KEYS and k not in st.session_state:
        st.session_state[k] = v

# Initialize Client API Wrapper in Session State
if "client" not in st.session_state:
    st.session_state.client = PublicDotComClientWrapper(
        account_id=ACCOUNT_ID,
        secret_key=PUBLIC_SECRET_KEY
    )

if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = datetime.datetime.now().strftime("%I:%M:%S %p")

# Optional Password Authentication Check
if APP_PASSWORD:
    if not st.session_state.get("authenticated", False):
        st.markdown("## 🔒 GEXOR Dashboard Protection")
        with st.form("login_form"):
            pwd = st.text_input("Enter Dashboard Password:", type="password")
            submit_login = st.form_submit_button("Unlock Dashboard")
            if submit_login:
                if pwd == APP_PASSWORD:
                    st.session_state.authenticated = True
                    save_session(dict(st.session_state))
                    st.rerun()
                else:
                    st.error("Invalid password")
        st.stop()

# Cache API calls per ticker and expiration for fast response
@st.cache_data(ttl=30, show_spinner=False)
def fetch_ticker_gex_data(symbol: str, expiration_count: int = 20, strike_window_pct: float = 12.0, min_oi: int = 10, formula_mode: str = "standard"):
    client = st.session_state.client
    spot = client.get_spot_price(symbol)
    expirations = client.get_option_expirations(symbol, count=expiration_count)

    exp_gex_dfs = {}
    key_levels_map = {}
    expected_moves_map = {}
    all_chain_strikes = []

    for exp in expirations:
        chain_raw = client.get_option_chain_with_greeks(symbol, exp, strike_window_pct)
        calls_df = pd.DataFrame(chain_raw.get("calls", []))
        puts_df = pd.DataFrame(chain_raw.get("puts", []))

        gex_df = calculate_gex_df(calls_df, puts_df, spot_price=spot, min_oi=min_oi, formula_mode=formula_mode)
        if not gex_df.empty:
            all_chain_strikes.extend(gex_df["strike"].tolist())
        exp_gex_dfs[exp] = gex_df

    # Auto-align spot price if quote API returned an out-of-range value vs actual option chain strikes
    if all_chain_strikes:
        min_s, max_s = min(all_chain_strikes), max(all_chain_strikes)
        if spot < min_s or spot > max_s:
            spot = min(all_chain_strikes, key=lambda s: abs(s - spot))
            for exp in expirations:
                if exp in exp_gex_dfs and not exp_gex_dfs[exp].empty:
                    exp_gex_dfs[exp]["distance_from_spot_pct"] = ((exp_gex_dfs[exp]["strike"] - spot) / spot) * 100.0

    for exp in expirations:
        gex_df = exp_gex_dfs.get(exp, pd.DataFrame())
        if not gex_df.empty:
            levels = find_gex_key_levels(gex_df, spot_price=spot)
            straddle_move = calculate_atm_straddle_move(gex_df, spot_price=spot)
        else:
            levels = find_gex_key_levels(pd.DataFrame(), spot_price=spot)
            straddle_move = calculate_atm_straddle_move(pd.DataFrame(), spot_price=spot)

        key_levels_map[exp] = levels
        expected_moves_map[exp] = straddle_move

    return {
        "symbol": symbol,
        "spot_price": spot,
        "expirations": expirations,
        "exp_gex_dfs": exp_gex_dfs,
        "key_levels_map": key_levels_map,
        "expected_moves_map": expected_moves_map
    }

# SIDEBAR CONTROLS
st.sidebar.markdown("## ⚙️ Dashboard Controls")

formula_opts = ["Standard Notional ($S²)", "Skylit Model ($)"]
saved_formula_idx = formula_opts.index(st.session_state.get("gex_formula_mode")) if st.session_state.get("gex_formula_mode") in formula_opts else 0

gex_formula_mode = st.sidebar.radio(
    "📐 GEX Formula Methodology",
    options=formula_opts,
    index=saved_formula_idx,
    help="Standard Notional measures dollar gamma per 1% spot move (Gamma * OI * S²). Skylit Model measures dollar gamma per $1 move (Gamma * OI * S) matching Skylit platform metrics."
)
if gex_formula_mode != st.session_state.get("gex_formula_mode"):
    st.session_state.gex_formula_mode = gex_formula_mode
    save_session(dict(st.session_state))

formula_mode_key = "skylit" if "Skylit" in gex_formula_mode else "standard"

strike_window = st.sidebar.slider(
    "Strike Window Range (±%)",
    min_value=4.0, max_value=25.0, value=float(st.session_state.get("strike_window", DEFAULT_STRIKE_WINDOW_PCT)), step=1.0,
    help="Filters strikes within ±X% around current spot price."
)
if strike_window != st.session_state.get("strike_window"):
    st.session_state.strike_window = strike_window
    save_session(dict(st.session_state))

min_oi_filter = st.sidebar.slider(
    "Minimum Open Interest (OI)",
    min_value=0, max_value=500, value=int(st.session_state.get("min_oi_filter", DEFAULT_MIN_OI)), step=10,
    help="Filters out low liquidity options with OI below threshold."
)
if min_oi_filter != st.session_state.get("min_oi_filter"):
    st.session_state.min_oi_filter = min_oi_filter
    save_session(dict(st.session_state))

def get_formatted_refresh_time() -> str:
    """Returns formatted 12-hour timestamp with AM/PM (e.g. 09:12:49 PM)."""
    return datetime.datetime.now().strftime("%I:%M:%S %p")

if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = get_formatted_refresh_time()

# Auto Refresh & Manual Refresh Controls
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Refresh Controls")
auto_refresh = st.sidebar.toggle("30-Sec Auto Refresh", value=False)
if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.session_state.last_refresh_time = get_formatted_refresh_time()
    st.rerun()

st.sidebar.caption(f"Last updated: **{st.session_state.last_refresh_time}**")

# TOP NAVIGATION & HEADER
top_col1, top_col2 = st.columns([3, 1])

with top_col1:
    st.markdown("# ⚡ GEXOR — Gamma Exposure Dashboard")

with top_col2:
    mode_text = "🟢 Live API" if not st.session_state.client.is_mock else "🟡 Demo Mode (Public.com SDK)"
    st.markdown(
        f"""
        <div style="text-align: right; padding-top: 10px;">
            <span style="background-color: #161b22; border: 1px solid #30363d; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem;">
                {mode_text}
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

# TICKER SELECTION & PRESETS BAR
preset_cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 4])
if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = "SPX"

for idx, preset in enumerate(PRESET_TICKERS[:8]):
    with preset_cols[idx]:
        if st.button(preset, key=f"btn_{preset}"):
            st.session_state.active_ticker = preset
            save_session(dict(st.session_state))
            st.rerun()

with preset_cols[8]:
    custom_input = st.text_input(
        "Enter Any Ticker Symbol:",
        value=st.session_state.active_ticker,
        placeholder="e.g. SPX, AAPL, TSLA, NVDA, SPY..."
    )
    if custom_input and custom_input.upper().strip() != st.session_state.active_ticker:
        st.session_state.active_ticker = custom_input.upper().strip()
        save_session(dict(st.session_state))
        st.rerun()

current_ticker = st.session_state.active_ticker.upper().strip()

# MAIN DASHBOARD NAVIGATION TABS
tab_options = ["📊 Single Ticker Deep Dive", "⚡ 0DTE Multi-Ticker Matrix (Trinity View)"]
saved_tab = st.session_state.get("active_tab", tab_options[0])
saved_tab_idx = tab_options.index(saved_tab) if saved_tab in tab_options else 0

active_tab = st.radio(
    "Select Dashboard View:",
    options=tab_options,
    index=saved_tab_idx,
    horizontal=True,
    key="active_tab_nav"
)
if active_tab != st.session_state.get("active_tab"):
    st.session_state.active_tab = active_tab
    save_session(dict(st.session_state))

# CONDITIONAL DATA FETCHING BASED ON ACTIVE VIEW
if active_tab == "📊 Single Ticker Deep Dive":
    # FETCH DATA FOR ACTIVE TICKER ONLY (ALL AVAILABLE EXPIRATIONS)
    data = fetch_ticker_gex_data(current_ticker, expiration_count=20, strike_window_pct=strike_window, min_oi=min_oi_filter, formula_mode=formula_mode_key)
    spot_price = data["spot_price"]
    expirations = data["expirations"]

    if not expirations:
        st.error(f"No option expirations found for ticker {current_ticker}.")
        st.stop()

    # AGGREGATE GEX DATA ACROSS ALL EXPIRATIONS
    all_dfs = [df for df in data["exp_gex_dfs"].values() if not df.empty]
    if all_dfs:
        agg_df = pd.concat(all_dfs, ignore_index=True).groupby("strike", as_index=False).agg({
            "call_gex_m": "sum",
            "put_gex_m": "sum",
            "net_gex_m": "sum",
            "call_open_interest": "sum",
            "put_open_interest": "sum",
            "total_oi": "sum",
            "call_volume": "sum",
            "put_volume": "sum",
            "total_volume": "sum",
            "call_last": "mean",
            "put_last": "mean",
            "call_gamma": "mean",
            "put_gamma": "mean",
        })
        agg_df["call_vol_oi_ratio"] = agg_df["call_volume"] / (agg_df["call_open_interest"].replace(0, 1))
        agg_df["put_vol_oi_ratio"] = agg_df["put_volume"] / (agg_df["put_open_interest"].replace(0, 1))
        agg_df["total_vol_oi_ratio"] = agg_df["total_volume"] / (agg_df["total_oi"].replace(0, 1))
        agg_df["call_gex"] = agg_df["call_gex_m"] * 1e6
        agg_df["put_gex"] = agg_df["put_gex_m"] * 1e6
        agg_df["net_gex"] = agg_df["net_gex_m"] * 1e6
    else:
        agg_df = pd.DataFrame()

    agg_levels = find_gex_key_levels(agg_df, spot_price)
    first_exp = expirations[0]
    first_straddle_move = data["expected_moves_map"].get(first_exp, calculate_atm_straddle_move(agg_df, spot_price))
    regime = analyze_gamma_regime(agg_levels["net_gex_total_m"], spot_price, agg_levels["gamma_flip"])
    pinning = calculate_pinning_score(spot_price, agg_levels["king_node"], agg_levels["call_wall"], agg_levels["put_wall"], dte_days=0.5)

    # 1. KPI Header
    render_kpi_header(current_ticker, spot_price, agg_levels, first_straddle_move, regime, pinning)
    render_regime_banner(regime, pinning)

    # 2. Expiration Date Selector
    exp_col, export_col = st.columns([4, 1])
    with exp_col:
        selected_exp = st.selectbox(
            "Select Expiration Date for Deep Dive:",
            options=["ALL (Aggregated Chain)"] + expirations,
            index=0
        )

    active_df = agg_df if selected_exp == "ALL (Aggregated Chain)" else data["exp_gex_dfs"].get(selected_exp, pd.DataFrame())
    active_levels = agg_levels if selected_exp == "ALL (Aggregated Chain)" else data["key_levels_map"].get(selected_exp, agg_levels)
    active_move = first_straddle_move if selected_exp == "ALL (Aggregated Chain)" else data["expected_moves_map"].get(selected_exp, first_straddle_move)
    exp_label = "" if selected_exp == "ALL (Aggregated Chain)" else selected_exp

    with export_col:
        if not active_df.empty:
            csv_bytes = active_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export CSV",
                data=csv_bytes,
                file_name=f"{current_ticker}_GEX_{selected_exp}.csv",
                mime="text/csv",
                width='stretch'
            )

    # 3. Primary Net GEX Bar Chart
    fig_bar = create_gex_bar_chart(active_df, spot_price, active_levels, active_move, symbol=current_ticker, expiration=exp_label)
    st.plotly_chart(fig_bar, width='stretch')

    # 4. High-Signal Strike Recommender Table
    signals = get_interest_zones_and_signals(
        active_df, spot_price, active_levels["gamma_flip"],
        active_levels["call_wall"], active_levels["put_wall"],
        active_levels["king_node"], active_move["straddle_price"]
    )
    render_trade_recommendations_table(signals)

    # 5. Heatmaps Section
    st.markdown("### 🌡️ Multi-Expiration Heatmaps")
    
    hm_col1, hm_col2 = st.columns([3, 2])
    with hm_col1:
        view_mode = st.radio(
            "Heatmap Display Style:",
            options=["🔥 Heatmap Grid Table (Numeric Matrix)", "📈 Plotly Continuous Surface Chart"],
            horizontal=True,
            index=0,
            help="Heatmap Grid Table renders formatted numerical values inside every cell, white spot strike badge, and gold glowing King Node pills."
        )

    with hm_col2:
        strike_focus_opt = st.selectbox(
            "Strike Focus Window:",
            options=[
                "±$100 Dollar Offset around Spot",
                "🎯 ±10 Strikes around King Node (Centered)",
                "🎯 ±5 Strikes around King Node (Tight)",
                "🎯 ±15 Strikes around King Node (Medium)",
                "Full Window (All Strikes)"
            ],
            index=0,
            help="Filters grid to N strikes above & below spot or King Node, centered in the viewport."
        )

    strike_count_around_king = None
    strike_focus_dollar = None

    if "±$100" in strike_focus_opt:
        strike_focus_dollar = 100.0
    elif "±10 Strikes" in strike_focus_opt:
        strike_count_around_king = 10
    elif "±5 Strikes" in strike_focus_opt:
        strike_count_around_king = 5
    elif "±15 Strikes" in strike_focus_opt:
        strike_count_around_king = 15

    hm_tab1, hm_tab2, hm_tab3 = st.tabs(["Net GEX Matrix (King Nodes)", "Open Interest Matrix", "Volume / OI Matrix"])

    # Construct Heatmap Matrices (Safely group by strike to avoid duplicate index errors)
    net_gex_dict = {}
    oi_dict = {}
    vol_oi_dict = {}
    king_nodes_per_exp = {}

    for exp in expirations:
        e_df = data["exp_gex_dfs"].get(exp, pd.DataFrame())
        if not e_df.empty:
            e_uniq = e_df.groupby("strike", as_index=False).agg({
                "net_gex_m": "sum",
                "total_oi": "sum",
                "total_vol_oi_ratio": "mean"
            }).sort_values("strike")

            net_gex_dict[exp] = e_uniq.set_index("strike")["net_gex_m"]
            oi_dict[exp] = e_uniq.set_index("strike")["total_oi"]
            vol_oi_dict[exp] = e_uniq.set_index("strike")["total_vol_oi_ratio"]
            king_nodes_per_exp[exp] = data["key_levels_map"][exp]["king_node"]

    net_gex_matrix = pd.DataFrame(net_gex_dict).sort_index() if net_gex_dict else pd.DataFrame()
    oi_matrix = pd.DataFrame(oi_dict).sort_index() if oi_dict else pd.DataFrame()
    vol_oi_matrix = pd.DataFrame(vol_oi_dict).sort_index() if vol_oi_dict else pd.DataFrame()

    with hm_tab1:
        if "Heatmap Grid" in view_mode:
            render_heatmap_grid(
                matrix=net_gex_matrix,
                spot_price=spot_price,
                king_nodes_per_exp=king_nodes_per_exp,
                symbol=current_ticker,
                title=f"{current_ticker} Net GEX Matrix (King Nodes Highlighted)",
                is_currency=True,
                strike_window_dollar=strike_focus_dollar,
                strike_count_around_king=strike_count_around_king,
                formula_mode=formula_mode_key
            )
        else:
            fig_hm_gex = create_gex_heatmap(
                net_gex_matrix,
                king_nodes_per_exp,
                title=f"{current_ticker} Net GEX Matrix Across Expirations (🟡 King Nodes Highlighted)"
            )
            st.plotly_chart(fig_hm_gex, width='stretch')

    with hm_tab2:
        if "Heatmap Grid" in view_mode:
            render_heatmap_grid(
                matrix=oi_matrix,
                spot_price=spot_price,
                symbol=current_ticker,
                title=f"{current_ticker} Total Open Interest Matrix",
                is_currency=False,
                strike_window_dollar=strike_focus_dollar,
                strike_count_around_king=strike_count_around_king
            )
        else:
            fig_hm_oi = create_generic_heatmap(
                oi_matrix,
                title=f"{current_ticker} Total Open Interest Matrix",
                z_label="Open Interest",
                colorscale="Plasma"
            )
            st.plotly_chart(fig_hm_oi, width='stretch')

    with hm_tab3:
        if "Heatmap Grid" in view_mode:
            render_heatmap_grid(
                matrix=vol_oi_matrix,
                spot_price=spot_price,
                symbol=current_ticker,
                title=f"{current_ticker} Volume / OI Ratio Matrix",
                is_currency=False,
                strike_window_dollar=strike_focus_dollar,
                strike_count_around_king=strike_count_around_king
            )
        else:
            fig_hm_vol = create_generic_heatmap(
                vol_oi_matrix,
                title=f"{current_ticker} Volume / OI Ratio Matrix (Fresh Institutional Positioning)",
                z_label="Vol / OI Ratio",
                colorscale="Inferno"
            )
            st.plotly_chart(fig_hm_vol, width='stretch')

else:
    # TAB 2: 0DTE MULTI-TICKER MATRIX (TRINITY VIEW ONLY)
    t_col1, t_col2 = st.columns([3, 2])
    with t_col1:
        saved_trinity = st.session_state.get("trinity_input", "SPX, SPY, QQQ")
        trinity_input = st.text_input(
            "Enter Tickers for 0DTE Side-by-Side Comparison (comma-separated, max 6):",
            value=saved_trinity,
            placeholder="e.g. SPX, SPY, QQQ, NVDA, TSLA, AAPL",
            help="Enter up to 6 ticker symbols separated by commas to compare 0DTE heatmaps."
        )
        if trinity_input != st.session_state.get("trinity_input"):
            st.session_state.trinity_input = trinity_input
            save_session(dict(st.session_state))

    with t_col2:
        trinity_focus_opt = st.selectbox(
            "Trinity Strike Focus Range:",
            options=["±$100 (Focused ATM)", "±$50 (Tight ATM)", "±$250 (Medium)", "±$500 (Wide)", "Full Window (All Strikes)"],
            index=0,
            key="trinity_strike_focus"
        )

    trinity_focus_dollar = None
    if "±$50" in trinity_focus_opt:
        trinity_focus_dollar = 50.0
    elif "±$100" in trinity_focus_opt:
        trinity_focus_dollar = 100.0
    elif "±$250" in trinity_focus_opt:
        trinity_focus_dollar = 250.0
    elif "±$500" in trinity_focus_opt:
        trinity_focus_dollar = 500.0

    raw_trinity_tickers = [t.strip().upper() for t in trinity_input.split(",") if t.strip()]
    selected_trinity_tickers = list(dict.fromkeys(raw_trinity_tickers))[:6]

    if not selected_trinity_tickers:
        st.warning("Please enter at least one valid ticker symbol above.")
    else:
        if len(raw_trinity_tickers) > 6:
            st.info(f"Displaying first 6 tickers: {', '.join(selected_trinity_tickers)}")

        trinity_data_list = []
        for t_sym in selected_trinity_tickers:
            # STRICTLY PULL 0DTE (expiration_count=1) FOR TRINITY VIEW
            t_data = fetch_ticker_gex_data(t_sym, expiration_count=1, strike_window_pct=max(15.0, strike_window), min_oi=min_oi_filter, formula_mode=formula_mode_key)
            t_exp = t_data["expirations"][0] if t_data["expirations"] else ""
            t_df = t_data["exp_gex_dfs"].get(t_exp, pd.DataFrame())
            t_levels = t_data["key_levels_map"].get(t_exp, {})
            trinity_data_list.append({
                "symbol": t_sym,
                "expiration": t_exp,
                "spot_price": t_data["spot_price"],
                "df": t_df,
                "levels": t_levels
            })

        render_trinity_multi_ticker_view(trinity_data_list, strike_window_dollar=trinity_focus_dollar)

# Auto-Refresh Handler
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.session_state.last_refresh_time = datetime.datetime.now().strftime("%H:%M:%S EDT")
    st.rerun()
