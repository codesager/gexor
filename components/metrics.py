import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional
from config import COLORS

def render_kpi_header(
    symbol: str,
    spot_price: float,
    levels: Dict[str, Any],
    expected_move: Dict[str, Any],
    regime: Dict[str, Any],
    pinning: Dict[str, Any]
):
    """
    Renders top KPI metrics cards with live spot, net GEX, walls, and gamma regime.
    """
    col1, col2, col3, col4, col5 = st.columns(5)

    # Col 1: Spot Price
    with col1:
        st.metric(
            label=f"🎯 {symbol} Spot Price",
            value=f"${spot_price:,.2f}",
            delta=f"ATM Straddle: ±{expected_move.get('implied_move_pct', 0.0):.2f}%"
        )

    # Col 2: Net GEX & Regime
    with col2:
        net_m = levels.get("net_gex_total_m", 0.0)
        net_str = f"${net_m:+.1f}M"
        st.metric(
            label="⚡ Total Net GEX",
            value=net_str,
            delta="Long Gamma" if regime.get("is_long_gamma") else "Short Gamma",
            delta_color="normal" if regime.get("is_long_gamma") else "inverse"
        )

    # Col 3: King Node (Gold Badge)
    with col3:
        king_node = levels.get("king_node", spot_price)
        dist_king = pinning.get("dist_king_pct", 0.0)
        st.metric(
            label="👑 King Node (Magnet)",
            value=f"{king_node:g} ★",
            delta=f"{dist_king:+.2f}% from spot"
        )

    # Col 4: Call & Put Walls
    with col4:
        call_wall = levels.get("call_wall", spot_price)
        put_wall = levels.get("put_wall", spot_price)
        st.metric(
            label="🧱 Walls (Call / Put)",
            value=f"{call_wall:g} / {put_wall:g}",
            delta=f"Range: {abs(call_wall - put_wall):g} pts"
        )

    # Col 5: Zero Gamma Level
    with col5:
        g_flip = levels.get("gamma_flip", spot_price)
        flip_dist = regime.get("flip_dist_pct", 0.0)
        st.metric(
            label="🌀 Gamma Flip (Zero GEX)",
            value=f"{g_flip:,.1f}",
            delta=f"{flip_dist:+.2f}% to Flip"
        )

