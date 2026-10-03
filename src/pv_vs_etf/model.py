"""Configuration dataclasses and TOML loading for pv-vs-etf."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class PvConfig:
    """Parameters of the PV investment (rooftop or balcony)."""

    mode: str = "rooftop"  # "rooftop" or "balcony"
    kwp: float = 10.0  # peak power in kWp
    cost_per_kwp: float = 1300.0  # EUR per kWp installed (net of VAT in §16 mode)
    # Battery storage
    storage_kwh: float = 10.0  # 0 disables storage
    storage_cost_per_kwh: float = 500.0
    storage_capacity_loss: float = 0.02  # fraction per year
    storage_efficiency: float = 0.90  # round-trip
    # Subsidies (e.g. KfW grant) subtracted from investment
    subsidy: float = 0.0
    # Yields
    yield_per_kwp: float = 950.0  # kWh per kWp per year
    degradation: float = 0.005  # panel yield loss per year
    self_consumption_share: float = 0.30  # fraction of production self-consumed
    # Prices
    electricity_price: float = 0.35  # EUR/kWh at start
    electricity_price_growth: float = 0.025  # real growth p.a.
    feed_in_tariff: float = 0.078  # EUR/kWh (Teileinspeisung, <=10 kWp, 2025)
    feed_in_tariff_growth: float = 0.0  # fixed by law during 20 years
    # Costs
    insurance_per_year: float = 120.0
    meter_rent_per_year: float = 40.0
    maintenance_per_year_per_kwp: float = 8.0
    inverter_replacement_cost: float = 2500.0
    inverter_replacement_year: int = 12
    inverter_replacement_escalation: float = 0.02  # cost growth p.a.
    # Horizon
    lifetime_years: int = 25
    # Remaining value at end of horizon (residual inverter/battery value), EUR
    residual_value: float = 0.0


@dataclass
class TaxConfig:
    """German tax parameters."""

    preset: str = "s16_2025"  # "s16_2025" or "legacy_2023"
    # §16 EStG (2025+): <=30 kWp income-tax-free and VAT-exempt -> no taxes due.
    # Legacy 2023/24: feed-in tax-free; 70% of self-consumption value taxed.
    income_tax_rate: float = 0.30  # marginal rate for legacy preset
    # ETF taxation
    capital_gains_tax_rate: float = 0.26375  # Abgeltungsteuer + Soli
    teilfreistellung: float = 0.30  # equity funds
    sparerpauschbetrag: float = 1000.0  # single; 2000 for couples
    basiszins: float = 0.0255  # Vorabpauschale base rate (2025)
    vorabpauschale_taxed_share: float = 0.70  # 70% of Vorabpauschale taxable


@dataclass
class EtfConfig:
    """Parameters of the alternative ETF investment."""

    expected_return: float = 0.07  # nominal p.a.
    dividend_yield: float = 0.02  # of which distributions (basis for Vorabpauschale)
    ter: float = 0.0  # already included in expected_return if set >0 subtracted
    years: int = 25


@dataclass
class AppConfig:
    """Top-level application configuration."""

    pv: PvConfig = field(default_factory=PvConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
    etf: EtfConfig = field(default_factory=EtfConfig)
    output_dir: str = "output"
    report_title: str = "PV-Anlage vs. ETF"


def _apply_toml(dataclass_obj: object, section: dict) -> list[str]:
    """Set attributes of a dataclass from a TOML section. Returns unknown keys."""
    valid = {f.name for f in fields(dataclass_obj)}
    unknown = []
    for key, value in section.items():
        if key in valid:
            setattr(dataclass_obj, key, value)
        else:
            unknown.append(key)
    return unknown


def load_config(path: Path | None = None, overrides: dict | None = None) -> AppConfig:
    """Load configuration from TOML file and apply CLI overrides.

    Overrides use dotted paths like {"pv.kwp": 12.0}.
    """
    config = AppConfig()
    if path is not None and Path(path).exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        for section_name in ("pv", "tax", "etf"):
            section = data.get(section_name)
            if section:
                unknown = _apply_toml(getattr(config, section_name), section)
                if unknown:
                    msg = f"Unknown keys in [{section_name}]: {', '.join(unknown)}"
                    print(f"Warning: {msg}")
        for key in ("output_dir", "report_title"):
            if key in data:
                setattr(config, key, data[key])

    if overrides:
        for dotted, value in overrides.items():
            section_name, _, key = dotted.partition(".")
            target = getattr(config, section_name, None)
            if target is None or not hasattr(target, key):
                msg = f"Unknown override: {dotted}"
                raise ValueError(msg)
            setattr(target, key, value)

    if config.pv.mode not in ("rooftop", "balcony"):
        msg = f"Invalid pv.mode: {config.pv.mode!r} (must be 'rooftop' or 'balcony')"
        raise ValueError(msg)
    if config.pv.lifetime_years < 1:
        msg = "pv.lifetime_years must be >= 1"
        raise ValueError(msg)
    return config


def balcony_defaults(config: AppConfig) -> AppConfig:
    """Return config adjusted for a typical balcony solar plant (Steckersolar)."""
    config.pv.mode = "balcony"
    config.pv.kwp = 0.8
    config.pv.cost_per_kwp = 1200.0  # ~960 EUR for 800 W incl. mounting
    config.pv.storage_kwh = 0.0
    config.pv.yield_per_kwp = 1000.0
    config.pv.self_consumption_share = 0.95  # nearly all production used
    config.pv.electricity_price = 0.35
    config.pv.insurance_per_year = 0.0
    config.pv.meter_rent_per_year = 0.0
    config.pv.maintenance_per_year_per_kwp = 0.0
    config.pv.inverter_replacement_cost = 150.0
    config.pv.inverter_replacement_year = 10
    config.pv.residual_value = 0.0
    return config
