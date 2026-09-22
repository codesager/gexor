import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

def calculate_gex_df(
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame,
    spot_price: float,
    min_oi: int = 10,
    formula_mode: str = "standard"
) -> pd.DataFrame:
    """
    Computes Net GEX, Call GEX, Put GEX, Open Interest, Volume, and Vol/OI ratios per strike.
    
    Formula Modes:
    - "standard": Standard Notional GEX ($) per 1% spot move = Gamma * OI * 100 * Spot^2 * 0.01 = 1.0 * Spot^2
    - "skylit": Skylit Dollar Gamma ($) per $1 spot move = Gamma * OI * 100 * Spot
    """
    if calls_df.empty and puts_df.empty:
        return pd.DataFrame()

    # Filter by min OI if columns exist
    if not calls_df.empty and "open_interest" in calls_df.columns:
        calls_df = calls_df[calls_df["open_interest"] >= min_oi].copy()
    if not puts_df.empty and "open_interest" in puts_df.columns:
        puts_df = puts_df[puts_df["open_interest"] >= min_oi].copy()

    # Merge Calls & Puts on strike
    c = calls_df.copy() if not calls_df.empty else pd.DataFrame(columns=["strike"])
    p = puts_df.copy() if not puts_df.empty else pd.DataFrame(columns=["strike"])

    # Prefix columns to avoid collisions
    c_cols = {col: f"call_{col}" for col in c.columns if col != "strike"}
    p_cols = {col: f"put_{col}" for col in p.columns if col != "strike"}
    
    c = c.rename(columns=c_cols)
    p = p.rename(columns=p_cols)

    df = pd.merge(c, p, on="strike", how="outer").sort_values("strike").reset_index(drop=True)

    # Fill NaNs
    fill_defaults = {
        "call_gamma": 0.0, "put_gamma": 0.0,
        "call_open_interest": 0, "put_open_interest": 0,
        "call_volume": 0, "put_volume": 0,
        "call_last": 0.0, "put_last": 0.0,
        "call_iv": 0.0, "put_iv": 0.0,
        "call_delta": 0.0, "put_delta": 0.0,
    }
    for col, default_val in fill_defaults.items():
        if col not in df.columns:
            df[col] = default_val
        else:
            df[col] = df[col].fillna(default_val)

    # Calculate Notional Gamma ($) based on formula mode
    if formula_mode.lower() == "skylit":
        # Dollar Gamma per $1 move: Gamma * OI * 100 * Spot (expressed such that call_gex_m * 1000 = $K)
        gex_multiplier = spot_price * 100.0
    else:
        # Standard Notional Dollar GEX per 1% move: Gamma * OI * 100 * Spot^2 * 0.01 = 1.0 * Spot^2
        gex_multiplier = spot_price * spot_price * 1.0

    df["call_gex"] = df["call_gamma"] * df["call_open_interest"] * gex_multiplier
    df["put_gex"] = -1.0 * df["put_gamma"] * df["put_open_interest"] * gex_multiplier
    df["net_gex"] = df["call_gex"] + df["put_gex"]

    # Express GEX in Millions ($M) for readable charts & metrics
    df["call_gex_m"] = df["call_gex"] / 1e6
    df["put_gex_m"] = df["put_gex"] / 1e6
    df["net_gex_m"] = df["net_gex"] / 1e6

    # Totals
    df["total_oi"] = df["call_open_interest"] + df["put_open_interest"]
    df["total_volume"] = df["call_volume"] + df["put_volume"]

    # Vol / OI Ratios
    df["call_vol_oi_ratio"] = df["call_volume"] / np.maximum(1, df["call_open_interest"])
    df["put_vol_oi_ratio"] = df["put_volume"] / np.maximum(1, df["put_open_interest"])
    df["total_vol_oi_ratio"] = df["total_volume"] / np.maximum(1, df["total_oi"])

    # Strike Distance from Spot %
    df["distance_from_spot_pct"] = ((df["strike"] - spot_price) / spot_price) * 100.0

    return df