def render_regime_banner(regime: Dict[str, Any], pinning: Dict[str, Any]):
    """
    Renders styled alert banner for Gamma Regime & Market Pinning Score.
    """
    badge_col = regime.get("badge_color", COLORS["gamma_flip"])
    regime_text = regime.get("regime", "")
    desc = regime.get("description", "")
    pin_score = pinning.get("king_magnet_score", 50)
    pin_rating = pinning.get("pin_rating", "MODERATE")

    st.markdown(
        f"""
        <div style="background-color: #161b22; border-left: 5px solid {badge_col}; border-radius: 8px; padding: 12px 18px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-weight: 700; font-size: 1.05rem; color: {badge_col};">REGIME: {regime_text}</span>
                    <p style="margin: 4px 0 0 0; font-size: 0.9rem; color: #8b949e;">{desc}</p>
                </div>
                <div style="text-align: right; margin-top: 6px;">
                    <span style="font-size: 0.85rem; color: #8b949e;">0DTE Magnet Pinning Score:</span>
                    <span style="font-weight: 700; font-size: 1.1rem; color: #ffd700; margin-left: 6px;">{pin_score}% — {pin_rating}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_trade_recommendations_table(signals: List[Dict[str, Any]]):
    """
    Renders formatted table of high-signal strike recommendations.
    """
    if not signals:
        st.info("No unusual strike signals detected in the active window.")
        return

    st.markdown("### 🎯 High-Signal Interest Zones & Trade Setups")
    
    rows_html = ""
    for s in signals:
        badge_style = "background-color: #238636; color: white;"
        if "SELL" in s["signal"] or "CREDIT" in s["signal"]:
            badge_style = "background-color: #da3633; color: white;"
        elif "MAGNET" in s["signal"]:
            badge_style = "background-color: #ffd700; color: black; font-weight: bold;"
        elif "BUY CALLS" in s["signal"]:
            badge_style = "background-color: #1f6beb; color: white;"
        elif "BUY PUTS" in s["signal"]:
            badge_style = "background-color: #8957e5; color: white;"

        gex_color = "#00c853" if s["net_gex_m"] >= 0 else "#ff5252"
        rows_html += (
            f'<tr style="border-bottom: 1px solid #30363d;">'
            f'<td style="padding: 10px; font-weight: bold; font-family: monospace; font-size: 1.05rem; color: #f0f6fc;">{s["strike"]:g}</td>'
            f'<td style="padding: 10px; color: #c9d1d9;">{s["type"]}</td>'
            f'<td style="padding: 10px;"><span style="padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; {badge_style}">{s["signal"]}</span></td>'
            f'<td style="padding: 10px; color: #8b949e; font-size: 0.9rem;">{s["reason"]}</td>'
            f'<td style="padding: 10px; text-align: right; font-family: monospace; color: #ffd700;">{s["vol_oi_ratio"]:.1f}x</td>'
            f'<td style="padding: 10px; text-align: right; font-family: monospace; color: {gex_color};">${s["net_gex_m"]:+.1f}M</td>'
            f'</tr>'
        )

    html_table = (
        '<div style="overflow-x: auto; background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 6px; margin-bottom: 25px;">'
        '<table style="width: 100%; border-collapse: collapse; text-align: left;">'
        '<thead>'
        '<tr style="border-bottom: 2px solid #30363d; color: #8b949e; font-size: 0.85rem;">'
        '<th style="padding: 10px;">STRIKE</th>'
        '<th style="padding: 10px;">TYPE</th>'
        '<th style="padding: 10px;">SIGNAL / ACTION</th>'
        '<th style="padding: 10px;">ANALYSIS / RATIONALE</th>'
        '<th style="padding: 10px; text-align: right;">VOL / OI</th>'
        '<th style="padding: 10px; text-align: right;">NET GEX</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '</div>'
    )

    if hasattr(st, "html"):
        st.html(html_table)
    else:
        st.markdown(html_table, unsafe_allow_html=True)

def render_trinity_multi_ticker_view(
    tickers_data: List[Dict[str, Any]],
    strike_window_dollar: Optional[float] = 100.0
):
    """
    Renders 0DTE Multi-Ticker Matrix (Trinity View) with side-by-side Institutional Grid tables,
    live spot prices, Yellow `#FFD700` King Node highlights, and formatted numerical values.
    """
    st.markdown("## ⚡ 0DTE Multi-Ticker Matrix (Trinity View)")
    st.caption("Side-by-side 0DTE GEX Institutional Heatmap Grids with King Node (🟡 ★) and Spot Price (⚪) highlights.")

    if not tickers_data:
        st.warning("No multi-ticker comparison data available.")
        return

    cols = st.columns(len(tickers_data))

    from components.institutional_grid import render_institutional_heatmap_grid

    for idx, data in enumerate(tickers_data):
        symbol = data["symbol"]
        spot = data["spot_price"]
        df = data["df"]
        levels = data["levels"]
        king_node = levels.get("king_node", spot)
        exp_date = data.get("expiration") or "0DTE"

        with cols[idx]:
            if df.empty:
                st.info(f"No 0DTE chain data for {symbol}")
                continue

            # Group by strike to calculate Net GEX per strike
            df_uniq = df.groupby("strike", as_index=False).agg({
                "net_gex_m": "sum"
            })

            # Create 1-column matrix (Strike x 0DTE Expiration)
            matrix_df = df_uniq.set_index("strike")[["net_gex_m"]].rename(columns={"net_gex_m": f"{exp_date}"})

            # Render Institutional Grid table for this ticker
            render_institutional_heatmap_grid(
                matrix=matrix_df,
                spot_price=spot,
                king_nodes_per_exp={f"{exp_date}": king_node},
                symbol=symbol,
                title=f"{symbol} 0DTE Matrix",
                is_currency=True,
                strike_window_dollar=strike_window_dollar
            )
