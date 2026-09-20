import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

def _get_config_var(key: str, default: str = "") -> str:
    """Helper to fetch config from Streamlit Secrets (cloud) or os.getenv/.env (local)."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)

# Public.com API Credentials
# Account ID: Brokerage Account Number
ACCOUNT_ID = _get_config_var("ACCOUNT_ID", "12345")

# Public.com API Secret Key (Generated in Public.com app under Account Settings > Security > API)
PUBLIC_SECRET_KEY = _get_config_var("PUBLIC_SECRET_KEY", _get_config_var("PUBLIC_API_KEY", "xxxxxxx"))

# Optional Dashboard Protection Password
APP_PASSWORD = _get_config_var("APP_PASSWORD", "")

# Default Dashboard Settings
DEFAULT_STRIKE_WINDOW_PCT = 10.0  # Default +/- 10%
DEFAULT_MIN_OI = 10               # Minimum open interest filter
DEFAULT_CACHE_TTL = 30            # Cache TTL in seconds

# Index Tickers (auto 0DTE/1DTE focus)
INDEX_TICKERS = {"SPX", "SPXW", "SPY", "QQQ", "NDX", "IWM", "RUT", "VIX"}
DEFAULT_INDEX_EXPIRATIONS_COUNT = 2   # 0DTE and 1DTE
DEFAULT_EQUITY_EXPIRATIONS_COUNT = 6  # Nearest 5 to 7 expirations

# Popular Ticker Quick Presets
PRESET_TICKERS = ["SPX", "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN"]
TRINITY_DEFAULT_TICKERS = ["SPX", "SPY", "QQQ"]

# Modern Dark Theme Color Palette
COLORS = {
    "background": "#0e1117",
    "card_bg": "#161b22",
    "card_border": "#30363d",
    "text_primary": "#f0f6fc",
    "text_secondary": "#8b949e",
    "call_gex": "#00e676",      # Bright Emerald Green for Calls
    "put_gex": "#ff5252",       # Vibrant Crimson Red for Puts
    "net_positive": "#00c853",  # Green
    "net_negative": "#d50000",  # Red
    "spot_line": "#00e5ff",     # Electric Cyan for Spot Price
    "call_wall": "#00e676",     # Call Wall Green
    "put_wall": "#ff1744",      # Put Wall Red
    "gamma_flip": "#ff9100",    # Amber/Orange for Zero Gamma Level
    "king_node": "#ffd700",     # Gold / Yellow for King Node highlight
    "king_bg": "#3a3200",       # Dark Gold background for King strike
    "expected_move": "rgba(0, 229, 255, 0.12)" # Light Cyan overlay
}