def find_gex_key_levels(df: pd.DataFrame, spot_price: float) -> Dict[str, Any]:
    """
    Identifies Call Wall, Put Wall, King Node, and interpolates Gamma Flip Level.
    """
    if df.empty:
        return {
            "call_wall": spot_price,
            "put_wall": spot_price,
            "king_node": spot_price,
            "gamma_flip": spot_price,
            "net_gex_total_m": 0.0,
            "call_gex_total_m": 0.0,
            "put_gex_total_m": 0.0,
            "king_net_gex_m": 0.0,
        }

    # Call Wall: Max Positive Call GEX strike
    call_wall_row = df.loc[df["call_gex_m"].idxmax()] if not df.empty else None
    call_wall = float(call_wall_row["strike"]) if call_wall_row is not None else spot_price

    # Put Wall: Max Absolute Put GEX strike (most negative put_gex_m)
    put_wall_row = df.loc[df["put_gex_m"].idxmin()] if not df.empty else None
    put_wall = float(put_wall_row["strike"]) if put_wall_row is not None else spot_price

    # King Node: Max Net GEX strike (or highest absolute net GEX concentration)
    king_row = df.loc[df["net_gex_m"].abs().idxmax()] if not df.empty else None
    king_node = float(king_row["strike"]) if king_row is not None else spot_price
    king_net_gex_m = float(king_row["net_gex_m"]) if king_row is not None else 0.0

    # Gamma Flip (Zero Gamma Level): Exact price level near spot where Net GEX crosses 0
    df_sorted = df.sort_values("strike").reset_index(drop=True)
    net_vals = df_sorted["net_gex_m"].values
    strikes = df_sorted["strike"].values

    gamma_flip = spot_price

    if len(strikes) > 1:
        # Identify zero-crossings (sign flips) in Net GEX between adjacent strikes
        sign_changes = np.where(np.diff(np.signbit(net_vals)))[0]
        
        if len(sign_changes) > 0:
            # Pick sign-change transition closest to current spot price
            closest_idx = sign_changes[np.argmin(np.abs(strikes[sign_changes] - spot_price))]
            x0, x1 = strikes[closest_idx], strikes[closest_idx + 1]
            y0, y1 = net_vals[closest_idx], net_vals[closest_idx + 1]
            
            if y1 != y0:
                gamma_flip = float(x0 - y0 * (x1 - x0) / (y1 - y0))
            else:
                gamma_flip = float(x0)
        else:
            # Fallback to strike with absolute minimum Net GEX near spot price
            closest_idx = (df_sorted["strike"] - spot_price).abs().idxmin()
            gamma_flip = float(df_sorted.loc[closest_idx, "strike"])

    total_call_gex_m = float(df["call_gex_m"].sum())
    total_put_gex_m = float(df["put_gex_m"].sum())
    total_net_gex_m = float(df["net_gex_m"].sum())

    return {
        "call_wall": call_wall,
        "put_wall": put_wall,
        "king_node": king_node,
        "king_net_gex_m": king_net_gex_m,
        "gamma_flip": round(gamma_flip, 2),
        "net_gex_total_m": total_net_gex_m,
        "call_gex_total_m": total_call_gex_m,
        "put_gex_total_m": total_put_gex_m,
    }

def calculate_atm_straddle_move(df: pd.DataFrame, spot_price: float) -> Dict[str, Any]:
    """
    Computes ATM Straddle price, implied move percentage, and upper/lower expected move bounds.
    """
    if df.empty:
        return {
            "atm_strike": spot_price,
            "straddle_price": 0.0,
            "implied_move_pct": 0.0,
            "upper_bound": spot_price,
            "lower_bound": spot_price,
        }

    # Find strike closest to spot price
    df_sorted = df.copy()
    df_sorted["dist"] = (df_sorted["strike"] - spot_price).abs()
    atm_row = df_sorted.loc[df_sorted["dist"].idxmin()]
    
    atm_strike = float(atm_row["strike"])
    call_price = float(atm_row.get("call_last", 0.0) or 0.0)
    put_price = float(atm_row.get("put_last", 0.0) or 0.0)

    # Fallback to bid/ask midpoint if last is 0
    if call_price <= 0 and "call_bid" in atm_row and "call_ask" in atm_row:
        call_price = (float(atm_row["call_bid"]) + float(atm_row["call_ask"])) / 2.0
    if put_price <= 0 and "put_bid" in atm_row and "put_ask" in atm_row:
        put_price = (float(atm_row["put_bid"]) + float(atm_row["put_ask"])) / 2.0

    straddle_price = max(0.01, call_price + put_price)
    implied_move_pct = (straddle_price / spot_price) * 100.0

    return {
        "atm_strike": atm_strike,
        "straddle_price": round(straddle_price, 2),
        "implied_move_pct": round(implied_move_pct, 2),
        "upper_bound": round(spot_price + straddle_price, 2),
        "lower_bound": round(spot_price - straddle_price, 2),
    }

def calculate_pinning_score(
    spot_price: float,
    king_node: float,
    call_wall: float,
    put_wall: float,
    dte_days: float
) -> Dict[str, Any]:
    """
    Calculates Pinning Probability & Magnet Score based on wall proximity and DTE.
    """
    dist_to_king_pct = abs(spot_price - king_node) / spot_price * 100.0
    dist_to_call_wall_pct = abs(spot_price - call_wall) / spot_price * 100.0
    dist_to_put_wall_pct = abs(spot_price - put_wall) / spot_price * 100.0

    # Magnet strength increases as DTE approaches 0 and distance to wall drops
    time_factor = 1.0 / (0.2 + dte_days)
    king_magnet_score = max(5, min(98, int((100.0 / (1.0 + dist_to_king_pct * 2.0)) * time_factor * 0.4)))

    if king_magnet_score > 70:
        pin_rating = "HIGH (Strong Magnet)"
    elif king_magnet_score > 40:
        pin_rating = "MODERATE (Range Magnet)"
    else:
        pin_rating = "LOW (Breakout / Volatile)"

    return {
        "king_magnet_score": king_magnet_score,
        "pin_rating": pin_rating,
        "dist_king_pct": round(dist_to_king_pct, 2),
        "dist_call_wall_pct": round(dist_to_call_wall_pct, 2),
        "dist_put_wall_pct": round(dist_to_put_wall_pct, 2),
    }
