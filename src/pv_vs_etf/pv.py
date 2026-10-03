"""PV system cash-flow model: rooftop (with feed-in) and balcony (self-consumption only)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .model import AppConfig


@dataclass
class PvResult:
    """Year-by-year PV results and derived cash flows."""

    years: list[int]
    production_kwh: list[float]
    self_consumed_kwh: list[float]
    fed_in_kwh: list[float]
    savings_eur: list[float]  # avoided electricity purchases
    feed_in_eur: list[float]
    costs_eur: list[float]  # operating + replacements (positive = outflow)
    taxes_eur: list[float]  # income tax on self-consumption (legacy preset)
    cashflow_eur: list[float]  # net: investment in year 0, then savings+feedin-costs-taxes
    investment: float
    annual_cashflow_avg: float


def investment_total(config: AppConfig) -> float:
    """Total gross investment in year 0 (net of subsidy)."""
    p = config.pv
    inv = p.kwp * p.cost_per_kwp
    if p.storage_kwh > 0:
        inv += p.storage_kwh * p.storage_cost_per_kwh
    return max(inv - p.subsidy, 0.0)


def pv_cashflows(config: AppConfig) -> PvResult:
    """Build the year-by-year PV cash-flow table (year 0 = investment)."""
    p = config.pv
    tax = config.tax

    inv = investment_total(config)
    n_years = p.lifetime_years

    rows = {
        "year": [],
        "production": [],
        "self_consumed": [],
        "fed_in": [],
        "savings": [],
        "feed_in": [],
        "costs": [],
        "taxes": [],
        "cashflow": [],
    }

    for t in range(n_years + 1):
        rows["year"].append(t)
        if t == 0:
            for key in (
                "production",
                "self_consumed",
                "fed_in",
                "savings",
                "feed_in",
                "costs",
                "taxes",
            ):
                rows[key].append(0.0)
            rows["cashflow"].append(-inv)
            continue

        year_index = t  # operational year 1..N
        # Production with degradation (first year full)
        production = p.yield_per_kwp * p.kwp * (1.0 - p.degradation) ** (year_index - 1)
        # Battery increases self-consumption share over the years (simple model):
        # storage lifts self-consumption from base share toward 1 - fed-in-limited max.
        # We keep it simple: effective share = base + storage bonus, capped.
        storage_bonus = (
            min(p.storage_kwh / max(production, 1e-9), 1.0) * 0.35 if p.storage_kwh > 0 else 0.0
        )
        eff_share = min(p.self_consumption_share + storage_bonus, 0.95)

        self_consumed = production * eff_share
        fed_in = production - self_consumed if p.mode == "rooftop" else 0.0

        elec_price = p.electricity_price * (1.0 + p.electricity_price_growth) ** (year_index - 1)
        tariff = p.feed_in_tariff * (1.0 + p.feed_in_tariff_growth) ** (year_index - 1)

        savings = self_consumed * elec_price
        feed_in_rev = fed_in * tariff

        costs = (
            p.insurance_per_year + p.meter_rent_per_year + p.maintenance_per_year_per_kwp * p.kwp
        )
        # costs escalate with general inflation assumption (use electricity growth as proxy)
        costs *= (1.0 + 0.02) ** (year_index - 1)
        if t == p.inverter_replacement_year and p.inverter_replacement_cost > 0:
            costs += (
                p.inverter_replacement_cost
                * (1.0 + p.inverter_replacement_escalation) ** year_index
            )

        taxes = 0.0
        if tax.preset == "legacy_2023" and p.mode == "rooftop":
            # 70% of self-consumed electricity value treated as taxable income
            taxes = 0.7 * savings * tax.income_tax_rate
        # §16 EStG 2025: tax-free for <=30 kWp (and VAT-exempt; prices above are net).

        cashflow = savings + feed_in_rev - costs - taxes
        if t == n_years and p.residual_value > 0:
            cashflow += p.residual_value

        rows["production"].append(production)
        rows["self_consumed"].append(self_consumed)
        rows["fed_in"].append(fed_in)
        rows["savings"].append(savings)
        rows["feed_in"].append(feed_in_rev)
        rows["costs"].append(costs)
        rows["taxes"].append(taxes)
        rows["cashflow"].append(cashflow)

    df = pd.DataFrame(rows)
    op_years = n_years
    annual_avg = float(df["cashflow"][1:].mean()) if op_years > 0 else 0.0

    return PvResult(
        years=rows["year"],
        production_kwh=rows["production"],
        self_consumed_kwh=rows["self_consumed"],
        fed_in_kwh=rows["fed_in"],
        savings_eur=rows["savings"],
        feed_in_eur=rows["feed_in"],
        costs_eur=rows["costs"],
        taxes_eur=rows["taxes"],
        cashflow_eur=rows["cashflow"],
        investment=inv,
        annual_cashflow_avg=annual_avg,
    )
