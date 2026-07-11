# Engineering Intelligent Operations Platforms - Companion Code

Companion source code for the book *Engineering Intelligent Operations Platforms: The DevOps Engineer's Guide to AIOps, MLOps, and LLMOps* by Mateen Ali Anjum (Apress, forthcoming).

Every nontrivial code listing in the book exists here as a runnable file. The printed listing is an excerpt; the full, runnable version lives in this repo, pinned to specific tool versions and tested in CI. This is the defense against code rot across 18 chapters.

## Layout

One directory per chapter:

```
ch01-convergence/         ch10-pipeline-orchestration/
ch02-platform-engineering/ ch11-model-serving/
ch03-observability/       ch12-ml-monitoring-drift/
ch04-iac-ai-era/          ch13-llmops-discipline/
ch05-intro-aiops/         ch14-llm-devops-tools/
ch06-anomaly-detection/   ch15-rag-operations/
ch07-finops-aiops/        ch16-securing-governing-ai/
ch08-chaos-engineering/   ch17-unified-ops-platform/
ch09-mlops-fundamentals/  ch18-future-intelligent-ops/
```

Each chapter directory has its own README mapping book listings (Listing N-x) to files, plus any prerequisites and pinned versions specific to that chapter.

## Listing-to-file convention

In the book, a listing is captioned "Listing 6-2". In this repo it lives at `ch06-anomaly-detection/listing-6-2-isolation-forest.py` (or similar), and the chapter README has a table mapping the two. The printed code matches the file where shown.

## Running the examples

- The running example across the book is one platform stack. Parts II onward build on a kind or EKS cluster with the OpenTelemetry Collector, Prometheus, Grafana, and Loki. Part III onward grows it into the unified platform (AIOSP).
- Versions are pinned per chapter. Do not assume "latest"; use the versions in each chapter README and in the pin files, because tool APIs in this space move fast.
- Where a listing needs cloud resources (S3, GPUs), the README notes it and, where possible, offers a local-only path.

## CI

A GitHub Actions workflow at `.github/workflows/ci.yml` validates the committed code listings on every push and pull request to `main`. It runs twenty-two independent jobs:

