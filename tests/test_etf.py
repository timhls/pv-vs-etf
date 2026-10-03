import pytest

from pv_vs_etf.etf import etf_net_return, etf_projection
from pv_vs_etf.model import AppConfig, EtfConfig, TaxConfig


class TestEtfProjection:
    def test_no_tax_grows_at_return(self):
        # disable taxes: basiszins=0 -> vorab=0; sale tax: capital_gains_tax_rate=0
        cfg = AppConfig(
            etf=EtfConfig(expected_return=0.07, years=10),
            tax=TaxConfig(basiszins=0.0, capital_gains_tax_rate=0.0),
        )
        res = etf_projection(cfg, initial=10_000)
        assert res.value_net[-1] == pytest.approx(10_000 * 1.07**10, rel=1e-9)

    def test_taxes_reduce_value(self):
        cfg = AppConfig(etf=EtfConfig(years=10))
        res = etf_projection(cfg, initial=10_000)
        assert res.value_net[-1] < 10_000 * 1.07**10

    def test_yearly_contributions_increase_value(self):
        cfg = AppConfig(etf=EtfConfig(years=10))
        lump = etf_projection(cfg, initial=10_000)
        with_sp = etf_projection(cfg, initial=10_000, yearly=[500] * 10)
        assert with_sp.value_net[-1] > lump.value_net[-1]

    def test_negative_return_no_sale_tax(self):
        cfg = AppConfig(
            etf=EtfConfig(expected_return=-0.02, years=5),
            tax=TaxConfig(basiszins=0.0),
        )
        res = etf_projection(cfg, initial=10_000)
        # only losses, no sale tax; value should equal pure growth
        assert res.value_net[-1] == pytest.approx(10_000 * 0.98**5, rel=1e-9)


class TestSaleTax:
    def test_sale_tax_hand_computed(self):
        # Basiszins=0 -> no Vorabpauschale. 2 years 10% growth.
        cfg = AppConfig(
            etf=EtfConfig(expected_return=0.10, years=2),
            tax=TaxConfig(
                basiszins=0.0,
                capital_gains_tax_rate=0.25,
                teilfreistellung=0.30,
                sparerpauschbetrag=0.0,
            ),
        )
        res = etf_projection(cfg, initial=1000)
        value_gross = 1000 * 1.1**2  # 1210
        gain = value_gross - 1000  # 210
        expected_tax = gain * 0.7 * 0.25  # 36.75
        assert res.value_net[-1] == pytest.approx(value_gross - expected_tax, rel=1e-9)

    def test_sparerpauschbetrag_reduces_tax(self):
        common = dict(basiszins=0.0, capital_gains_tax_rate=0.25, teilfreistellung=0.0)
        cfg_small = AppConfig(
            etf=EtfConfig(expected_return=0.10, years=2),
            tax=TaxConfig(sparerpauschbetrag=0.0, **common),
        )
        cfg_exempt = AppConfig(
            etf=EtfConfig(expected_return=0.10, years=2),
            tax=TaxConfig(sparerpauschbetrag=100_000.0, **common),
        )
        small = etf_projection(cfg_small, initial=1000)
        exempt = etf_projection(cfg_exempt, initial=1000)
        assert exempt.value_net[-1] > small.value_net[-1]
        assert exempt.value_net[-1] == pytest.approx(1000 * 1.1**2)


class TestVorabpauschale:
    def test_vorab_tax_hand_computed(self):
        # 1 year, 10% return, basiszins 2.55%, taxed share 70%, TF 30%, tax 26.375%
        cfg = AppConfig(
            etf=EtfConfig(expected_return=0.10, years=1),
            tax=TaxConfig(
                basiszins=0.0255,
                vorabpauschale_taxed_share=0.70,
                teilfreistellung=0.30,
                capital_gains_tax_rate=0.26375,
                sparerpauschbetrag=0.0,
            ),
        )
        res = etf_projection(cfg, initial=1000)
        start_value = 1000
        value_gross = 1000 * 1.10  # 1100
        vorab = start_value * 0.0255  # 25.5
        tax_vorab = vorab * 0.7 * 0.7 * 0.26375  # 3.29...
        value_after_vorab = value_gross - tax_vorab
        # sale tax on total gain
        gain = value_after_vorab - 1000
        sale_tax = gain * 0.7 * 0.26375
        expected_net = value_after_vorab - sale_tax
        assert res.value_net[-1] == pytest.approx(expected_net, rel=1e-9)

    def test_allowance_applied_in_year1(self):
        # Sparerpauschbetrag 1000 > vorab gain -> no vorab tax
        cfg = AppConfig(
            etf=EtfConfig(expected_return=0.07, years=2),
            tax=TaxConfig(basiszins=0.0255, sparerpauschbetrag=1000.0),
        )
        res = etf_projection(cfg, initial=1000)
        assert res.taxes_paid[1] == pytest.approx(0.0)


class TestNetReturn:
    def test_net_return_below_gross(self):
        cfg = AppConfig(etf=EtfConfig(expected_return=0.07, years=20))
        assert etf_net_return(cfg) < 0.07

    def test_net_return_positive(self):
        cfg = AppConfig(etf=EtfConfig(expected_return=0.07, years=20))
        assert 0.05 < etf_net_return(cfg) < 0.07
