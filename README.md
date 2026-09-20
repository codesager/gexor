# GEXOR — Options Gamma Exposure (GEX) Research Platform

GEXOR is a high-performance quantitative options analytics platform and interactive research dashboard built for tracking Market Maker Gamma Exposure (GEX), key support/resistance levels, gamma regimes, and 0DTE options dynamics.

---

## 📚 Quantitative Foundations & Methodology

For a complete mathematical manual explaining all Black-Scholes formulas, Notional GEX derivations, Gamma Flip algorithms, and visualization mappings, read:

👉 **[QUANT_METHODOLOGY.md](QUANT_METHODOLOGY.md)**

---

## ⚡ Key Features

1. **Live & SDK Options Data Provider**:
   - Integrates directly with Public.com API / SDK (`publicdotcom-py`).
   - Seamless fallback generator for demo mode and market off-hours.

2. **Quantitative GEX Engine**:
   - Calculates **Call GEX**, **Put GEX**, and **Net GEX ($M)** per 1% spot move.
   - Computes **Call Wall**, **Put Wall**, **King Node (Magnet)**, and **Gamma Flip (Zero GEX)** level.

3. **Heatmap Grid**:
   - Numeric matrix grid table with formatted `$K`/`$M` cell values.
   - Dynamic white pointer badge for active spot price strike (e.g. `7650.0` / `568.0`).
   - Glowing gold `#FFD700` pills for King Nodes (`👑 7650★`).
   - Viewport auto-centering, 850px expanded height, and default $\pm \$100$ dollar offset strike focus.

4. **0DTE Multi-Ticker Matrix (Trinity View)**:
   - Free-text input allowing custom side-by-side 0DTE comparison for up to 6 tickers (e.g. SPX, SPY, QQQ, NVDA, TSLA, AAPL).

5. **High-Signal Trade Generator**:
   - Detects institutional call/put volume spikes ($\text{Vol/OI} > 1.2x$), credit spread levels, and magnet targets.

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10+
- `uv` package manager (or `pip`)

### Running locally:
```bash
# Run Streamlit dashboard using uv
uv run streamlit run app.py
```

### Running unit tests:
```bash
uv run python -m unittest discover tests
```
