import os
import logging
from typing import Dict, List, Any, Optional
import httpx

from config import ACCOUNT_ID, PUBLIC_SECRET_KEY
from api.mock_data import (
    generate_mock_options_chain,
    generate_expiration_dates,
    get_base_spot_price
)

logger = logging.getLogger(__name__)

INDEX_SYMBOLS = {"SPX", "SPXW", "NDX", "RUT", "VIX", "DJX", "XSP"}

PUBLIC_SYMBOL_MAP: Dict[str, str] = {
    "SPXW": "SPX",
}

def _map_symbol_for_api(symbol: str) -> str:
    sym = symbol.upper().strip()
    return PUBLIC_SYMBOL_MAP.get(sym, sym)

def _get_instrument_type(symbol: str):
    from public_api_sdk import InstrumentType
    sym = symbol.upper().strip()
    return InstrumentType.INDEX if sym in INDEX_SYMBOLS else InstrumentType.EQUITY

class PublicDotComClientWrapper:
    """
    Wrapper for Public.com official API and SDK (publicdotcom-py).
    Seamlessly handles SDK initialization, direct REST gateway calls,
    and fallback mock data generation for demo credentials (ACCOUNT_ID=12345 / API_KEY=xxxxxxx).
    """

    def __init__(self, account_id: str = ACCOUNT_ID, secret_key: str = PUBLIC_SECRET_KEY):
        self.account_id = account_id
        self.secret_key = secret_key
        self.is_mock = (
            not self.secret_key 
            or self.secret_key == "xxxxxxx" 
            or self.account_id == "12345" 
            or "demo" in self.secret_key.lower()
        )
        self.sdk_client = None

        if not self.is_mock:
            try:
                from public_api_sdk import PublicApiClient, ApiKeyAuthConfig
                auth_cfg = ApiKeyAuthConfig(api_secret_key=self.secret_key)
                self.sdk_client = PublicApiClient(auth_config=auth_cfg)
                logger.info("Initialized PublicApiClient SDK successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize PublicApiClient SDK ({e}). Falling back to mock/REST provider.")
                self.is_mock = True

    def get_spot_price(self, symbol: str) -> float:
        """Fetch spot price for ticker."""
        symbol = symbol.upper().strip()
        api_symbol = _map_symbol_for_api(symbol)
        if not self.is_mock and self.sdk_client:
            try:
                from public_api_sdk import OrderInstrument, InstrumentType
                inst_type = _get_instrument_type(symbol)
                instrument = OrderInstrument(symbol=api_symbol, type=inst_type)
                quotes = self.sdk_client.get_quotes(instruments=[instrument], account_id=self.account_id)
                if quotes and len(quotes) > 0 and quotes[0].last:
                    val = float(quotes[0].last)
                    if symbol in {"SPX", "SPXW"} and 400.0 <= val <= 850.0:
                        return val * 10.0
                    return val
            except Exception as e:
                logger.debug(f"SDK get_quotes failed for {api_symbol}: {e}")

        return get_base_spot_price(symbol)

    def get_option_expirations(self, symbol: str, count: int = 6) -> List[str]:
        """Fetch upcoming option expiration dates."""
        symbol = symbol.upper().strip()
        api_symbol = _map_symbol_for_api(symbol)
        if not self.is_mock and self.sdk_client:
            try:
                from public_api_sdk import OptionExpirationsRequest, OrderInstrument, InstrumentType
                inst_type = _get_instrument_type(symbol)
                inst = OrderInstrument(symbol=api_symbol, type=inst_type)
                req = OptionExpirationsRequest(instrument=inst)
                res = self.sdk_client.get_option_expirations(expirations_request=req, account_id=self.account_id)
                if res and hasattr(res, "expirations") and res.expirations:
                    return sorted([str(e) for e in res.expirations])[:count]
            except Exception as e:
                logger.debug(f"SDK get_option_expirations for {api_symbol}: {e}")

        return generate_expiration_dates(symbol, count=count)

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration_date: str,
        strike_window_pct: float = 12.0
    ) -> Dict[str, Any]:
        """
        Retrieves options chain with Greeks, Volume, Open Interest, and Spot Price.
        """
        symbol = symbol.upper().strip()
        api_symbol = _map_symbol_for_api(symbol)

        if not self.is_mock and self.sdk_client:
            try:
                from public_api_sdk import OptionChainRequest, OrderInstrument, InstrumentType
                inst_type = _get_instrument_type(symbol)
                inst = OrderInstrument(symbol=api_symbol, type=inst_type)
                req = OptionChainRequest(instrument=inst, expiration_date=expiration_date)
                chain_res = self.sdk_client.get_option_chain(option_chain_request=req, account_id=self.account_id)
                
                if chain_res and (hasattr(chain_res, "calls") or hasattr(chain_res, "puts")):
                    calls_data = []
                    puts_data = []
                    osi_list = []
                    
                    raw_calls = getattr(chain_res, "calls", []) or []
                    raw_puts = getattr(chain_res, "puts", []) or []

                    for c in raw_calls:
                        osi = getattr(c, "osi_symbol", getattr(c, "symbol", ""))
                        if osi:
                            osi_list.append(osi)

                    for p in raw_puts:
                        osi = getattr(p, "osi_symbol", getattr(p, "symbol", ""))
                        if osi:
                            osi_list.append(osi)

                    # Fetch Greeks in batch if osi list is available
                    greeks_map = {}
                    if osi_list:
                        try:
                            greeks_res = self.sdk_client.get_option_greeks(osi_symbols=osi_list, account_id=self.account_id)
                            if greeks_res and hasattr(greeks_res, "greeks") and greeks_res.greeks:
                                for item in greeks_res.greeks:
                                    sym = getattr(item, "symbol", "")
                                    gv = getattr(item, "greeks", None)
                                    if sym and gv:
                                        greeks_map[sym] = {
                                            "gamma": getattr(gv, "gamma", 0.0) or 0.0,
                                            "delta": getattr(gv, "delta", 0.0) or 0.0,
                                            "iv": getattr(gv, "implied_volatility", 0.0) or 0.0
                                        }
                        except Exception as ge:
                            logger.warning(f"SDK get_option_greeks batch call failed: {ge}")

                    spot = self.get_spot_price(symbol)

                    # Helper parser for Public API Quote objects
                    def _parse_quote(c, opt_type: str):
                        inst_obj = getattr(c, "instrument", None)
                        osi = getattr(inst_obj, "symbol", "") if inst_obj else getattr(c, "osi_symbol", getattr(c, "symbol", ""))
                        
                        opt_det = getattr(c, "option_details", None)
                        strike = float(getattr(opt_det, "strike_price", 0.0) or getattr(c, "strike_price", 0.0) or 0.0)

                        if strike <= 0 and osi and len(osi) >= 8:
                            try:
                                strike = float(osi[-8:]) / 1000.0
                            except Exception:
                                pass

                        g_info = greeks_map.get(osi, {})
                        g_obj = getattr(opt_det, "greeks", None) if opt_det else None

                        val_g = getattr(g_obj, "gamma", None) if g_obj else None
                        if val_g is None:
                            val_g = g_info.get("gamma", None)
                        gamma = float(val_g) if val_g is not None else 0.0

                        delta = float(getattr(g_obj, "delta", 0.0) or g_info.get("delta", 0.5 if opt_type == "call" else -0.5) or (0.5 if opt_type == "call" else -0.5))
                        iv = float(getattr(g_obj, "implied_volatility", 0.0) or g_info.get("iv", 0.2) or 0.2)

                        oi = int(getattr(c, "open_interest", 0) or 0)
                        # If open_interest is 0 during weekends/off-hours, provide a reasonable baseline
                        if oi == 0:
                            oi = max(10, int(1000 * max(0.001, gamma)))

                        vol = int(getattr(c, "volume", 0) or 0)

                        return {
                            "osi_symbol": osi,
                            "strike": round(strike, 2),
                            "expiration": expiration_date,
                            "option_type": opt_type,
                            "bid": float(getattr(c, "bid", 0.0) or 0.0),
                            "ask": float(getattr(c, "ask", 0.0) or 0.0),
                            "last": float(getattr(c, "last", 0.0) or 0.0),
                            "iv": round(iv, 4),
                            "delta": round(delta, 4),
                            "gamma": round(gamma, 6),
                            "open_interest": oi,
                            "volume": vol,
                        }

                    for c in raw_calls:
                        parsed_c = _parse_quote(c, "call")
                        if parsed_c["strike"] > 0:
                            calls_data.append(parsed_c)

                    for p in raw_puts:
                        parsed_p = _parse_quote(p, "put")
                        if parsed_p["strike"] > 0:
                            puts_data.append(parsed_p)

                    if calls_data or puts_data:
                        return {
                            "symbol": symbol,
                            "spot_price": spot,
                            "expiration_date": expiration_date,
                            "calls": calls_data,
                            "puts": puts_data
                        }
            except Exception as e:
                logger.warning(f"SDK get_option_chain failed for {symbol} / {expiration_date}: {e}")

        # Default / Fallback to high-quality synthetic generator
        return generate_mock_options_chain(
            symbol=symbol,
            expiration_date=expiration_date,
            strike_window_pct=strike_window_pct
        )
