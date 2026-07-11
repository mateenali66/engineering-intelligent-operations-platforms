# Chapter 01: The Convergence of AI and Operations

Code listings for Chapter 01. Each listing in the printed book maps to a file here.

Chapter 1 is the framing chapter, and its two listings are illustrative teasers,
reproduced here exactly as printed. The runnable, CI-tested versions live where
the book develops them: the Collector pattern in `ch03-observability/` and
KServe serving in Part III.

| Listing | File | Description | Runnable version |
|---|---|---|---|
| 1-1 | `inference-service.yaml` | Simplified KServe InferenceService teaser | `ch11-model-serving/` (Chapter 11) |
| 1-2 | `otel-collector-teaser.yaml` | Minimal dual-routing Collector config teaser | `ch03-observability/collector-config/otel-collector-config.yaml` (Chapter 3) |

## Run

The teaser files are not meant to be applied as-is; they omit the surrounding
infrastructure the chapter describes. Follow Chapter 3 for the full Collector
deployment (including the contrib-build requirement for the `awss3` exporter)
and Chapter 11 for KServe model serving. Prerequisites and pinned versions are
listed in the repository root README.
