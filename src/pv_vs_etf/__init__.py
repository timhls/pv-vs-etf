"""pv-vs-etf: PV-Anlage vs. ETF investment comparison calculator."""

from .model import AppConfig, EtfConfig, PvConfig, TaxConfig, load_config

__all__ = [
    "AppConfig",
    "EtfConfig",
    "PvConfig",
    "TaxConfig",
    "load_config",
    "__version__",
]

__version__ = "0.1.0"