| Job | What it validates | Gating |
|---|---|---|
| `yaml-lint` | ch02 `catalog-info.yaml` and scaffolder `template.yaml`; ch03 OTel Collector config and operator CR; ch05 Argo remediation runbook; ch08 Chaos Mesh manifests | Yes |
| `ch03-python` | ch03 Python listings: ruff lint, `py_compile` on all three files, end-to-end run of `drain_templates.py` | Yes |
| `ch05-python` | ch05 `decide.py`: ruff lint, `py_compile`, and full run of its embedded confidence-gate assertion suite | Yes |
| `ch06-python` | ch06 anomaly-detection pipeline: ruff lint, `py_compile`, and an end-to-end `run_smoke.py` that trains every model family on a synthetic slice and asserts the AUC gate and density separation | Yes |
| `ch07-python` | ch07 FinOps pipeline: ruff lint, `py_compile`, and an end-to-end `run_smoke.py` that ingests synthetic FOCUS billing, detects the spend spike, forecasts with SARIMAX, and frames dollars | Yes |
| `ch08-python` | ch08 chaos flywheel: ruff lint, `py_compile`, and an end-to-end `run_smoke.py` that injects a fault, confirms the Chapter 6 detector responds, runs the review gate, and round-trips exported labels through Chapter 6's own loader | Yes |
| `ch09-python` | ch09 MLOps lab: ruff lint, `py_compile`, and an end-to-end `run_smoke.py` that trains and registers the detector to a real MLflow 3 registry and runs the validation gate (pass on hold, block on regression) | Yes |
| `ch10-kfp` | ch10 Kubeflow Pipelines v2 listing: ruff lint, then compile `pipeline.py` to the IR and assert the v2 shape (`components`/`deploymentSpec`/`root`, `schemaVersion` 2.1.0), no cluster | Yes |
| `ch10-airflow` | ch10 Airflow 3 asset DAG: ruff lint, then a DagBag parse that asserts both DAGs register with zero import errors, no scheduler | Yes |
| `ch10-zenml` | ch10 ZenML pipeline: ruff lint, then a hermetic local-stack run that executes both steps | Yes |
| `ch10-dvc` | ch10 DVC caching: ruff lint, then `dvc repro` twice in an isolated temp repo, asserting the second run skips both stages | Yes |
| `ch11-serving` | ch11 serving: ruff, then serve the anomaly-detector through MLServer (KServe's sklearn runtime) and assert a V2 Open Inference Protocol response, then run the load harness; the KServe manifests are validated by `yaml-lint` (a real deploy needs a cluster/GPU) | Yes |
| `ch12-monitoring` | ch12 monitoring: ruff, then `run_smoke.py` runs NannyML CBPE (label-free estimate + the `ml_estimated_roc_auc` gauge), Evidently drift exported to Prometheus gauges, and River ADWIN streaming detection, all in one Python 3.12 venv; the alert rule is validated with promtool and the Grafana dashboard with a JSON parse | Yes |
| `ch13-llmops` | ch13 LLMOps: ruff, emit an OpenTelemetry GenAI span and assert its gen_ai.* attributes, run a deterministic DeepEval eval gate (pass + asserted-fail), yamllint the Promptfoo probe set; live LLM/Langfuse/Ragas paths are validation-only | Yes |
| `ch14-iacgen` | ch14 iacgen: install Checkov 3.3.1 + Trivy 0.71.1 + Conftest 0.68.2, warm the Trivy bundle, then run the bounded generate-scan-repair loop on recorded fixtures (generation stubbed, scanners real), assert convergence, gate with OPA, upload merged SARIF to code scanning | Yes |
| `ch15-rag` | ch15 Incident Copilot against a `pgvector/pgvector:pg17` service container: schema + ingest (local MiniLM, 384-dim), dense + Postgres `tsvector` lexical retrieval fused with RRF, FlashRank ONNX rerank, contextual-retrieval A/B, and a deterministic faithfulness gate; hybrid beats dense on the identifier query, rerank lifts MRR to 1.000. The LLM generation, live Ragas/TruLens judges, and the LangGraph agent are validation-only (compile-checked) | Yes |
| `ch16-guardrails` | ch16 layered guardrail proxy + attack harness: a FastAPI proxy runs input defenses, a lethal-trifecta containment check, a stubbed LLM, and output defenses; the harness proves a direct jailbreak is blocked at input, indirect injection slips past output filtering, and the trifecta exfiltration is stopped by containment; plus a stdlib pickle-danger demo. Prompt Guard 2, Llama Guard 4 (12B/GPU), Presidio NER, Guardrails AI, NeMo, and managed cloud guardrails are validation-only (compile-checked) | Yes |
| `ch17-platform` | ch17 AIOSP capstone: yamllints the GitOps manifests (three KServe InferenceServices, the Argo CD Applications + app-of-apps, the OTel Collector), then the convergence check asserts the three disciplines share one serving API (predictive AND generative), one Argo delivery loop, and one OTLP endpoint, and the unified trace asserts an infra span and a gen_ai child span share one trace with token usage and a computed cost; three negative tests prove the check fails when any substrate diverges. The live `kind` deploy, KServe Hugging Face/vLLM serving, and Backstage are validation-only | Yes |
| `ch18-future` | ch18 agent control plane (pure stdlib): an L2 remediation agent opens a diagnosis PR and a remediation PR and cannot actuate; the smoke test and suite assert it changes nothing until a human approves, that it cannot approve its own work (separation of duties), that only an approved change reconciles (r42 -> r41), that the red button (guardian) halts the agent, and that the agent is structurally pinned at L2 (no actuate method). A real LLM agent and the OpenTelemetry agent conventions (still Development) are validation-only | Yes |
| `iac-clean` | ch04 `clean-module/` passes Checkov 3.3.1 and Trivy 0.71.1 at HIGH/CRITICAL severity | Yes |
| `iac-insecure` | ch04 `generated-module/` expected to fail both scanners (teaching artifact, non-gating) | No |
| `iac-policy` | ch04 Conftest 0.68.2 policy tests: two pass fixtures must pass, one deny fixture must fire | Yes |

The ch02 Backstage scaffolder skeleton (`scaffolder-templates/model/skeleton/inference-service.yaml`) is excluded from YAML lint because it contains Jinja2 `{%- if %}` blocks that are not valid YAML tokens. Its `template.yaml` parent is linted normally.

## Status

As of June 21, 2026, chapter directories `ch01` through `ch18` are populated (all 18) with runnable, version-pinned, CI-tested code. The root CI runs 22 gating jobs (above). The repository is built alongside the manuscript; Apress migrates it into the official `github.com/Apress` organization near production.

## License

Code in this repository is released under the MIT License (see `LICENSE`). The book text is copyright the author and Apress and is not part of this repository.

## Errata and contributions

After publication, readers may open issues and pull requests for code corrections; the author approves changes. Until then this repo tracks the manuscript and is not yet open for external PRs.
