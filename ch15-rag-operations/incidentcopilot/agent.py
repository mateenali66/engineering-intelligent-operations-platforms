"""VALIDATION-ONLY: agentic RAG with LangGraph.

Agentic RAG lets the assistant decide whether to retrieve again rather than
retrieving exactly once: it can rewrite a vague query, do a second hop, or grade
the retrieved context and re-search if it is thin. This needs a chat model and a
key, so the file is py_compile-checked in CI and never executed. The
deterministic retrieve + rerank + eval pipeline is what CI proves.
"""

from __future__ import annotations


def build_incident_copilot_agent():  # pragma: no cover - validation-only
    """Shape only: a LangGraph 1.x agent over a hybrid-search retrieval tool.

        from langchain.agents import create_agent     # the LangChain 1.x API
        # (langgraph.prebuilt.create_react_agent is the lower-level alternative)

        def search_runbooks(query: str) -> str:
            '''Retrieve runbook and postmortem chunks for an incident query.'''
            hits = hybrid_search(conn, embedder, query, k=5)
            return format_context(hits)

        agent = create_agent(
            model="gpt-4.1",
            tools=[search_runbooks],
            prompt="You are an on-call incident copilot. Cite the runbook you used.",
        )
        return agent

    The agent decides when to call search_runbooks again; that control loop needs
    a model, so this is validation-only.
    """
    raise NotImplementedError("agentic RAG is validation-only; see docstring")
