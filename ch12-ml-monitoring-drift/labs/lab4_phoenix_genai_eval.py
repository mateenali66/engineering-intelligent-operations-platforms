"""Listing 12-4 (validation-only bridge): Phoenix + OpenTelemetry GenAI tracing
with an LLM-as-judge eval.

This listing is the bridge to the LLMOps chapters (13 to 16). It is NOT run in
CI, for the same honest reason Chapter 11's vLLM path is not: it needs services
and credentials CI does not have.

  - Phoenix runs a collector/UI server (px.launch_app or a docker container) that
    receives OpenTelemetry GenAI spans. CI has no such server.
  - The LLM-as-judge eval calls an external LLM (OpenAI, Anthropic, Bedrock, ...)
    that needs an API key and network egress. CI has neither.

So this file is illustrative: it shows the code shape the chapter prints, but the
companion CI does not execute it. Run it locally with a Phoenix server up and an
LLM API key exported. Verified package line (mid-2026): arize-phoenix==17.9.0,
arize-phoenix-evals==3.1.0, both requiring python <3.15,>=3.10.

    pip install arize-phoenix==17.9.0 arize-phoenix-evals==3.1.0 \
        openinference-instrumentation-openai
    export OPENAI_API_KEY=...        # the judge model
    python lab4_phoenix_genai_eval.py
"""

from __future__ import annotations

# --- illustrative only: not imported or executed by CI -----------------------


def trace_and_judge():
    """Trace a GenAI call into Phoenix, then score it with an LLM judge."""
    import phoenix as px
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from phoenix.evals import OpenAIModel, llm_classify
    from phoenix.otel import register

    # 1. Start the Phoenix server and register the OTel tracer provider. Phoenix
    #    is the OTLP collector AND the UI; GenAI spans land here.
    px.launch_app()
    tracer_provider = register(project_name="anomaly-detector-copilot")
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    # 2. The traced GenAI call (the "explain this anomaly" copilot from later
    #    chapters). Instrumentation captures the prompt, response, and token
    #    usage as OpenTelemetry GenAI spans automatically.
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You explain infra anomalies tersely."},
            {"role": "user", "content": "Latency p95 tripled on checkout. Why?"},
        ],
    )
    answer = response.choices[0].message.content

    # 3. LLM-as-judge eval: a second model scores the answer for relevance. This
    #    is the call that needs an API key, so CI cannot run it.
    import pandas as pd

    template = (
        "You are grading an answer to an infrastructure question.\n"
        "Question: {input}\nAnswer: {output}\n"
        "Is the answer relevant and grounded? Reply relevant or irrelevant."
    )
    judged = llm_classify(
        data=pd.DataFrame([{"input": "Latency p95 tripled on checkout. Why?",
                            "output": answer}]),
        model=OpenAIModel(model="gpt-4o"),
        template=template,
        rails=["relevant", "irrelevant"],
    )
    return judged


if __name__ == "__main__":
    print(
        "Listing 12-4 is validation-only: it needs a running Phoenix server and "
        "an LLM API key, so the companion CI does not execute it. Run it locally "
        "with OPENAI_API_KEY exported. See the module docstring."
    )
