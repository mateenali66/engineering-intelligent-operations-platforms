"""Listing 13-4 (RUNS IN CI): a token cost meter over the GenAI span.

The opener's five-figure bill had one cause: per-token economics met unbounded
input, with no budget, no cap, and no cheaper fallback for simple queries. This
module is the countermeasure. It reads the same token counts Lab 1 already put on
the span (gen_ai.usage.input_tokens / output_tokens), turns them into dollars
with an explicit price table, and accumulates spend per route. It enforces two
separate limits: a soft downshift line, past which requests go to the cheapest
route, and a hard daily cap, which no request may cross. Before each call the
meter reserves the call's worst-case cost (the real input plus the max_tokens
output cap), so an admitted call cannot push spend past the cap, and a request
that fits on no route is refused, however often it is retried.

This is an in-process meter for one instance. Section 13.7 covers what a
production version adds: a shared store for reservations across instances and a
daily reset keyed on the date.

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


MAX_OUTPUT_TOKENS = 1_024  # the max_tokens cap sent with every call


class BudgetExceeded(Exception):
    """Raised when a request's worst-case cost fits on no route."""


def cost_usd(route: str, in_tok: int, out_tok: int) -> float:
    """Cost of one request from its token counts and the per-1M price table."""
    price = PRICES_PER_1M[route]
    return (in_tok * price["input"] + out_tok * price["output"]) / 1_000_000


class CostMeter:
    """Per-route spend with a soft downshift line and a hard daily cap."""

    def __init__(self, daily_budget_usd: float, downshift_at: float = 0.5,
                 cheapest_route: str = MINI):
        self.budget = daily_budget_usd
        self.downshift_line = daily_budget_usd * downshift_at
        self.cheapest = cheapest_route
        self.reserved = 0.0
        self.cost_by_route: dict[str, float] = defaultdict(float)
        self.tokens_by_route: dict[str, int] = defaultdict(int)

    @property
    def spent(self) -> float:
        return sum(self.cost_by_route.values())

    def admit(self, requested: str, in_tok: int) -> tuple[str, float]:
        """Choose a route and reserve its worst-case cost, or refuse."""
        committed = self.spent + self.reserved
        first = requested if committed < self.downshift_line else self.cheapest
        for route in dict.fromkeys((first, self.cheapest)):
            worst = cost_usd(route, in_tok, MAX_OUTPUT_TOKENS)
            if committed + worst <= self.budget:
                self.reserved += worst
                return route, worst
        raise BudgetExceeded(f"daily cap ${self.budget:.2f} reached, refusing")

    def settle(self, route: str, reservation: float,
               in_tok: int, out_tok: int) -> float:
        """Release the reservation and charge what the call actually used."""
        self.reserved -= reservation
        charge = cost_usd(route, in_tok, out_tok)
        self.cost_by_route[route] += charge
        self.tokens_by_route[route] += in_tok + out_tok
        return charge


# The workload the meter replays below: a label, the route the caller asked for,
# the token counts, and how many times it arrives. The first row reuses Lab 1's
# span (41 in / 32 out); the pasted-document rows are the opener's runaway, a
# client retrying a long input on the frontier route over and over.
WORKLOAD = [
    ("incident question", FRONTIER, 41, 32, 2),
    ("pasted runbook dump", FRONTIER, 150_000, 600, 30),
    ("simple greeting", MINI, 41, 32, 1),
]


def run(meter: CostMeter) -> list[tuple[str, str, int]]:
    """Replay the workload; return (label, outcome, count) runs in order."""
    runs: list[tuple[str, str, int]] = []
    for label, requested, in_tok, out_tok, repeat in WORKLOAD:
        for _ in range(repeat):
            try:
                route, held = meter.admit(requested, in_tok)
            except BudgetExceeded:
                outcome = "REFUSED, daily cap reached"
            else:
                meter.settle(route, held, in_tok, out_tok)
                outcome = f"served on {route}"
                if route != requested:
                    outcome += " (downshifted)"
            if runs and runs[-1][:2] == (label, outcome):
                runs[-1] = (label, outcome, runs[-1][2] + 1)
            else:
                runs.append((label, outcome, 1))
    return runs


if __name__ == "__main__":
    m = CostMeter(daily_budget_usd=1.00)
    print(f"daily cap: $1.00, downshift at ${m.downshift_line:.2f} "
          f"(frontier {FRONTIER}, fallback {MINI})")
    for label, outcome, count in run(m):
        print(f"  {count:>2} x {label:<20} {outcome}")
    print("per-route ledger:")
    for route in (FRONTIER, MINI):
        print(
            f"  {route:<20} {m.tokens_by_route[route]:>9} tokens "
            f"${m.cost_by_route[route]:.4f}"
        )
    assert m.spent <= m.budget and abs(m.reserved) < 1e-9
    print(f"total spend: ${m.spent:.4f} of $1.00 cap, never exceeded")
