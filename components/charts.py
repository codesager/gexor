import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from config import COLORS

def create_gex_bar_chart(
    df: pd.DataFrame,
    spot_price: float,
    levels: Dict[str, Any],
    expected_move: Dict[str, Any],
    symbol: str = "TICKER",
    expiration: str = ""
) -> go.Figure:
    """
    Creates interactive Net GEX Bar Chart with Call Wall, Put Wall, Gamma Flip, Spot Price,
    King Node, and Expected Move shaded overlay.
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No options data available", template="plotly_dark")
        return fig

    df_sorted = df.sort_values("strike").copy()

    # Bar Colors: Emerald Green for Positive Net GEX, Crimson Red for Negative Net GEX
    colors = [
        COLORS["net_positive"] if val >= 0 else COLORS["net_negative"]
        for val in df_sorted["net_gex_m"]
    ]

    fig = go.Figure()

    # Net GEX Bars
    fig.add_trace(
        go.Bar(
            x=df_sorted["strike"],
            y=df_sorted["net_gex_m"],
            marker_color=colors,
            name="Net GEX ($M)",
            hovertemplate=(
                "<b>Strike %{x}</b><br>" +
                "Net GEX: $%{y:.2f}M<br>" +
                "<extra></extra>"
            )
        )
    )

    # Shaded Expected Move Band (ATM Straddle)
    lower_b = expected_move.get("lower_bound", spot_price)
    upper_b = expected_move.get("upper_bound", spot_price)
    y_min = float(df_sorted["net_gex_m"].min()) * 1.15 if not df_sorted.empty else -10
    y_max = float(df_sorted["net_gex_m"].max()) * 1.15 if not df_sorted.empty else 10

    fig.add_vrect(
        x0=lower_b,
        x1=upper_b,
        fillcolor=COLORS["expected_move"],
        opacity=0.3,
        layer="below",
        line_width=1,
        line_dash="dot",
        line_color=COLORS["spot_line"],
        annotation_text=f"Expected Move (±{expected_move.get('implied_move_pct', 0):.1f}%)",
        annotation_position="top left",
        annotation_font=dict(size=10, color=COLORS["spot_line"])
    )

    # Vertical Line: Spot Price
    fig.add_vline(
        x=spot_price,
        line_width=2.5,
        line_color=COLORS["spot_line"],
        annotation_text=f"Spot: ${spot_price:,.2f}",
        annotation_position="top right",
        annotation_font=dict(color=COLORS["spot_line"], size=11, family="monospace")
    )

    # Vertical Line: Call Wall
    call_wall = levels.get("call_wall", 0)
    if call_wall > 0:
        fig.add_vline(
            x=call_wall,
            line_width=2,
            line_dash="dash",
            line_color=COLORS["call_wall"],
            annotation_text=f"Call Wall: {call_wall:g}",
            annotation_position="top right",
            annotation_font=dict(color=COLORS["call_wall"], size=10)
        )

    # Vertical Line: Put Wall
    put_wall = levels.get("put_wall", 0)
    if put_wall > 0:
        fig.add_vline(
            x=put_wall,
            line_width=2,
            line_dash="dash",
            line_color=COLORS["put_wall"],
            annotation_text=f"Put Wall: {put_wall:g}",
            annotation_position="bottom left",
            annotation_font=dict(color=COLORS["put_wall"], size=10)
        )

    # Vertical Line: Gamma Flip Level
    gamma_flip = levels.get("gamma_flip", 0)
    if gamma_flip > 0:
        fig.add_vline(
            x=gamma_flip,
            line_width=2,
            line_dash="dot",
            line_color=COLORS["gamma_flip"],
            annotation_text=f"Gamma Flip: {gamma_flip:.1f}",
            annotation_position="bottom right",
            annotation_font=dict(color=COLORS["gamma_flip"], size=10)
        )

    # King Node Star Annotation
    king_node = levels.get("king_node", 0)
    king_val = levels.get("king_net_gex_m", 0)
    if king_node > 0 and not df_sorted.empty:
        fig.add_annotation(
            x=king_node,
            y=king_val,
            text=f"👑 KING {king_node:g}★",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowcolor=COLORS["king_node"],
            font=dict(color="#000000", size=11, family="sans-serif"),
            bgcolor=COLORS["king_node"],
            bordercolor="#FFFFFF",
            borderwidth=1,
            borderpad=4,
            opacity=0.95
        )

    exp_title = f" ({expiration})" if expiration else ""
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}{exp_title} — Net Gamma Exposure (GEX) by Strike</b>",
            font=dict(size=16, color=COLORS["text_primary"])
        ),
        xaxis_title=dict(text="Strike Price ($)", font=dict(color=COLORS["text_secondary"])),
        yaxis_title=dict(text="Net GEX ($ Millions)", font=dict(color=COLORS["text_secondary"])),
        template="plotly_dark",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["card_bg"],
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )

    fig.update_xaxes(showgrid=True, gridcolor="#21262d", zeroline=True, zerolinecolor="#30363d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d", zeroline=True, zerolinecolor="#30363d")

    return fig

def create_gex_heatmap(
    heatmap_matrix: pd.DataFrame,
    king_nodes_per_exp: Dict[str, float],
    title: str = "Net GEX Heatmap Across Strikes × Expirations"
) -> go.Figure:
    """
    Creates Heatmap of Net GEX across Strikes (Y) and Expirations (X)
    with Yellow Gold `#FFD700` Star `★` highlights for King Nodes.
    """
    if heatmap_matrix.empty:
        fig = go.Figure()
        fig.update_layout(title="No matrix data available", template="plotly_dark")
        return fig

    z_vals = heatmap_matrix.values
    exp_dates = list(heatmap_matrix.columns)
    strikes = list(heatmap_matrix.index)

    # Custom Diverging Color scale (Red -> Dark -> Emerald Green)
    custom_colorscale = [
        [0.0, "#d50000"],    # Deep Red
        [0.45, "#421010"],   # Dark Red
        [0.5, "#161b22"],    # Dark BG Neutral
        [0.55, "#0a3d1d"],   # Dark Green
        [1.0, "#00c853"],    # Emerald Green
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_vals,
            x=exp_dates,
            y=strikes,
            colorscale=custom_colorscale,
            zmid=0,
            colorbar=dict(title="Net GEX ($M)", tickfont=dict(color=COLORS["text_secondary"])),
            hovertemplate=(
                "Expiration: %{x}<br>" +
                "Strike: %{y}<br>" +
                "Net GEX: $%{z:.2f}M<br>" +
                "<extra></extra>"
            )
        )
    )

    # Add King Node Yellow `#FFD700` Star Highlights
    for exp_col, k_strike in king_nodes_per_exp.items():
        if exp_col in exp_dates and k_strike in strikes:
            k_val = heatmap_matrix.loc[k_strike, exp_col]
            fig.add_annotation(
                x=exp_col,
                y=k_strike,
                text=f"👑 {k_strike:g}★",
                showarrow=False,
                font=dict(color="#000000", size=10, family="sans-serif"),
                bgcolor=COLORS["king_node"],
                bordercolor="#FFFFFF",
                borderwidth=1,
                borderpad=3,
                opacity=0.95
            )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=15, color=COLORS["text_primary"])),
        xaxis_title="Expiration Date",
        yaxis_title="Strike Price ($)",
        template="plotly_dark",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["card_bg"],
        margin=dict(l=40, r=40, t=50, b=40),
        height=550
    )

    fig.update_xaxes(type="category", showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(autorange="reversed", showgrid=True, gridcolor="#21262d")

    return fig

def create_generic_heatmap(
    matrix: pd.DataFrame,
    title: str,
    z_label: str = "Value",
    colorscale: str = "Viridis"
) -> go.Figure:
    """
    Generic Heatmap generator for Open Interest or Volume / OI Ratio matrices.
    """
    if matrix.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for {title}", template="plotly_dark")
        return fig

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=list(matrix.columns),
            y=list(matrix.index),
            colorscale=colorscale,
            colorbar=dict(title=z_label, tickfont=dict(color=COLORS["text_secondary"])),
            hovertemplate=(
                "Expiration: %{x}<br>" +
                "Strike: %{y}<br>" +
                f"{z_label}: %{{z:.2f}}<br>" +
                "<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=15, color=COLORS["text_primary"])),
        xaxis_title="Expiration Date",
        yaxis_title="Strike Price ($)",
        template="plotly_dark",
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["card_bg"],
        margin=dict(l=40, r=40, t=50, b=40),
        height=520
    )

    fig.update_xaxes(type="category", showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(autorange="reversed", showgrid=True, gridcolor="#21262d")

    return fig
