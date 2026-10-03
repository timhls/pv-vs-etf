"""ETF investment projection with German capital gains tax, Teilfreistellung,
Vorabpauschale and Sparerpauschbetrag."""

from __future__ import annotations

from dataclasses import dataclass

from .model import AppConfig


@dataclass
class EtfResult:
    years: list[int]
    value_gross: list[float]  # before taxes
    value_net: list[float]  # after yearly Vorabpauschale taxes and final sale tax
    taxes_paid: list[float]  # taxes per year (final year includes sale tax)


def _sale_tax(gain: float, cfg: AppConfig, allowance_used: float) -> float:
    """Tax on realized gains: 30% Teilfreistellung, remaining taxed, allowance."""
    taxable = gain * (1.0 - cfg.tax.teilfreistellung)
    allowance_remaining = max(cfg.tax.sparerpauschbetrag - allowance_used, 0.0)
    taxable = max(taxable - allowance_remaining, 0.0)
    return taxable * cfg.tax.capital_gains_tax_rate


def etf_projection(
    config: AppConfig, initial: float, yearly: list[float] | None = None
) -> EtfResult:
    """Project an ETF investment.

    initial: lump sum at t=0. yearly: additional contributions at start of years 1..N.
    yearly[i] is added at the beginning of year i+1 (after Vorabpauschale of prior year).
    """
    etf = config.etf
    tax = config.tax
    n = etf.years

    r = etf.expected_return - etf.ter

    value = initial
    years, gross, net, taxes = [0], [initial], [initial], [0.0]
    total_taxes = 0.0
    invested = initial
    allowance_used_per_year: list[float] = []

    for year in range(1, n + 1):
        # contribution at start of year
        contribution = yearly[year - 1] if yearly and year - 1 < len(yearly) else 0.0
        value += contribution
        invested += contribution

        # growth
        value *= 1.0 + r

        # Vorabpauschale: base = Basiszins * start value (value before growth)
        start_value = value / (1.0 + r)
        vorab = start_value * tax.basiszins
        # actual distributions count as lower bound substitute -> use vorab vs div:
        vorab = max(vorab, 0.0)
        taxable_vorab = vorab * tax.vorabpauschale_taxed_share
        taxable_vorab *= 1.0 - tax.teilfreistellung  # Teilfreistellung applies
        allowance = (
            max(tax.sparerpauschbetrag - sum(allowance_used_per_year), 0.0) if year == 1 else 0.0
        )
        # Sparerpauschbetrag typically applied annually; approximate: full amount in year 1
        taxable_after_allowance = max(taxable_vorab - allowance, 0.0)
        tax_due = taxable_after_allowance * tax.capital_gains_tax_rate
        allowance_used_per_year.append(taxable_after_allowance)
        value -= tax_due
        total_taxes += tax_due

        years.append(year)
        gross.append(value + total_taxes)  # hypothetical gross value
        net.append(value)
        taxes.append(tax_due)

    # final sale tax on gains (held >= 1yr -> Teilfreistellung 30%)
    gain = value - invested
    if gain > 0:
        sale_tax = _sale_tax(gain, config, allowance_used=sum(allowance_used_per_year))
        value -= sale_tax
        total_taxes += sale_tax
        net[-1] = value
        taxes[-1] += sale_tax

    return EtfResult(years=years, value_gross=gross, value_net=net, taxes_paid=taxes)


def etf_net_return(config: AppConfig, initial: float = 10_000.0) -> float:
    """Effective net return p.a. of the ETF after all taxes (CAGR of net value)."""
    result = etf_projection(config, initial)
    n = config.etf.years
    net_final = result.value_net[-1]
    if initial <= 0 or net_final <= 0:
        return 0.0
    return (net_final / initial) ** (1.0 / n) - 1.0
