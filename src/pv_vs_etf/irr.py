"""NPV, IRR and break-even calculations. Own solver, no numpy_financial."""

from __future__ import annotations

import math


def npv(rate: float, cashflows: list[float]) -> float:
    """Net present value of cashflows starting at t=0 (no discounting of first)."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def irr(
    cashflows: list[float], lo: float = -0.99, hi: float = 1.0, tol: float = 1e-10
) -> float | None:
    """Internal rate of return via bisection on the NPV.

    Returns None if no sign change in [lo, hi] (no IRR in that range).
    """
    f_lo, f_hi = npv(lo, cashflows), npv(hi, cashflows)
    if f_lo == 0.0:
        return lo
    if f_hi == 0.0:
        return hi
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < tol or (hi - lo) / 2.0 < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def break_even_year(cashflows: list[float]) -> float | None:
    """Break-even year of a raw cashflow series (== simple payback, fractional years)."""
    return simple_payback(cashflows)


def simple_payback(cashflows: list[float]) -> float | None:
    """Amortization period in years (first point cumulative >= 0), fractional."""
    running = 0.0
    for t, cf in enumerate(cashflows):
        prev = running
        running += cf
        if running >= 0.0 and t > 0:
            if running == prev:
                return float(t)
            frac = -prev / (running - prev)
            return (t - 1) + frac
    return None


def annuity_payment(principal: float, rate: float, years: int) -> float:
    """Constant annuity payment for a loan (rate=0 -> principal/years)."""
    if rate <= 0:
        return principal / years
    q = 1.0 + rate
    return principal * (q**years * rate) / (q**years - 1.0)


def cagr(start: float, end: float, years: int) -> float:
    """Compound annual growth rate."""
    if start <= 0 or years <= 0:
        return math.nan
    return (end / start) ** (1.0 / years) - 1.0
