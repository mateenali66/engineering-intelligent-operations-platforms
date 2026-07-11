"""Listing 13-4 (RUNS IN CI): a token cost meter over the GenAI span.

The opener's five-figure bill had one cause: per-token economics met unbounded
input, with no budget, no cap, and no cheaper fallback for simple queries. This
module is the countermeasure. It reads the same token counts Lab 1 already put on
the span (gen_ai.usage.input_tokens / output_tokens), turns them into dollars
with an explicit price table, accumulates spend per route, and enforces a daily
budget: over budget it downshifts a request to the cheapest route it has, and a
request already on that route (nowhere cheaper to go) is refused.

No LLM, no key, no network: the token counts come from the stub in Lab 1, so the
whole meter is deterministic and runs in CI. Swap in a live client and the
counts come from the provider's usage field instead; the meter is unchanged.

Run:
    python lab3_cost_meter.py
"""

from __future__ import annotations

from collections import defaultdict

# Illustrative list prices in USD per 1,000,000 tokens, mid-2026. These are
# stand-in numbers for a self-hosted stub, NOT a live vendor quote: put your
# provider's real per-1M input/output prices here and date them, because prices
# move. FRONTIER is the expensive high-quality route, MINI the cheap fallback.
FRONTIER = "anomaly-copilot-v1"
MINI = "anomaly-copilot-mini"
PRICES_PER_1M = {
    FRONTIER: {"input": 2.50, "output": 10.00},
    MINI: {"input": 0.15, "output": 0.60},
}


class BudgetExceeded(Exception):
    """Raised when the budget is spent and a request cannot be downshifted."""


def cost_usd(route: str, in_tok: int, out_tok: int) -> float:
    """Cost of one request from its token counts and the per-1M price table."""
    price = PRICES_PER_1M[route]
    return (in_tok * price["input"] + out_tok * price["output"]) / 1_000_000


class CostMeter:
    """Per-route token and cost accounting with a daily budget cap."""

    def __init__(self, daily_budget_usd: float, cheapest_route: str = MINI):
        self.budget = daily_budget_usd
        self.cheapest = cheapest_route
        self.cost_by_route: dict[str, float] = defaultdict(float)
        self.tokens_by_route: dict[str, int] = defaultdict(int)

    @property
    def spent(self) -> float:
        return sum(self.cost_by_route.values())

    def route_for(self, requested: str) -> str:
        """Honor the request under budget; over budget downshift, then refuse."""
        if self.spent < self.budget:
            return requested
        if requested != self.cheapest:
            return self.cheapest
        raise BudgetExceeded(f"daily budget ${self.budget:.2f} spent, refusing")

    def record(self, route: str, in_tok: int, out_tok: int) -> float:
        """Charge one served request to its route and return its cost."""
        charge = cost_usd(route, in_tok, out_tok)
        self.cost_by_route[route] += charge
        self.tokens_by_route[route] += in_tok + out_tok
        return charge


# The workload the meter replays below: a label, the route the caller asked for,
# and the token counts. The first two rows reuse Lab 1's span (41 in / 32 out);
# the "pasted document" rows are the opener's runaway, a long input on the
# frontier route.
WORKLOAD = [
    ("incident question", FRONTIER, 41, 32),
    ("incident question", FRONTIER, 41, 32),
    ("pasted runbook dump", FRONTIER, 200_000, 600),
    ("pasted runbook dump", FRONTIER, 200_000, 600),
    ("pasted runbook dump", FRONTIER, 200_000, 600),
    ("simple greeting", MINI, 41, 32),
]


def run() -> CostMeter:
    """Replay the workload through a $1.00/day meter and return the meter."""
    meter = CostMeter(daily_budget_usd=1.00)
    for label, requested, in_tok, out_tok in WORKLOAD:
        try:
            route = meter.route_for(requested)
        except BudgetExceeded as exc:
            print(f"  REFUSED {label:<20} ({requested}): {exc}")
            continue
        charge = meter.record(route, in_tok, out_tok)
        note = "" if route == requested else f"  downshifted from {requested}"
        print(f"  served  {label:<20} -> {route:<20} ${charge:.4f}{note}")
    return meter


if __name__ == "__main__":
    print(f"daily budget: $1.00   (frontier {FRONTIER}, fallback {MINI})")
    m = run()
    print("per-route ledger:")
    for route in (FRONTIER, MINI):
        print(
            f"  {route:<20} {m.tokens_by_route[route]:>7} tokens "
            f"${m.cost_by_route[route]:.4f}"
        )
    print(f"total spend: ${m.spent:.4f} of $1.00 budget")
