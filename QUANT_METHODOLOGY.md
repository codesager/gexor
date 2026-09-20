# GEXOR — Quantitative & Derivatives Analytics Methodology Guide

> **Domain Reference Manual**: Complete mathematical foundations, derivatives theory, algorithms, and visualization mapping used in the GEXOR Gamma Exposure Research Platform.

---

## 1. Executive Summary & Market Microstructure Foundations

In modern equity and index options markets, **Options Market Makers (MMs)** handle the vast majority of retail and institutional order flow. MMs aim to remain delta-neutral (hedged against direct price direction). To maintain neutrality as spot prices change, MMs must continuously execute dynamic hedging trades in the underlying asset.

The direction of MM hedging depends entirely on whether MMs are **Long Gamma** or **Short Gamma**:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 SPOT PRICE MOVEMENT                     │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
          ┌───────────────────────────┐                   ┌───────────────────────────┐
          │  LONG GAMMA (Net GEX > 0) │                   │ SHORT GAMMA (Net GEX < 0) │
          └────────────┬──────────────┘                   └────────────┬──────────────┘
                       │                                               │
        ┌──────────────┴──────────────┐                 ┌──────────────┴──────────────┐
        ▼                             ▼                 ▼                             ▼
  Spot Price RISES             Spot Price FALLS   Spot Price RISES             Spot Price FALLS
  MMs SELL Underlying          MMs BUY Underlying MMs BUY Underlying           MMs SELL Underlying
  (Dampens Volatility)       (Dampens Volatility) (Amplifies Momentum)         (Amplifies Sell-off)
