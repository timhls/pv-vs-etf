import pytest

from pv_vs_etf.model import AppConfig, EtfConfig, PvConfig, TaxConfig
from pv_vs_etf.pv import investment_total, pv_cashflows


class TestInvestment:
    def test_rooftop_with_storage(self):
        cfg = AppConfig(
            pv=PvConfig(kwp=10, cost_per_kwp=1300, storage_kwh=10, storage_cost_per_kwh=500)
        )
        assert investment_total(cfg) == pytest.approx(10 * 1300 + 10 * 500)

    def test_without_storage(self):
        cfg = AppConfig(pv=PvConfig(kwp=10, cost_per_kwp=1300, storage_kwh=0))
        assert investment_total(cfg) == pytest.approx(13_000)

    def test_subsidy_deducted(self):
        cfg = AppConfig(pv=PvConfig(kwp=10, cost_per_kwp=1300, storage_kwh=0, subsidy=2000))
        assert investment_total(cfg) == pytest.approx(11_000)


class TestCashflows:
    def test_year0_is_investment(self):
        cfg = AppConfig(pv=PvConfig(lifetime_years=5))
        res = pv_cashflows(cfg)
        assert res.cashflow_eur[0] == pytest.approx(-res.investment)
        assert res.years == list(range(6))

    def test_first_year_values(self):
        cfg = AppConfig(
            pv=PvConfig(
                kwp=10,
                yield_per_kwp=950,
                self_consumption_share=0.3,
                electricity_price=0.35,
                feed_in_tariff=0.078,
                lifetime_years=3,
                storage_kwh=0,
                insurance_per_year=0,
                meter_rent_per_year=0,
                maintenance_per_year_per_kwp=0,
                inverter_replacement_cost=0,
            )
        )
        res = pv_cashflows(cfg)
        production = 9500.0
        assert res.production_kwh[1] == pytest.approx(production)
        assert res.self_consumed_kwh[1] == pytest.approx(production * 0.3)
        assert res.fed_in_kwh[1] == pytest.approx(production * 0.7)
        assert res.savings_eur[1] == pytest.approx(production * 0.3 * 0.35)
        assert res.feed_in_eur[1] == pytest.approx(production * 0.7 * 0.078)
        assert res.cashflow_eur[1] == pytest.approx(res.savings_eur[1] + res.feed_in_eur[1])

    def test_degradation_reduces_production(self):
        cfg = AppConfig(pv=PvConfig(lifetime_years=3, degradation=0.01))
        res = pv_cashflows(cfg)
        assert res.production_kwh[2] == pytest.approx(res.production_kwh[1] * 0.99)
        assert res.production_kwh[3] == pytest.approx(res.production_kwh[1] * 0.99**2)

    def test_price_growth_applied(self):
        cfg = AppConfig(
            pv=PvConfig(
                lifetime_years=3,
                electricity_price=0.30,
                electricity_price_growth=0.02,
                self_consumption_share=1.0,
                storage_kwh=0,
            )
        )
        res = pv_cashflows(cfg)
        # savings grow ~2% but degradation (default 0.5%) reduces production;
        # year2 price factor 1.02 vs year1, production factor (1-degradation)^1
        assert res.savings_eur[2] == pytest.approx(res.savings_eur[1] * 1.02 * (1 - 0.005))

    def test_inverter_replacement_in_costs(self):
        cfg = AppConfig(
            pv=PvConfig(
                lifetime_years=13,
                inverter_replacement_cost=2000,
                inverter_replacement_year=12,
                inverter_replacement_escalation=0.0,
            )
        )
        res = pv_cashflows(cfg)
        # year 12 costs = running costs escalated 2% from year 11 + flat 2000 replacement
        base_op_cost_11 = res.costs_eur[11]
        base_op_cost_12 = base_op_cost_11 * 1.02
        assert res.costs_eur[12] == pytest.approx(base_op_cost_12 + 2000.0)

    def test_balcony_no_feed_in(self):
        cfg = AppConfig(pv=PvConfig(mode="balcony", lifetime_years=5, self_consumption_share=0.95))
        res = pv_cashflows(cfg)
        assert all(v == 0 for v in res.fed_in_kwh)

    def test_storage_raises_self_consumption(self):
        base = AppConfig(pv=PvConfig(lifetime_years=2, storage_kwh=0))
        with_storage = AppConfig(pv=PvConfig(lifetime_years=2, storage_kwh=10))
        r1 = pv_cashflows(base)
        r2 = pv_cashflows(with_storage)
        assert r2.self_consumed_kwh[1] > r1.self_consumed_kwh[1]

    def test_s16_preset_charges_no_tax(self):
        cfg = AppConfig(pv=PvConfig(lifetime_years=3), tax=TaxConfig(preset="s16_2025"))
        res = pv_cashflows(cfg)
        assert all(t == 0 for t in res.taxes_eur)

    def test_residual_value_in_final_year(self):
        cfg = AppConfig(pv=PvConfig(lifetime_years=3, residual_value=1000))
        res = pv_cashflows(cfg)
        cfg2 = AppConfig(pv=PvConfig(lifetime_years=3, residual_value=0))
        res2 = pv_cashflows(cfg2)
        assert res.cashflow_eur[3] - res2.cashflow_eur[3] == pytest.approx(1000)

    def test_plausible_irr_default(self):
        from pv_vs_etf.irr import irr

        cfg = AppConfig(pv=PvConfig(lifetime_years=25), etf=EtfConfig(years=25))
        res = pv_cashflows(cfg)
        r = irr(res.cashflow_eur)
        assert r is not None
        assert 0.02 < r < 0.20
