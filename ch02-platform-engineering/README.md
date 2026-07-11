# Chapter 02: Platform Engineering as the Foundation

Code for Chapter 2. Each listing in the printed book maps to a file here.

| Listing | File | Description |
|---|---|---|
| 2-1 | `catalog-info.yaml` | Backstage Component entity for the `payments-api` service |
| 2-2 | `scaffolder-templates/service/template.yaml` | Backstage software template that scaffolds a Python service plus its OpenTelemetry stub and registers it in the catalog |
| 2-3 | `scaffolder-templates/model/skeleton/inference-service.yaml` | The "deploy a model" golden-path skeleton: a parameterized KServe InferenceService (GPU limit templated conditionally) |
| unnumbered (2.8) | `scaffolder-templates/model/template.yaml` | The "deploy a model" template itself; its `parameters` block is printed in Section 2.8 |
| not printed | `org.yaml` | Group entities (`team-payments`, `team-platform`) for the `OwnerPicker` field |
| not printed | `scaffolder-templates/service/skeleton/` | Skeleton the service template renders: a templated `catalog-info.yaml` plus the OpenTelemetry stub (`otel_setup.py`) |
| not printed | `scaffolder-templates/model/skeleton/catalog-info.yaml` | Templated catalog entry the model golden path registers |

## Notes

- `catalog-info.yaml`, `org.yaml`, and the two `template.yaml` files are standalone valid YAML. Files under `skeleton/` directories are Backstage scaffolder skeletons: they contain `${{ values.* }}` substitutions (and, in `inference-service.yaml`, a `{% if %}` conditional), so they are rendered by the `fetch:template` step, not applied directly.
- Annotations used are real Backstage annotations: `argocd/app-name` (Argo CD plugin), `backstage.io/kubernetes-label-selector` and `backstage.io/kubernetes-id` (Kubernetes plugin), `backstage.io/techdocs-ref` (TechDocs), `prometheus.io/scrape` (Prometheus scrape). They are inert until the matching Backstage plugin is installed; the entities ingest and the scaffolder runs fine without them.

## Prerequisites

- **Node.js 22 or 24.** Backstage tracks the active Node LTS releases. `node --version` before you start.
- **A GitHub personal access token** (classic) with `repo` and `workflow` scopes, exported as `GITHUB_TOKEN`. The `publish:github` scaffolder action creates the new repository with it.
- **A GitHub org or user account you control.** Both templates hardcode `owner=saas-team` in their `repoUrl`; change it to your org or username before running.
- **Group entities in the catalog.** The `OwnerPicker` field in both templates lists Group entities; register `org.yaml` (step 3 below) or the dropdown stays empty.

## Run the lab

1. **Create the app.** Run `npx @backstage/create-app@latest` and accept or edit the suggested name. Expected: a new directory containing `packages/app`, `packages/backend`, and a `backstage.json` that records the Backstage release you just scaffolded against.
2. **Wire the GitHub integration.** In the generated `app-config.yaml`, add:

   ```yaml
   integrations:
     github:
       - host: github.com
         token: ${GITHUB_TOKEN}
   ```

   and export `GITHUB_TOKEN` in the shell you will start Backstage from. Expected: no visible change yet; the scaffolder's publish step now has credentials.
3. **Register this chapter's files.** Add four `type: file` locations under `catalog.locations` in `app-config.yaml`, adjusting the relative paths to where you cloned this repo:

   ```yaml
   catalog:
     locations:
       - type: file
         target: ../ch02-platform-engineering/org.yaml
         rules:
           - allow: [Group, User]
       - type: file
         target: ../ch02-platform-engineering/catalog-info.yaml
       - type: file
         target: ../ch02-platform-engineering/scaffolder-templates/service/template.yaml
         rules:
           - allow: [Template]
       - type: file
         target: ../ch02-platform-engineering/scaffolder-templates/model/template.yaml
         rules:
           - allow: [Template]
   ```

   The `rules` entries matter: the default catalog rules do not ingest `Group`, `User`, or `Template` kinds from arbitrary locations. Expected: nothing yet; the entities load at startup.
4. **Start it.** Run `yarn start` from the app root. Expected: the portal opens at `http://localhost:3000`, `payments-api` is in the catalog with `team-payments` as its owner, and the Create page lists both golden-path templates.
5. **Scaffold a service.** On the Create page, choose "Python service with OpenTelemetry", fill in a name, pick an owner from the dropdown, name a system, and run it. Expected: the step log shows `fetch`, `publish`, and `register` completing in order, a new repository appears in your GitHub org containing the rendered `catalog-info.yaml` and `otel_setup.py`, and the new component appears in the catalog.

## Troubleshooting

- **The OwnerPicker dropdown is empty.** The `org.yaml` location is missing or lacks the `allow: [Group, User]` rule, so the Group entities were never ingested.
- **The publish step fails with a 404 or 403.** Either `GITHUB_TOKEN` lacks the `repo` and `workflow` scopes, or the `owner=` in the template's `repoUrl` does not match an org or account the token can create repositories in.
- **A template never appears on the Create page.** Its location is missing the `allow: [Template]` rule, or the backend logged a YAML parse error at startup; check the terminal running `yarn start`.

## Version pinning

Backstage is a CNCF Incubating project as of 2026. `create-app` pins the release it scaffolds in the generated `backstage.json`; commit that file so later upgrades are deliberate rather than accidental. Both templates use the stable `scaffolder.backstage.io/v1beta3` template API, which is unchanged across recent Backstage releases, so the listings do not depend on a specific minor version.
