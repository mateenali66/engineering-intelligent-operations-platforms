"""Layered guardrail proxy for Chapter 16.

A FastAPI reverse proxy that runs input defenses, then a (stubbed) LLM, then
output defenses, with an architectural containment layer that breaks the lethal
trifecta. The deterministic pipeline runs headless in CI with no API key and no
GPU; Prompt Guard 2, Llama Guard 4, Presidio's NER, Guardrails AI, NeMo
Guardrails, and the managed cloud guardrails are validation-only and clearly
labeled. The point the lab demonstrates: input and output guardrails are
probabilistic and bypassable, so the control that actually contains indirect
prompt injection is architectural, not a classifier.
"""
