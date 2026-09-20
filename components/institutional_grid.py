import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, Any, Optional

def _format_grid_val(val: float, is_currency: bool = True) -> str:
    """Format cell value into quantitative ($K or $M) matrix string."""
    if pd.isna(val) or abs(val) < 1e-6:
        return "$0.0K" if is_currency else "0"
    
    val_k = val * 1000.0  # Input is in $M, convert to $K
    prefix = "$" if is_currency else ""
    sign = "-" if val < 0 else ""
    abs_k = abs(val_k)
    
    if abs_k >= 100000.0:
        return f"{sign}{prefix}{abs_k:,.0f}K"
    elif abs_k >= 1000.0:
        return f"{sign}{prefix}{abs_k:,.1f}K"
    elif abs_k >= 1.0:
        return f"{sign}{prefix}{abs_k:.1f}K"
    else:
        return f"{sign}{prefix}{abs_k:.1f}K"

def _get_cell_bg_style(val: float, max_abs_val: float, is_king: bool = False) -> str:
    """Computes quantitative heat cell background color and font styling."""
    if is_king:
        return (
            "background: linear-gradient(135deg, #ffd700 0%, #ffab00 100%); "
            "color: #000000; font-weight: 800; border: 1.5px solid #ffffff; "
            "box-shadow: 0 0 12px rgba(255, 215, 0, 0.85); border-radius: 4px;"
        )
    
    if pd.isna(val) or abs(val) < 1e-6 or max_abs_val <= 0:
        return "background-color: #121720; color: #484f58;"
    
    # Non-linear opacity scaling for rich visual contrast
    ratio = min(1.0, abs(val) / max_abs_val)
    opacity = 0.18 + (0.72 * (ratio ** 0.55))
    
    if val > 0:
        # Emerald Cyan for Positive GEX
        return f"background-color: rgba(16, 165, 140, {opacity:.2f}); color: #ffffff;"
    else:
        # Indigo/Purple for Negative GEX
        return f"background-color: rgba(125, 45, 175, {opacity:.2f}); color: #ffffff;"

