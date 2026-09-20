import math
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
from scipy.stats import norm

# Standard reference prices for common tickers
TICKER_SPOT_PRESETS = {
    "SPX": 5680.0,
    "SPXW": 5680.0,
    "SPY": 568.0,
    "QQQ": 485.0,
    "NDX": 19800.0,
    "IWM": 218.0,
    "NVDA": 118.0,
    "TSLA": 235.0,
    "AAPL": 222.0,
    "AMD": 152.0,
    "MSFT": 430.0,
    "AMZN": 186.0,
    "META": 515.0,
    "GOOGL": 172.0,
}

def get_base_spot_price(symbol: str) -> float:
    """Returns realistic base spot price for any symbol."""
    sym = symbol.upper().strip()
    if sym in TICKER_SPOT_PRESETS:
        return TICKER_SPOT_PRESETS[sym]
    # For any unknown symbol, derive a reproducible deterministic price based on hash
    seed = sum(ord(c) for c in sym)
    return round(50.0 + (seed % 350) + (seed % 100) * 0.25, 2)

def generate_expiration_dates(symbol: str, count: int = 6) -> List[str]:
    """Generates realistic upcoming expiration dates."""
    today = date.today()
    expirations = []
    
    # 0DTE (today if weekday, else next Monday)
    curr = today
    while curr.weekday() >= 5: # Saturday/Sunday -> Monday
        curr += timedelta(days=1)
    
    # Generate requested number of upcoming expirations (daily for 0DTE/1DTE, then weekly/monthly)
    d = curr
    for i in range(count * 2):
        if len(expirations) >= count:
            break
        # Skip weekends
        if d.weekday() < 5:
            date_str = d.strftime("%Y-%m-%d")
            if date_str not in expirations:
                expirations.append(date_str)
        # For index tickers, include daily expirations; for equities, step by 2-5 days
        step = 1 if i < 3 else (3 if d.weekday() == 4 else 1)
        d += timedelta(days=step)
        
    return sorted(expirations)[:count]

def black_scholes_greeks(
    spot: float,
    strike: float,
    dte_years: float,
    iv: float,
    r: float = 0.05,
    option_type: str = "call"
) -> Tuple[float, float, float]:
    """Calculates Black-Scholes Delta, Gamma, and Price."""
    if dte_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.5, 0.01, max(0.01, spot - strike if option_type == "call" else strike - spot)
        
    d1 = (math.log(spot / strike) + (r + 0.5 * iv ** 2) * dte_years) / (iv * math.sqrt(dte_years))
    d2 = d1 - iv * math.sqrt(dte_years)
    
    gamma = norm.pdf(d1) / (spot * iv * math.sqrt(dte_years))
    
    if option_type.lower() == "call":
        delta = norm.cdf(d1)
        price = spot * norm.cdf(d1) - strike * math.exp(-r * dte_years) * norm.cdf(d2)
    else:
        delta = -norm.cdf(-d1)
        price = strike * math.exp(-r * dte_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)
        
    return float(delta), float(gamma), max(0.01, float(price))

