import math

import pytest

from pv_vs_etf.irr import annuity_payment, break_even_year, irr, npv, simple_payback


class TestNpvIrr:
    def test_npv_zero_rate_is_sum(self):
        assert npv(0.0, [-100, 60, 60]) == pytest.approx(20.0)

    def test_npv_known_value(self):
        # -100 + 110/1.1 = 0
        assert npv(0.10, [-100, 110]) == pytest.approx(0.0, abs=1e-9)

    def test_irr_simple(self):
        assert irr([-100, 110]) == pytest.approx(0.10, abs=1e-7)

    def test_irr_two_year(self):
        r = irr([-100, 60, 60])
        assert npv(r, [-100, 60, 60]) == pytest.approx(0.0, abs=1e-6)
        assert r == pytest.approx(0.13066, abs=1e-4)

    def test_irr_none_when_no_sign_change(self):
        assert irr([100, 50]) is None

    def test_irr_conventional_project(self):
        # investment 1000, 10 years of 150 -> IRR ~ 8.14%
        cfs = [-1000] + [150] * 10
        r = irr(cfs)
        assert r is not None
        assert r == pytest.approx(0.0814, abs=1e-3)


class TestBreakEven:
    def test_break_even_exact(self):
        assert break_even_year([-100, 60, 40]) == pytest.approx(2.0)

    def test_break_even_fractional(self):
        be = break_even_year([-100, 60, 60])
        assert be == pytest.approx(1.6667, abs=1e-3)

    def test_break_even_never(self):
        assert break_even_year([-100, 10, 10]) is None

    def test_simple_payback(self):
        assert simple_payback([-100, 60, 60]) == pytest.approx(1.6667, abs=1e-3)

    def test_simple_payback_none(self):
        assert simple_payback([-100, 10, 10]) is None


class TestAnnuity:
    def test_zero_rate(self):
        assert annuity_payment(1000, 0.0, 10) == pytest.approx(100.0)

    def test_known_annuity(self):
        p = annuity_payment(100_000, 0.03, 10)
        # payment * annuity factor = 100000
        factor = (1 - 1.03**-10) / 0.03
        assert p * factor == pytest.approx(100_000, rel=1e-9)
        assert p == pytest.approx(11_723.05, abs=0.01)


def test_cagr_roundtrip():
    from pv_vs_etf.irr import cagr

    assert cagr(1000, 2000, 10) == pytest.approx(2**0.1 - 1)
    assert math.isnan(cagr(0, 100, 10))