```

1. **Long Gamma Regime ($\text{Net GEX} > 0$)**:
   - Customers bought puts and sold calls $\rightarrow$ MMs are long gamma.
   - When spot rises, MM delta becomes increasingly positive $\rightarrow$ MMs **sell** shares/futures to re-hedge.
   - When spot falls, MM delta becomes increasingly negative $\rightarrow$ MMs **buy** shares/futures to re-hedge.
   - **Market Effect**: Volatility is suppressed, price mean-reverts towards high-concentration strikes (**King Node**).

2. **Short Gamma Regime ($\text{Net GEX} < 0$)**:
   - Customers bought calls and sold puts $\rightarrow$ MMs are short gamma.
   - When spot rises, MM delta becomes negative $\rightarrow$ MMs must **buy** underlying to re-hedge (pushes price higher).
   - When spot falls, MM delta becomes positive $\rightarrow$ MMs must **sell** underlying to re-hedge (accelerates sell-off).
   - **Market Effect**: Volatility expands, leading to rapid trend acceleration and potential gamma squeezes.

---

## 2. Options Greeks & Black-Scholes Foundations

### 2.1 Black-Scholes Model & Option Pricing
Under the Black-Scholes-Merton model, the price of a European call ($C$) and put ($P$) with strike $K$, spot price $S$, risk-free rate $r$, implied volatility $\sigma$, and time to expiration $T$ (in years) is given by:

\[
d_1 = \frac{\ln(S / K) + \left(r + \frac{\sigma^2}{2}\right)T}{\sigma \sqrt{T}}, \quad d_2 = d_1 - \sigma \sqrt{T}
\]

\[
C = S \cdot N(d_1) - K e^{-r T} N(d_2)
\]

\[
P = K e^{-r T} N(-d_2) - S \cdot N(-d_1)
\]

where $N(x)$ is the cumulative standard normal distribution function, and $N'(x) = \frac{1}{\sqrt{2\pi}} e^{-x^2 / 2}$ is the standard normal probability density function (PDF).

### 2.2 Option Gamma ($\Gamma$)
Option **Gamma** ($\Gamma$) is the second derivative of the option price with respect to spot price $S$, or equivalently, the rate of change of option **Delta** ($\Delta$) per \$1 move in the underlying asset:

\[
\Gamma = \frac{\partial^2 C}{\partial S^2} = \frac{\partial \Delta}{\partial S} = \frac{N'(d_1)}{S \cdot \sigma \sqrt{T}}
\]

**Key Properties of Gamma**:
- Gamma is strictly positive ($\Gamma > 0$) for long positions in both Calls and Puts.
- Gamma peaks at At-The-Money (ATM) strikes ($S \approx K$) and decays rapidly as $T \to 0$ for Out-Of-The-Money (OTM) strikes.
- Short-dated options (0DTE/1DTE) exhibit extreme ATM Gamma concentration.

---

## 3. Dollar Notional Gamma Exposure (GEX) Calculation

### 3.1 Mathematical Derivation
To convert theoretical option Gamma into dollar notional market impact per **1% move in underlying spot price**, GEXOR calculates Notional GEX as follows:

Let $S$ be the underlying spot price, $\Gamma_i$ be the option gamma for strike $K_i$, and $\text{OI}_i$ be open interest.

Each option contract controls 100 shares. A 1% move in spot price equals $\Delta S = 0.01 \times S$.
The change in delta for 100 shares per 1% move is:

\[
\Delta \text{Delta (Shares)} = \Gamma_i \times \text{OI}_i \times 100 \times (0.01 \times S)
\]

Multiplying by spot price $S$ converts the share volume into total dollar value:

\[
\text{Dollar GEX}_i = \Gamma_i \times \text{OI}_i \times 100 \times (0.01 \times S) \times S = \Gamma_i \times \text{OI}_i \times S^2
\]

### 3.2 Call, Put, and Net GEX Equations
- **Call GEX (\$)**:
  \[
  \text{GEX}_{\text{Call}}(K_i) = \Gamma_{\text{Call}, i} \times \text{OI}_{\text{Call}, i} \times S^2
  \]
- **Put GEX (\$)**: (Puts represent negative market maker gamma exposure)
  \[
  \text{GEX}_{\text{Put}}(K_i) = -1.0 \times \Gamma_{\text{Put}, i} \times \text{OI}_{\text{Put}, i} \times S^2
  \]
- **Net GEX (\$ Millions)**:
  \[
  \text{Net GEX}_M(K_i) = \frac{\text{GEX}_{\text{Call}}(K_i) + \text{GEX}_{\text{Put}}(K_i)}{1,000,000}
  \]

### 3.3 Implementation in Code
Located in [`analytics/gex_calculator.py`](file:///e:/quant-experimentz/gexor/analytics/gex_calculator.py#L56-L68):

```python
# Factor = 100 * spot^2 * 0.01 = 1.0 * spot^2
gex_multiplier = spot_price * spot_price * 1.0

df["call_gex"] = df["call_gamma"] * df["call_open_interest"] * gex_multiplier
df["put_gex"] = -1.0 * df["put_gamma"] * df["put_open_interest"] * gex_multiplier
df["net_gex"] = df["call_gex"] + df["put_gex"]

# Express in Millions ($M)
df["call_gex_m"] = df["call_gex"] / 1e6
df["put_gex_m"] = df["put_gex"] / 1e6
df["net_gex_m"] = df["net_gex"] / 1e6
```

---

## 4. Key Quantitative Levels Engine

GEXOR scans the option chain across strikes to identify four critical institutional levels:

```
─────────────────────────────────────────────────────────────────────────────
 LEVEL             FORMULA / ALGORITHM               TRADING IMPLICATION
─────────────────────────────────────────────────────────────────────────────
 Call Wall         K with max(Call_GEX_M)            Heavy overhead resistance ceiling.
 Put Wall          K with min(Put_GEX_M)             Strong downside support floor.
 King Node         K with max(|Net_GEX_M|)           Primary market magnet / pin target.
 Gamma Flip        K where Net_GEX(K) = 0            Regime shift (Long GEX <-> Short GEX).
