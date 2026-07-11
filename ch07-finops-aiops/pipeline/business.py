"""Listing 7-4: translate model output into business framing.

The differentiator of FinOps ML is the metric. A forecaster's R-squared and a
detector's F1 are means, not ends. Finance acts on dollars saved, return on
investment, and payback period. In the review behind this chapter, only a small
fraction of studies reported any business outcome and almost none reported unit
economics, so producing these numbers is the part the literature skips.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SavingsCase:
    monthly_baseline_usd: float   # current monthly spend on the resource
    monthly_optimized_usd: float  # projected monthly spend after the change
    implementation_usd: float     # one-time cost to build and ship the change
    monthly_run_usd: float = 0.0  # ongoing cost of running the ML solution


def business_case(case):
    """Return dollar savings, ROI, and payback for an optimization."""
    gross_monthly = case.monthly_baseline_usd - case.monthly_optimized_usd
    net_monthly = gross_monthly - case.monthly_run_usd
    annual_net = net_monthly * 12
    roi = (annual_net - case.implementation_usd) / case.implementation_usd
    payback_months = (
        case.implementation_usd / net_monthly if net_monthly > 0 else float("inf")
    )
    return {
        "monthly_savings_usd": round(net_monthly, 2),
        "annual_savings_usd": round(annual_net, 2),
        "roi_first_year": round(roi, 2),
        "payback_months": round(payback_months, 1),
    }


def unit_economics(monthly_spend_usd, monthly_transactions):
    """Cost per transaction: the unit metric the corpus never reported."""
    return round(monthly_spend_usd / max(monthly_transactions, 1), 6)


if __name__ == "__main__":
    case = SavingsCase(
        monthly_baseline_usd=42_000,
        monthly_optimized_usd=31_000,
        implementation_usd=15_000,
        monthly_run_usd=400,
    )
    print("business case:", business_case(case))
    print("cost per transaction: $",
          unit_economics(31_000, monthly_transactions=2_400_000))