def render_institutional_heatmap_grid(
    matrix: pd.DataFrame,
    spot_price: float,
    king_nodes_per_exp: Optional[Dict[str, float]] = None,
    symbol: str = "TICKER",
    title: str = "Institutional GEX Matrix",
    is_currency: bool = True,
    strike_window_dollar: Optional[float] = None,
    strike_count_around_king: Optional[int] = None
):
    """
    Renders an interactive Institutional Heatmap Grid Table
    with per-column King Node highlights, centered viewport scrolling,
    and strike filtering (N strikes above/below King Node or dollar window).
    """
    if matrix.empty:
        st.info("No options matrix data available to render Heatmap Grid.")
        return

    # Sort strikes descending (highest strike at top, like standard option chains)
    matrix_sorted = matrix.copy()
    matrix_sorted.index = [float(x) for x in matrix_sorted.index]
    matrix_sorted = matrix_sorted.sort_index(ascending=False)
    
    exp_dates = list(matrix_sorted.columns)
    king_nodes = dict(king_nodes_per_exp) if king_nodes_per_exp else {}
    
    # Ensure EVERY expiration column has a King Node (max Net GEX magnitude)
    for d in exp_dates:
        if d not in king_nodes or king_nodes[d] is None or king_nodes[d] <= 0:
            col_s = matrix_sorted[d].abs() if d in matrix_sorted.columns else pd.Series()
            if not col_s.empty and col_s.max() > 0:
                king_nodes[d] = float(col_s.idxmax())

    # Identify primary King Node / Center Strike for viewport focusing
    primary_king = None
    if exp_dates and exp_dates[0] in king_nodes:
        primary_king = king_nodes[exp_dates[0]]
    if primary_king is None or primary_king <= 0:
        primary_king = min(list(matrix_sorted.index), key=lambda s: abs(s - spot_price)) if not matrix_sorted.empty else spot_price

    # Filter matrix rows if strike_count_around_king or strike_window_dollar is specified
    strikes_all = list(matrix_sorted.index)
    
    if strike_count_around_king is not None and strike_count_around_king > 0 and strikes_all:
        center_s = min(strikes_all, key=lambda s: abs(s - primary_king))
        c_idx = strikes_all.index(center_s)
        
        start_idx = max(0, c_idx - strike_count_around_king)
        end_idx = min(len(strikes_all), c_idx + strike_count_around_king + 1)
        matrix_sorted = matrix_sorted.loc[strikes_all[start_idx:end_idx]]
    elif strike_window_dollar is not None and strike_window_dollar > 0:
        lower_bound = spot_price - strike_window_dollar
        upper_bound = spot_price + strike_window_dollar
        filtered_df = matrix_sorted.loc[(matrix_sorted.index >= lower_bound) & (matrix_sorted.index <= upper_bound)]
        if not filtered_df.empty:
            matrix_sorted = filtered_df

    strikes = list(matrix_sorted.index)
    if not strikes:
        st.warning("No strikes in selected focus window.")
        return

    closest_spot_strike = min(strikes, key=lambda s: abs(s - spot_price))
    center_row_strike = min(strikes, key=lambda s: abs(s - primary_king))
    
    # Compute 95th percentile absolute value for robust heat scale max bound
    flat_vals = matrix_sorted.values.flatten()
    clean_vals = [abs(v) for v in flat_vals if not pd.isna(v)]
    max_abs_val = float(np.percentile(clean_vals, 95)) if clean_vals else 1.0
    if max_abs_val <= 0:
        max_abs_val = 1.0

    # Build Custom HTML Table
    html_lines = []
    html_lines.append("""
    <style>
        .inst-grid-wrapper {
            background-color: #0b0e14;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
            font-family: 'JetBrains Mono', 'Fira Code', 'Segoe UI', monospace;
        }
        .inst-grid-header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid #21262d;
            margin-bottom: 12px;
        }
        .inst-grid-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #f0f6fc;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .inst-grid-pill-group {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .inst-grid-pill {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 4px 12px;
            font-size: 0.8rem;
            color: #8b949e;
            font-weight: 600;
        }
        .inst-grid-pill-spot {
            background: rgba(0, 229, 255, 0.15);
            border: 1px solid #00e5ff;
            color: #00e5ff;
        }
        .inst-grid-table-container {
            max-height: 580px;
            overflow: auto;
            border-radius: 8px;
            border: 1px solid #21262d;
            position: relative;
        }
        .inst-grid-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 2px;
            background-color: #0b0e14;
        }
        .inst-grid-table th {
            position: sticky;
            top: 0;
            background-color: #161b22;
            color: #8b949e;
            padding: 10px 14px;
            text-align: right;
            font-size: 0.82rem;
            font-weight: 700;
            border-bottom: 2px solid #30363d;
            z-index: 10;
            white-space: nowrap;
        }
        .inst-grid-table th.col-strike {
            position: sticky;
            left: 0;
            text-align: left;
            z-index: 20;
            background-color: #161b22;
            min-width: 100px;
            border-right: 1px solid #30363d;
        }
        .inst-grid-table td.col-strike-cell {
            position: sticky;
            left: 0;
            background-color: #0e1117;
            color: #c9d1d9;
            font-weight: 700;
            padding: 6px 12px;
            text-align: left;
            z-index: 5;
            font-size: 0.85rem;
            border-right: 1px solid #21262d;
            white-space: nowrap;
        }
        .spot-strike-badge {
            background-color: #ffffff;
            color: #000000 !important;
            font-weight: 900 !important;
            padding: 3px 8px;
            border-radius: 4px 12px 12px 4px;
            box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
            display: inline-block;
        }
        .inst-grid-table td.cell-val {
            padding: 7px 12px;
            text-align: right;
            font-weight: 600;
            font-size: 0.83rem;
            white-space: nowrap;
            border-radius: 3px;
        }
        .inst-grid-legend {
            display: flex;
            gap: 16px;
            justify-content: flex-end;
            padding-top: 10px;
            font-size: 0.78rem;
            color: #8b949e;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .color-box-king {
            width: 12px;
            height: 12px;
            background: #ffd700;
            border-radius: 2px;
        }
        .color-box-pos {
            width: 12px;
            height: 12px;
            background: #10a58c;
            border-radius: 2px;
        }
        .color-box-neg {
            width: 12px;
            height: 12px;
            background: #7d2daf;
            border-radius: 2px;
        }
    </style>
    """)

    html_lines.append('<div class="inst-grid-wrapper">')
    
    # Header Control Bar
    king_str = f"{primary_king:g}" if (primary_king % 1 == 0) else f"{primary_king:.1f}"
    html_lines.append(f"""
    <div class="inst-grid-header-bar">
        <div class="inst-grid-title">
            <span>🔥 {title}</span>
        </div>
        <div class="inst-grid-pill-group">
            <span class="inst-grid-pill skylit-pill-spot">🎯 {symbol}: ${spot_price:,.2f}</span>
            <span class="inst-grid-pill" style="border-color:#ffd700; color:#ffd700;">👑 King: {king_str}★</span>
        </div>
    </div>
    """)

    # Table Container
    html_lines.append('<div class="inst-grid-table-container" id="grid-container-box">')
    html_lines.append('<table class="inst-grid-table">')
    
    # Table Header Row
    html_lines.append('<thead><tr>')
    html_lines.append('<th class="col-strike">Strike</th>')
    for d in exp_dates:
        html_lines.append(f'<th>{d}</th>')
    html_lines.append('</tr></thead>')
    
    # Table Body Rows
    html_lines.append('<tbody>')
    for s in strikes:
        is_spot_strike = (s == closest_spot_strike)
        is_center_row = (s == center_row_strike)
        strike_str = f"{s:g}" if (s % 1 == 0) else f"{s:.1f}"
        
        row_attr = ' id="grid-center-row"' if is_center_row else ""
        html_lines.append(f'<tr{row_attr}>')
        
        # Strike Y-Axis Cell (With White Spot Badge if spot strike)
        if is_spot_strike:
            html_lines.append(f'<td class="col-strike-cell"><span class="spot-strike-badge">{strike_str}</span></td>')
        else:
            html_lines.append(f'<td class="col-strike-cell">{strike_str}</td>')
            
        # Expiration Data Cells
        for d in exp_dates:
            val = matrix_sorted.loc[s, d] if (s in matrix_sorted.index and d in matrix_sorted.columns) else 0.0
            is_king = (king_nodes.get(d) == s)
            
            formatted_text = _format_grid_val(val, is_currency=is_currency)
            if is_king and not formatted_text.endswith("★"):
                formatted_text += "★"
                
            style_css = _get_cell_bg_style(val, max_abs_val, is_king=is_king)
            html_lines.append(f'<td class="cell-val" style="{style_css}">{formatted_text}</td>')
            
        html_lines.append('</tr>')
        
    html_lines.append('</tbody></table></div>')

    # Footer Legend
    html_lines.append("""
    <div class="inst-grid-legend">
        <div class="legend-item"><span class="spot-strike-badge" style="padding:1px 5px; font-size:10px;">365.0</span> Spot Strike</div>
        <div class="legend-item"><div class="color-box-king"></div> 👑 King Node (Max GEX)</div>
        <div class="legend-item"><div class="color-box-pos"></div> Positive GEX</div>
        <div class="legend-item"><div class="color-box-neg"></div> Negative GEX</div>
    </div>
    """)

    # Auto-Scroll script to position King Node center row in vertical center of table viewport
    html_lines.append("""
    <script>
        (function() {
            setTimeout(function() {
                var row = document.getElementById("grid-center-row");
                if (row && row.scrollIntoView) {
                    row.scrollIntoView({ behavior: "instant", block: "center" });
                }
            }, 120);
        })();
    </script>
    """)

    html_lines.append('</div>')

    # Render in Streamlit safely
    full_html = "".join(html_lines)
    if hasattr(st, "html"):
        st.html(full_html)
    else:
        st.markdown(full_html, unsafe_allow_html=True)