─────────────────────────────────────────────────────────────────────────────
```

### 4.1 Call Wall & Put Wall
- **Call Wall**: The strike price containing the single largest positive Call GEX concentration. Option sellers at this strike have sold significant call volume, obligating MMs to sell underlying shares as price approaches this strike from below.
  \[
  K_{\text{Call Wall}} = \arg\max_{K_i} \left( \text{Call GEX}_M(K_i) \right)
  \]
- **Put Wall**: The strike price containing the largest negative Put GEX magnitude. Acts as a major structural support floor.
  \[
  K_{\text{Put Wall}} = \arg\min_{K_i} \left( \text{Put GEX}_M(K_i) \right)
  \]

### 4.2 King Node (Primary Market Magnet)
The **King Node** is the strike price with the single highest absolute Net GEX magnitude in the option chain.
\[
K_{\text{King}} = \arg\max_{K_i} \left| \text{Net GEX}_M(K_i) \right|
\]
Because MM hedging intensity peaks at this strike, price is magnetically pulled towards the King Node on expiration days (0DTE pinning effect).

### 4.3 Gamma Flip Level (Zero Gamma Level)
The **Gamma Flip Level** ($K_{\text{flip}}$) is the exact underlying price level where Net GEX transitions from negative to positive.

**Linear Interpolation Algorithm**:
1. Sort options chain by strike $K_i$.
2. Locate the adjacent strike pair $(K_0, K_1)$ near current spot price where $\text{Net GEX}_M(K_0) \le 0$ and $\text{Net GEX}_M(K_1) > 0$.
3. Linearly interpolate the zero-crossing price:
   \[
   K_{\text{flip}} = K_0 - \text{GEX}_0 \times \frac{K_1 - K_0}{\text{GEX}_1 - \text{GEX}_0}
   \]

Located in [`analytics/gex_calculator.py`](file:///e:/quant-experimentz/gexor/analytics/gex_calculator.py#L112-L137):

```python
sign_changes = np.where(np.diff(np.signbit(net_vals)))[0]
if len(sign_changes) > 0:
    closest_idx = sign_changes[np.argmin(np.abs(strikes[sign_changes] - spot_price))]
    x0, x1 = strikes[closest_idx], strikes[closest_idx + 1]
    y0, y1 = net_vals[closest_idx], net_vals[closest_idx + 1]
    gamma_flip = float(x0 - y0 * (x1 - x0) / (y1 - y0)) if y1 != y0 else float(x0)
