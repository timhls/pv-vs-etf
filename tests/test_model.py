import pytest

from pv_vs_etf.model import AppConfig, PvConfig, TaxConfig, balcony_defaults, load_config


class TestDefaults:
    def test_default_config(self):
        cfg = load_config(None)
        assert cfg.pv.mode == "rooftop"
        assert cfg.pv.kwp == 10.0
        assert cfg.tax.preset == "s16_2025"

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            load_config(None, {"pv.mode": "wind"})

    def test_invalid_years_rejected(self):
        with pytest.raises(ValueError, match="lifetime_years"):
            load_config(None, {"pv.lifetime_years": 0})

    def test_unknown_override_rejected(self):
        with pytest.raises(ValueError, match="Unknown override"):
            load_config(None, {"pv.nonsense": 1})


class TestToml:
    def test_load_toml_file(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text(
            '[pv]\nkwp = 12.5\nmode = "rooftop"\n\n'
            '[tax]\npreset = "legacy_2023"\n\n'
            "[etf]\nexpected_return = 0.06\n",
            encoding="utf-8",
        )
        cfg = load_config(f)
        assert cfg.pv.kwp == 12.5
        assert cfg.tax.preset == "legacy_2023"
        assert cfg.etf.expected_return == 0.06
        # untouched defaults
        assert cfg.pv.electricity_price == 0.35

    def test_override_wins_over_toml(self, tmp_path):
        f = tmp_path / "config.toml"
        f.write_text("[pv]\nkwp = 12.5\n", encoding="utf-8")
        cfg = load_config(f, {"pv.kwp": 9.0})
        assert cfg.pv.kwp == 9.0


class TestBalconyDefaults:
    def test_balcony(self):
        cfg = balcony_defaults(AppConfig())
        assert cfg.pv.mode == "balcony"
        assert cfg.pv.kwp == pytest.approx(0.8)
        assert cfg.pv.storage_kwh == 0.0
        assert cfg.pv.self_consumption_share == pytest.approx(0.95)


class TestTaxPresets:
    def test_s16_no_pv_tax(self):
        from pv_vs_etf.pv import pv_cashflows

        cfg = AppConfig(pv=PvConfig(lifetime_years=5), tax=TaxConfig(preset="s16_2025"))
        res = pv_cashflows(cfg)
        assert all(t == 0 for t in res.taxes_eur)

    def test_legacy_taxes_self_consumption(self):
        from pv_vs_etf.pv import pv_cashflows

        cfg = AppConfig(pv=PvConfig(lifetime_years=5), tax=TaxConfig(preset="legacy_2023"))
        res = pv_cashflows(cfg)
        # tax = 0.7 * savings * 0.30 in each operational year
        for savings, tax in zip(res.savings_eur[1:], res.taxes_eur[1:], strict=True):
            assert tax == pytest.approx(0.7 * savings * 0.30)