def generate_mock_options_chain(
    symbol: str,
    expiration_date: str,
    strike_window_pct: float = 12.0
) -> Dict[str, Any]:
    """
    Generates realistic synthetic options chain data for a given ticker and expiration date.
    Includes strike, mid price, bid/ask, IV, delta, gamma, open interest, and volume.
    """
    symbol = symbol.upper().strip()
    spot = get_base_spot_price(symbol)
    
    # Calculate DTE
    try:
        exp_d = datetime.strptime(expiration_date, "%Y-%m-%d").date()
        today = date.today()
        dte_days = max(0.1, (exp_d - today).days)
    except Exception:
        dte_days = 1.0
    
    dte_years = dte_days / 365.0
    
    # Determine strike interval based on spot price level
    if spot > 3000:
        strike_step = 5.0
    elif spot > 500:
        strike_step = 1.0
    elif spot > 100:
        strike_step = 1.0
    elif spot > 20:
        strike_step = 0.5
    else:
        strike_step = 0.25
        
    min_strike = math.floor((spot * (1.0 - strike_window_pct / 100.0)) / strike_step) * strike_step
    max_strike = math.ceil((spot * (1.0 + strike_window_pct / 100.0)) / strike_step) * strike_step
    
    strikes = np.arange(min_strike, max_strike + strike_step * 0.5, strike_step)
    
    # Deterministic random seed per ticker + expiration for consistent updates
    seed = (sum(ord(c) for c in symbol) + int(exp_d.strftime("%Y%m%d"))) % 10000
    np.random.seed(seed)
    
    # Baseline Volatility curve (Volatility Smile / Skew)
    base_iv = 0.18 if "SPX" in symbol or "SPY" in symbol else 0.35
    iv_smile = base_iv + 0.08 * ((strikes - spot) / spot) ** 2 - 0.05 * ((strikes - spot) / spot)
    
    calls = []
    puts = []
    
    for i, K in enumerate(strikes):
        iv = max(0.08, float(iv_smile[i]))
        
        # Open interest distribution with wall spikes near key round numbers
        dist_from_spot = abs(K - spot) / spot
        base_oi = int(10000 * math.exp(-12.0 * dist_from_spot))
        
        # Inject key wall spikes on round strikes (e.g. 5700, 5650, 480, 220)
        is_call_wall_candidate = (K > spot) and (K % (strike_step * 10) == 0 or K % (strike_step * 5) == 0)
        is_put_wall_candidate = (K < spot) and (K % (strike_step * 10) == 0 or K % (strike_step * 5) == 0)
        
        call_oi_mult = 3.5 if is_call_wall_candidate else (1.0 + 0.5 * np.random.rand())
        put_oi_mult = 4.2 if is_put_wall_candidate else (1.0 + 0.5 * np.random.rand())
        
        call_oi = max(50, int(base_oi * call_oi_mult + np.random.randint(100, 1500)))
        put_oi = max(50, int(base_oi * put_oi_mult + np.random.randint(100, 1500)))
        
        # Volume generation (some strikes experience heavy volume spikes -> high Vol/OI ratio)
        vol_spike_call = 4.0 if (i % 7 == 2) else 0.4
        vol_spike_put = 3.5 if (i % 7 == 5) else 0.4
        
        call_vol = int(call_oi * (0.15 + 0.3 * np.random.rand() * vol_spike_call))
        put_vol = int(put_oi * (0.15 + 0.3 * np.random.rand() * vol_spike_put))
        
        # Calculate Greeks & Prices
        c_delta, c_gamma, c_price = black_scholes_greeks(spot, K, dte_years, iv, option_type="call")
        p_delta, p_gamma, p_price = black_scholes_greeks(spot, K, dte_years, iv, option_type="put")
        
        osi_call = f"{symbol}{exp_d.strftime('%y%m%d')}C{int(K*1000):08d}"
        osi_put = f"{symbol}{exp_d.strftime('%y%m%d')}P{int(K*1000):08d}"
        
        calls.append({
            "osi_symbol": osi_call,
            "strike": round(float(K), 2),
            "expiration": expiration_date,
            "option_type": "call",
            "bid": round(c_price * 0.98, 2),
            "ask": round(c_price * 1.02, 2),
            "last": round(c_price, 2),
            "iv": round(iv, 4),
            "delta": round(c_delta, 4),
            "gamma": round(c_gamma, 6),
            "open_interest": call_oi,
            "volume": call_vol,
        })
        
        puts.append({
            "osi_symbol": osi_put,
            "strike": round(float(K), 2),
            "expiration": expiration_date,
            "option_type": "put",
            "bid": round(p_price * 0.98, 2),
            "ask": round(p_price * 1.02, 2),
            "last": round(p_price, 2),
            "iv": round(iv, 4),
            "delta": round(p_delta, 4),
            "gamma": round(p_gamma, 6),
            "open_interest": put_oi,
            "volume": put_vol,
        })
        
    return {
        "symbol": symbol,
        "spot_price": spot,
        "expiration_date": expiration_date,
        "dte_days": dte_days,
        "calls": calls,
        "puts": puts
    }
