"""Plotly charts and HTML report generation."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from .etf import EtfResult
from .irr import break_even_year
from .model import AppConfig
from .pv import PvResult


def _style(fig: go.Figure, title: str, ytitle: str, xtitle: str = "Jahr") -> go.Figure:
    fig.update_layout(
        title=title,
        xaxis_title=xtitle,
        yaxis_title=ytitle,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        margin={"l": 60, "r": 30, "t": 60, "b": 50},
    )
    return fig


def fig_cumulative(pv: PvResult, etf_lump: EtfResult, etf_reinvest: EtfResult | None) -> go.Figure:
    """Cumulative PV cash flow vs. ETF value development."""
    cum = []
    running = 0.0
    for cf in pv.cashflow_eur:
        running += cf
        cum.append(running)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=pv.years, y=cum, name="PV kumuliert", line={"color": "#e6a23c", "width": 3})
    )
    fig.add_trace(
        go.Scatter(
            x=etf_lump.years,
            y=etf_lump.value_net,
            name=f"ETF (Einmalanlage {pv.investment:,.0f} EUR)",
            line={"color": "#3a7ca5", "width": 3},
        )
    )
    if etf_reinvest is not None:
        fig.add_trace(
            go.Scatter(
                x=etf_reinvest.years,
                y=etf_reinvest.value_net,
                name="ETF + PV-Ersparnisse angelegt",
                line={"color": "#6a994e", "width": 2, "dash": "dot"},
            )
        )
    be = break_even_year(pv.cashflow_eur)
    if be is not None:
        fig.add_vline(
            x=be,
            line_dash="dash",
            line_color="gray",
            opacity=0.6,
            annotation_text=f"Break-even ≈ {be:.1f} Jahre",
            annotation_position="top left",
        )
    return _style(fig, "Kumulierter Cashflow: PV-Anlage vs. ETF", "EUR")


def fig_annual_pv(pv: PvResult) -> go.Figure:
    """Annual PV cash flow components as stacked/symmetric bars."""
    fig = go.Figure()
    op_years = pv.years[1:]
    fig.add_trace(
        go.Bar(x=op_years, y=[-c for c in pv.costs_eur[1:]], name="Kosten", marker_color="#c94f4f")
    )
    if any(t > 0 for t in pv.taxes_eur[1:]):
        fig.add_trace(
            go.Bar(
                x=op_years, y=[-t for t in pv.taxes_eur[1:]], name="Steuern", marker_color="#8c5c58"
            )
        )
    fig.add_trace(
        go.Bar(
            x=op_years,
            y=pv.savings_eur[1:],
            name="Ersparnis Eigenverbrauch",
            marker_color="#6a994e",
        )
    )
    if any(v > 0 for v in pv.feed_in_eur[1:]):
        fig.add_trace(
            go.Bar(
                x=op_years, y=pv.feed_in_eur[1:], name="Einspeisevergütung", marker_color="#3a7ca5"
            )
        )
    fig.add_trace(
        go.Scatter(
            x=op_years,
            y=pv.cashflow_eur[1:],
            name="Netto-Cashflow",
            mode="lines+markers",
            line={"color": "#333", "width": 2},
        )
    )
    fig.update_layout(barmode="relative", bargap=0.1)
    return _style(fig, "Jährliche PV-Cashflows", "EUR")


def fig_sensitivity(
    config: AppConfig,
    pv_result_factory,
    values_growth: list[float],
    values_sc: list[float],
    z_values: list[list[float]],
    z_title: str,
) -> go.Figure:
    """Sensitivity heatmap of PV IRR over electricity price growth x self-consumption."""
    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=[f"{v:.0%}" for v in values_growth],
            y=[f"{v:.0%}" for v in values_sc],
            colorscale="RdYlGn",
            zmid=0.0,
            colorbar={"title": z_title},
            text=[[f"{z:.1%}" if z is not None else "–" for z in row] for row in z_values],
            texttemplate="%{text}",
        )
    )
    fig.update_layout(
        title="Sensitivität: interner Zins (IRR) der PV-Anlage",
        xaxis_title="Strompreisanstieg p.a.",
        yaxis_title="Eigenverbrauchsanteil",
        template="plotly_white",
        margin={"l": 60, "r": 30, "t": 60, "b": 50},
    )
    return fig


def fig_final_wealth(
    pv: PvResult, etf_lump: EtfResult, etf_reinvest: EtfResult | None
) -> go.Figure:
    """Final wealth comparison as bar chart."""
    labels, values = [], []

    # PV path: investment stays in PV; net cashflows are reinvested in ETF
    labels.append(f"PV + Ersparnisse angelegt<br>({pv.years[-1]} Jahre)")
    if etf_reinvest is not None:
        values.append(etf_reinvest.value_net[-1])
    else:
        cum = sum(pv.cashflow_eur)
        values.append(cum)
    labels.append(f"ETF Einmalanlage<br>({etf_lump.years[-1]} Jahre)")
    values.append(etf_lump.value_net[-1])

    colors = ["#6a994e", "#3a7ca5"]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:,.0f} EUR" for v in values],
            textposition="outside",
        )
    )
    fig.update_yaxes(range=[0, max(values) * 1.15])
    return _style(fig, "Endvermögen nach Steuer", "EUR", xtitle="")


def build_report(
    config: AppConfig,
    pv: PvResult,
    etf_lump: EtfResult,
    etf_reinvest: EtfResult | None,
    figures: list[go.Figure],
    metrics_html: str,
    out_path: Path,
) -> Path:
    """Assemble all figures and a metrics summary into one standalone HTML file."""
    parts = [
        "<html><head><meta charset='utf-8'>",
        f"<title>{config.report_title}</title>",
        "<style>",
        "body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "max-width:960px;margin:24px auto;padding:0 16px;color:#222}",
        "h1{border-bottom:2px solid #e6a23c;padding-bottom:8px}",
        ".metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));"
        "gap:12px;margin:16px 0}",
        ".card{border:1px solid #ddd;border-radius:8px;padding:12px}",
        ".card h3{margin:0 0 4px;font-size:.85em;color:#666;text-transform:uppercase}",
        ".card p{margin:0;font-size:1.35em;font-weight:600}",
        ".note{font-size:.85em;color:#666;margin-top:24px}",
        "</style></head><body>",
        f"<h1>{config.report_title}</h1>",
        metrics_html,
    ]
    for fig in figures:
        parts.append(
            fig.to_html(
                full_html=False, include_plotlyjs="cdn" if figures.index(fig) == 0 else False
            )
        )
    parts.append(
        "<p class='note'>Vereinfachtes Modell ohne Gewähr. Steuern: "
        f"Preset '{config.tax.preset}'. Vorabpauschale, Teilfreistellung und "
        "Sparerpauschbetrag näherungsweise modelliert.</p>"
    )
    parts.append("</body></html>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path
