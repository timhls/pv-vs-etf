"""Command-line interface: pv-vs-etf [--mode rooftop|balcony] [--config FILE] [overrides]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .charts import build_report, fig_annual_pv, fig_cumulative, fig_final_wealth, fig_sensitivity
from .etf import etf_net_return, etf_projection
from .irr import irr, npv, simple_payback
from .model import balcony_defaults, load_config
from .pv import pv_cashflows


def _parse_overrides(args: argparse.Namespace) -> dict:
    overrides: dict[str, object] = {}
    if args.kwp is not None:
        overrides["pv.kwp"] = args.kwp
    if args.storage is not None:
        overrides["pv.storage_kwh"] = args.storage
    if args.price is not None:
        overrides["pv.electricity_price"] = args.price
    if args.price_growth is not None:
        overrides["pv.electricity_price_growth"] = args.price_growth
    if args.self_consumption is not None:
        overrides["pv.self_consumption_share"] = args.self_consumption
    if args.years is not None:
        overrides["pv.lifetime_years"] = args.years
        overrides["etf.years"] = args.years
    if args.etf_return is not None:
        overrides["etf.expected_return"] = args.etf_return
    if args.tax_preset is not None:
        overrides["tax.preset"] = args.tax_preset
    return overrides


def _fmt_pct(v: float | None, digits: int = 1) -> str:
    return f"{v * 100:.{digits}f} %" if v is not None else "n/a"


def _fmt_years(v: float | None) -> str:
    return f"{v:.1f} Jahre" if v is not None else "> Laufzeit"


def compute(config) -> dict:
    """Run the full comparison. Returns result bundle for CLI display and report."""
    pv_res = pv_cashflows(config)
    pv_irr = irr(pv_res.cashflow_eur)

    # ETF alternative: same lump sum invested at t=0
    etf_lump = etf_projection(config, initial=pv_res.investment)

    # PV savings reinvested into ETF: yearly contributions = PV net cashflows
    yearly = [cf for cf in pv_res.cashflow_eur[1:]]
    etf_reinvest = etf_projection(config, initial=pv_res.investment, yearly=yearly)

    etf_net = etf_net_return(config)

    cum = []
    running = 0.0
    for cf in pv_res.cashflow_eur:
        running += cf
        cum.append(running)

    return {
        "config": config,
        "pv": pv_res,
        "pv_irr": pv_irr,
        "pv_payback": simple_payback(pv_res.cashflow_eur),
        "pv_npv_at_etf": npv(etf_net, pv_res.cashflow_eur),
        "pv_cumulative": cum,
        "etf_lump": etf_lump,
        "etf_reinvest": etf_reinvest,
        "etf_net_return": etf_net,
    }


def _sensitivity(
    config, growth_values: list[float], sc_values: list[float]
) -> list[list[float | None]]:
    """IRR grid over electricity price growth x self-consumption share."""
    from copy import deepcopy

    grid: list[list[float | None]] = []
    for sc in sc_values:
        row: list[float | None] = []
        for g in growth_values:
            cfg = deepcopy(config)
            cfg.pv.electricity_price_growth = g
            cfg.pv.self_consumption_share = sc
            res = pv_cashflows(cfg)
            row.append(irr(res.cashflow_eur))
        grid.append(row)
    return grid


def _metrics_html(res: dict) -> str:
    pv = res["pv"]
    cards = [
        ("Investition", f"{pv.investment:,.0f} EUR"),
        ("PV IRR (intern)", _fmt_pct(res["pv_irr"])),
        ("PV Amortisation", _fmt_years(res["pv_payback"])),
        ("ETF Netto-Rendite", _fmt_pct(res["etf_net_return"])),
        ("Endvermögen PV+Sparplan", f"{res['etf_reinvest'].value_net[-1]:,.0f} EUR"),
        ("Endvermögen ETF", f"{res['etf_lump'].value_net[-1]:,.0f} EUR"),
    ]
    cards_html = "".join(f"<div class='card'><h3>{k}</h3><p>{v}</p></div>" for k, v in cards)
    return f"<div class='metrics'>{cards_html}</div>"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pv-vs-etf",
        description="PV-Anlage vs. ETF: Investitionsvergleichsrechner (IRR-Methode)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, default=None, help="Pfad zur config.toml")
    parser.add_argument(
        "--mode",
        choices=["rooftop", "balcony"],
        default=None,
        help="Szenario: rooftop (Default) oder balcony (setzt Balkonkraftwerk-Defaults)",
    )
    parser.add_argument("--kwp", type=float, help="Peakleistung in kWp")
    parser.add_argument("--storage", type=float, help="Speichergröße in kWh (0 = ohne)")
    parser.add_argument("--price", type=float, help="Strompreis EUR/kWh")
    parser.add_argument("--price-growth", type=float, help="Strompreisanstieg p.a. (0.02 = 2%%)")
    parser.add_argument(
        "--self-consumption", type=float, help="Eigenverbrauchsanteil (0.30 = 30%%)"
    )
    parser.add_argument("--years", type=int, help="Betrachtungshorizont in Jahren")
    parser.add_argument("--etf-return", type=float, help="ETF-Erwartungsrendite p.a. (0.07 = 7%%)")
    parser.add_argument("--tax-preset", choices=["s16_2025", "legacy_2023"], help="Steuervariante")
    parser.add_argument("--report", action="store_true", help="HTML-Report mit Charts erzeugen")
    parser.add_argument(
        "--sensitivity", action="store_true", help="IRR-Sensitivitäts-Heatmap erzeugen"
    )
    args = parser.parse_args(argv)

    overrides = _parse_overrides(args)
    try:
        config = load_config(args.config, overrides)
        if args.mode == "balcony":
            config = balcony_defaults(config)
    except (ValueError, OSError) as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 2

    res = compute(config)

    print(f"\n=== PV vs. ETF: {config.pv.mode} ===")
    print(f"Investition (t=0):        {res['pv'].investment:>12,.0f} EUR")
    print(f"Ø jährlicher Cashflow:    {res['pv'].annual_cashflow_avg:>12,.0f} EUR")
    print(f"PV IRR:                   {_fmt_pct(res['pv_irr']):>15}")
    print(f"PV Amortisation:          {_fmt_years(res['pv_payback']):>15}")
    print(f"ETF Netto-Rendite:        {_fmt_pct(res['etf_net_return']):>15}")
    print(f"NPV PV @ ETF-Rendite:     {res['pv_npv_at_etf']:>12,.0f} EUR")
    print(f"Endvermögen PV+Sparplan:  {res['etf_reinvest'].value_net[-1]:>12,.0f} EUR")
    print(f"Endvermögen ETF:          {res['etf_lump'].value_net[-1]:>12,.0f} EUR")
    if res["pv_irr"] is not None:
        winner = "PV" if res["pv_irr"] > res["etf_net_return"] else "ETF"
        print(f"\n==> Bei diesen Annahmen schlägt: {winner}\n")

    if args.report or args.sensitivity:
        from plotly.graph_objects import Figure

        figures: list[Figure] = [
            fig_cumulative(res["pv"], res["etf_lump"], res["etf_reinvest"]),
            fig_annual_pv(res["pv"]),
        ]
        if args.sensitivity:
            growth_values = [0.00, 0.01, 0.02, 0.03, 0.04]
            sc_values = [0.15, 0.25, 0.35, 0.45, 0.60]
            grid = _sensitivity(config, growth_values, sc_values)
            figures.append(
                fig_sensitivity(config, pv_cashflows, growth_values, sc_values, grid, "IRR p.a.")
            )
        figures.append(fig_final_wealth(res["pv"], res["etf_lump"], res["etf_reinvest"]))

        out_dir = Path(config.output_dir)
        out_path = out_dir / "report.html"
        build_report(
            config,
            res["pv"],
            res["etf_lump"],
            res["etf_reinvest"],
            figures,
            _metrics_html(res),
            out_path,
        )
        print(f"Report geschrieben: {out_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
