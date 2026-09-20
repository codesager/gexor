import pandas as pd
import numpy as np
from typing import Dict, List, Any

def analyze_gamma_regime(total_net_gex_m: float, spot_price: float, gamma_flip: float) -> Dict[str, Any]:
    """
    Determines market gamma regime (Long Gamma vs Short Gamma).
    """
    is_long_gamma = total_net_gex_m >= 0 and spot_price >= gamma_flip
    
    if is_long_gamma:
        regime = "LONG GAMMA (Sticky / Range-Bound)"
        description = "Market makers long gamma -> dampens volatility. Price tends to mean-revert towards King Node."
        badge_color = "#00e676" # Emerald Green
    else:
        regime = "SHORT GAMMA (Volatile / Trend Acceleration)"
        description = "Market makers short gamma -> amplifies price moves. Increased intraday volatility and downside risk."
        badge_color = "#ff5252" # Crimson Red

    flip_dist_pct = ((spot_price - gamma_flip) / spot_price) * 100.0

    return {
        "regime": regime,
        "is_long_gamma": is_long_gamma,
        "description": description,
        "badge_color": badge_color,
        "flip_dist_pct": round(flip_dist_pct, 2),
    }

def get_interest_zones_and_signals(
    df: pd.DataFrame,
    spot_price: float,
    gamma_flip: float,
    call_wall: float,
    put_wall: float,
    king_node: float,
    expected_move: float
) -> List[Dict[str, Any]]:
    """
    Scans option chain dataframe to identify high-signal strike recommendations.
    Flags candidates based on gamma concentration, unusual Vol/OI ratio, and wall alignment.
    """
    if df.empty:
        return []

    df_eval = df.copy()

    signals = []

    # 1. King Node (Dominant Magnet)
    king_row = df_eval[df_eval["strike"] == king_node]
    if not king_row.empty:
        k_r = king_row.iloc[0]
        signals.append({
            "strike": king_node,
            "type": "👑 King Node (Primary Magnet)",
            "signal": "MAGNET / TARGET",
            "reason": f"Highest net gamma concentration (${k_r['net_gex_m']:.1f}M). Price tends to pull towards this level.",
            "vol_oi_ratio": round(k_r.get("total_vol_oi_ratio", 0.0), 2),
            "net_gex_m": round(k_r.get("net_gex_m", 0.0), 1),
            "badge": "warning"
        })

    # 2. Call Wall (Resistance Ceiling)
    if call_wall != king_node:
        cw_row = df_eval[df_eval["strike"] == call_wall]
        if not cw_row.empty:
            cw_r = cw_row.iloc[0]
            signals.append({
                "strike": call_wall,
                "type": "🟢 Call Wall (Resistance Ceiling)",
                "signal": "SELL CALLS / CREDIT SPREAD",
                "reason": f"Strong call gamma wall (${cw_r['call_gex_m']:.1f}M). Acts as heavy resistance barrier.",
                "vol_oi_ratio": round(cw_r.get("call_vol_oi_ratio", 0.0), 2),
                "net_gex_m": round(cw_r.get("call_gex_m", 0.0), 1),
                "badge": "success"
            })

    # 3. Put Wall (Support Floor)
    if put_wall != king_node and put_wall != call_wall:
        pw_row = df_eval[df_eval["strike"] == put_wall]
        if not pw_row.empty:
            pw_r = pw_row.iloc[0]
            signals.append({
                "strike": put_wall,
                "type": "🔴 Put Wall (Support Floor)",
                "signal": "SELL PUTS / CREDIT SPREAD",
                "reason": f"Strong put gamma wall (${abs(pw_r['put_gex_m']):.1f}M). Acts as strong support floor.",
                "vol_oi_ratio": round(pw_r.get("put_vol_oi_ratio", 0.0), 2),
                "net_gex_m": round(pw_r.get("put_gex_m", 0.0), 1),
                "badge": "danger"
            })

    # 4. High Vol/OI Call Accumulation Strike (Long Call Candidate)
    bull_candidates = df_eval[
        (df_eval["strike"] > spot_price) &
        (df_eval["strike"] <= spot_price * 1.05) &
        (df_eval["call_vol_oi_ratio"] > 1.2) &
        (df_eval["call_open_interest"] >= 50)
    ].sort_values("call_vol_oi_ratio", ascending=False)

    if not bull_candidates.empty:
        top_bull = bull_candidates.iloc[0]
        if top_bull["strike"] not in [king_node, call_wall]:
            signals.append({
                "strike": float(top_bull["strike"]),
                "type": "🚀 Bullish Call Accumulation",
                "signal": "BUY CALLS / DEBIT SPREAD",
                "reason": f"Unusual call volume spike ({top_bull['call_vol_oi_ratio']:.1f}x Vol/OI). Fresh institutional accumulation.",
                "vol_oi_ratio": round(top_bull["call_vol_oi_ratio"], 2),
                "net_gex_m": round(top_bull["call_gex_m"], 1),
                "badge": "info"
            })

    # 5. High Vol/OI Put Accumulation Strike (Long Put Candidate)
    bear_candidates = df_eval[
        (df_eval["strike"] < spot_price) &
        (df_eval["strike"] >= spot_price * 0.95) &
        (df_eval["put_vol_oi_ratio"] > 1.2) &
        (df_eval["put_open_interest"] >= 50)
    ].sort_values("put_vol_oi_ratio", ascending=False)

    if not bear_candidates.empty:
        top_bear = bear_candidates.iloc[0]
        if top_bear["strike"] not in [king_node, put_wall]:
            signals.append({
                "strike": float(top_bear["strike"]),
                "type": "⚠️ Bearish Put Accumulation",
                "signal": "BUY PUTS / HEDGE",
                "reason": f"Unusual put volume spike ({top_bear['put_vol_oi_ratio']:.1f}x Vol/OI). Heavy downside hedging.",
                "vol_oi_ratio": round(top_bear["put_vol_oi_ratio"], 2),
                "net_gex_m": round(top_bear["put_gex_m"], 1),
                "badge": "secondary"
            })

    return signals
