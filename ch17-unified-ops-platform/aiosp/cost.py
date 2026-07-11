"""Token-to-cost conversion for the unified trace.

OpenTelemetry's GenAI semantic conventions define token-usage attributes
(gen_ai.usage.input_tokens, gen_ai.usage.output_tokens) but NO standard cost or
price attribute. Cost is therefore a custom attribute the platform computes from
token counts and a per-model price table. We namespace it as app.gen_ai.cost_usd
so nobody mistakes it for an OpenTelemetry standard.

Prices are illustrative USD per 1,000 tokens and live in one place so the trace,
the dashboards, and the chargeback report all agree.
"""

from __future__ import annotations

# Custom (non-standard) attribute key. The app. prefix marks it as ours, not part
# of the gen_ai.* convention.
APP_GENAI_COST_USD = "app.gen_ai.cost_usd"

# Illustrative price table: USD per 1,000 tokens, (input, output).
_PRICES_PER_1K = {
    "incident-copilot": (0.0005, 0.0015),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost of a generation, rounded to 6 decimal places.

    Falls back to the incident-copilot price for unknown models so the platform
    never silently reports a zero cost for a model it does not have a price for.
    """
    input_per_1k, output_per_1k = _PRICES_PER_1K.get(
        model, _PRICES_PER_1K["incident-copilot"]
    )
    cost = (input_tokens / 1000.0) * input_per_1k + (
        output_tokens / 1000.0
    ) * output_per_1k
    return round(cost, 6)
