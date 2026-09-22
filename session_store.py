import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

SESSION_FILE = os.path.join(os.path.dirname(__file__), ".gexor_session.json")

DEFAULT_SESSION = {
    "authenticated": False,
    "active_ticker": "SPX",
    "gex_formula_mode": "Standard Notional ($S²)",
    "strike_window": 12.0,
    "min_oi_filter": 10,
    "trinity_input": "SPX, SPY, QQQ",
    "active_tab": "📊 Single Ticker Deep Dive",
    "user_timezone": "Auto-Detect Local Time"
}

PERSISTENT_KEYS = {
    "authenticated",
    "active_ticker",
    "gex_formula_mode",
    "strike_window",
    "min_oi_filter",
    "trinity_input",
    "active_tab",
    "user_timezone"
}

def load_session() -> Dict[str, Any]:
    """Loads saved session and user preferences from disk."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                session = DEFAULT_SESSION.copy()
                for k, v in data.items():
                    if k in PERSISTENT_KEYS:
                        session[k] = v
                return session
        except Exception as e:
            logger.warning(f"Could not load session file ({e}). Resetting to default.")
    return DEFAULT_SESSION.copy()

def save_session(session_dict: Dict[str, Any]):
    """Saves session state and user preferences to disk."""
    try:
        data_to_save = {
            k: v for k, v in session_dict.items() 
            if k in PERSISTENT_KEYS and isinstance(v, (str, int, float, bool))
        }
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save session file: {e}")