```

---

## 5. Volatility, Expected Move & Pinning Models

### 5.1 ATM Straddle Price & Implied Move
The **ATM Straddle** measures the market's expected price move (volatility pricing) for a given expiration.

\[
P_{\text{Straddle}} = P_{\text{ATM Call}} + P_{\text{ATM Put}}
\]

\[
\text{Implied Move \%} = \frac{P_{\text{Straddle}}}{S} \times 100\%
\]

\[
\text{Expected Move Bounds} = \left[ S - P_{\text{Straddle}}, \; S + P_{\text{Straddle}} \right]
\]

### 5.2 0DTE Magnet Pinning Score
Quantifies the probability of price pinning to the King Node on expiration day.

\[
D_{\text{King\%}} = \frac{|S - K_{\text{King}}|}{S} \times 100
\]

\[
\text{Pinning Score} = \text{clamp}\left( \frac{100}{1 + 2 \cdot D_{\text{King\%}}} \times \frac{1}{0.2 + \text{DTE}} \times 0.4, \; 5, \; 98 \right)
\]

- Score $> 70\%$: **HIGH Pinning Magnet** (Low volatility expected, price pinned to King Node).
- Score $< 40\%$: **LOW Pinning Magnet** (High volatility / trend breakout expected).

---

## 6. Institutional Trade Signal Generator

Located in [`analytics/signals.py`](file:///e:/quant-experimentz/gexor/analytics/signals.py#L30-L136), GEXOR scans the options matrix for institutional trade setups:

1. **King Magnet Target**:
   - Condition: $K = K_{\text{King}}$.
   - Action: `MAGNET / TARGET`. Price tends to gravitate to this strike.
2. **Call Wall Resistance**:
   - Condition: $K = K_{\text{Call Wall}}$.
   - Action: `SELL CALLS / CREDIT SPREAD`. Overhead supply ceiling.
3. **Put Wall Support**:
   - Condition: $K = K_{\text{Put Wall}}$.
   - Action: `SELL PUTS / CREDIT SPREAD`. Heavy institutional put floor.
4. **Bullish Call Accumulation**:
   - Condition: $K > S$, $\text{Vol/OI} > 1.2x$, $\text{Call OI} \ge 50$.
   - Action: `BUY CALLS / DEBIT SPREAD`. Institutional call buying activity.
5. **Bearish Put Accumulation / Hedge**:
   - Condition: $K < S$, $\text{Vol/OI} > 1.2x$, $\text{Put OI} \ge 50$.
   - Action: `BUY PUTS / HEDGE`. Institutional downside hedging.

---

## 7. Complete Dashboard Visualization Mapping

The mathematical outputs map directly to GEXOR visual interface components:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. KPI Metric Header Cards (app.py -> render_kpi_header)                   │
├──────────────┬──────────────┬──────────────┬────────────────┬───────────────┤
│ Spot Price   │ Net GEX Total│ King Node    │ Walls          │ Gamma Flip    │
│ $7,650.50    │ +$507.2M     │ 7650 ★       │ 7700 / 7625    │ 7,648.5       │
└──────────────┴──────────────┴──────────────┴────────────────┴───────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Regime Alert Banner (app.py -> render_regime_banner)                     │
│ REGIME: SHORT GAMMA (Volatile / Trend Acceleration) | Pinning Score: 5% LOW │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Primary Net GEX Bar Chart (components/charts.py -> create_gex_bar_chart) │
│ - Emerald Green Bars: Positive Net GEX (Call dominance)                     │
│ - Crimson Red Bars: Negative Net GEX (Put dominance)                        │
│ - Vertical Cyan Line: Current Spot Price                                    │
│ - Vertical Dashed Green Line: Call Wall                                     │
│ - Vertical Dashed Red Line: Put Wall                                        │
│ - Vertical Dotted Amber Line: Gamma Flip Level                              │
│ - Gold Star Annotation: 👑 KING Node ★                                      │
│ - Shaded Cyan Overlay: Expected Move Band (±%)                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Heatmap Grid (components/heatmap.py)                                     │
│ - Y-Axis: Strike prices (sorted descending)                                 │
│ - X-Axis: Expiration dates                                                  │
│ - White Pointer Badge: Highlighting active Spot Strike (e.g. [ 7650.0 ])    │
│ - Yellow Gold Pill: Highlighting per-column King Nodes ($16,227.4K★)        │
│ - Teal/Emerald Gradient: Positive Net GEX cells                             │
│ - Indigo/Purple Gradient: Negative Net GEX cells                            │
│ - 850px Expanded Container: Fits 30+ strike rows without vertical scroll    │
│ - Default Strike Focus: ±$100 Dollar Offset around Spot Price               │
│ - Center Viewport Auto-Scroll: Keeps King Node in vertical center           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Trinity Multi-Ticker 0DTE View (app.py -> render_trinity_multi_ticker)   │
│ - Side-by-side Heatmap Grids for custom tickers (free-text input, up to 6 max)│
│ - Auto-centered King Node and Spot Price badges for multi-ticker 0DTE comparison│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Quick Reference Summary

- **Net GEX Formula**:
  \[
  \text{Net GEX}_M = \frac{(\Gamma_{\text{Call}} \cdot \text{OI}_{\text{Call}} - \Gamma_{\text{Put}} \cdot \text{OI}_{\text{Put}}) \times S^2}{10^6}
  \]
- **Gamma Flip**: Zero-crossing of Net GEX near spot price ($S$).
- **Long Gamma**: $\text{Net GEX} > 0$ and $S \ge K_{\text{flip}}$ $\rightarrow$ Volatility suppressed.
- **Short Gamma**: $\text{Net GEX} < 0$ or $S < K_{\text{flip}}$ $\rightarrow$ Volatility expanded.
