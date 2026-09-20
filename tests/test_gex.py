import unittest
import pandas as pd
import numpy as np

from api.mock_data import generate_mock_options_chain, get_base_spot_price
from analytics.gex_calculator import (
    calculate_gex_df,
    find_gex_key_levels,
    calculate_atm_straddle_move,
    calculate_pinning_score
)
from analytics.signals import analyze_gamma_regime, get_interest_zones_and_signals

class TestGEXCalculator(unittest.TestCase):

    def setUp(self):
        self.symbol = "SPX"
        self.spot = 5680.0
        chain = generate_mock_options_chain(self.symbol, "2026-09-19", strike_window_pct=10.0)
        self.calls_df = pd.DataFrame(chain["calls"])
        self.puts_df = pd.DataFrame(chain["puts"])

    def test_gex_calculation(self):
        gex_df = calculate_gex_df(self.calls_df, self.puts_df, spot_price=self.spot, min_oi=5)
        self.assertFalse(gex_df.empty)
        self.assertIn("call_gex_m", gex_df.columns)
        self.assertIn("put_gex_m", gex_df.columns)
        self.assertIn("net_gex_m", gex_df.columns)
        self.assertIn("call_vol_oi_ratio", gex_df.columns)

    def test_key_levels(self):
        gex_df = calculate_gex_df(self.calls_df, self.puts_df, spot_price=self.spot, min_oi=5)
        levels = find_gex_key_levels(gex_df, spot_price=self.spot)
        self.assertIn("call_wall", levels)
        self.assertIn("put_wall", levels)
        self.assertIn("king_node", levels)
        self.assertIn("gamma_flip", levels)
        self.assertGreater(levels["call_wall"], 0)
        self.assertGreater(levels["put_wall"], 0)
        self.assertGreater(levels["king_node"], 0)

    def test_atm_straddle_move(self):
        gex_df = calculate_gex_df(self.calls_df, self.puts_df, spot_price=self.spot, min_oi=5)
        move = calculate_atm_straddle_move(gex_df, spot_price=self.spot)
        self.assertIn("straddle_price", move)
        self.assertIn("implied_move_pct", move)
        self.assertGreater(move["straddle_price"], 0)
        self.assertGreater(move["upper_bound"], move["lower_bound"])

    def test_gamma_regime_and_signals(self):
        gex_df = calculate_gex_df(self.calls_df, self.puts_df, spot_price=self.spot, min_oi=5)
        levels = find_gex_key_levels(gex_df, spot_price=self.spot)
        regime = analyze_gamma_regime(levels["net_gex_total_m"], self.spot, levels["gamma_flip"])
        self.assertIn("regime", regime)
        self.assertIn("is_long_gamma", regime)

        signals = get_interest_zones_and_signals(
            gex_df, self.spot, levels["gamma_flip"],
            levels["call_wall"], levels["put_wall"],
            levels["king_node"], 30.0
        )
        self.assertIsInstance(signals, list)

if __name__ == "__main__":
    unittest.main()
