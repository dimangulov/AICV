---
phase: 01-infra-wiring-local-smoke-test
plan: 01
subsystem: infrastructure
tags: [terraform, github-actions, liveavatar, config-wiring]
requirements:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
  - INFRA-06
  - INFRA-07
dependency_graph:
  requires:
    - "existing live_avatar_avatar_id wiring pattern (variables.tf / main.tf / deploy-azure.yml)"
    - "backend/config.py reads LIVEAVATAR_IS_SANDBOX and LIVEAVATAR_SESSION_MODE (read-only reference, no edit)"
  provides:
    - "TF variable live_avatar_is_sandbox (bool, default true)"
    - "TF variable live_avatar_session_mode (string, default LITE, validated)"
    - "Container App env LIVEAVATAR_IS_SANDBOX"
    - "Container App env LIVEAVATAR_SESSION_MODE"
    - "Workflow TF_VAR_live_avatar_is_sandbox fallback 'true'"
    - "Workflow TF_VAR_live_avatar_session_mode fallback 'LITE'"
  affects:
    - "Phase 2 deploy path — tier flag now propagates end-to-end"
    - "Local operators running `terraform plan` — documented in tfvars.example"
tech_stack:
  added: []
  patterns:
    - "3-point wiring (TF variable → main.tf env block → workflow TF_VAR_*) mirroring live_avatar_avatar_id"
key_files:
  created: []
  modified:
    - infra/terraform/variables.tf
    - infra/terraform/main.tf
    - infra/terraform/terraform.tfvars.example
    - .github/workflows/deploy-azure.yml
decisions:
  - "Used tostring(var.live_avatar_is_sandbox) to coerce bool→string for Container App env.value (string-typed attribute). backend/config.py:60 does .lower()==\"true\" so \"true\"/\"True\"/\"TRUE\" all work."
  - "Workflow fallbacks hardcoded as 'true' and 'LITE' to match TF defaults per D-03 — GitHub-variable absence is a safe no-op, not a regression."
  - "validation{} block on live_avatar_session_mode constrains to LITE|FULL|CUSTOM per D-02 — hard-fails at terraform plan rather than 422ing in prod."
metrics:
  tasks: 2
  commits: 2
  files_modified: 4
  files_created: 0
  backend_python_files_modified: 0
  duration: ~4 min
  completed: 2026-04-22
---

# Phase 1 Plan 1: Terraform + Workflow Wiring for LiveAvatar Sandbox/Session-Mode Summary

Closed the confirmed 3-point Terraform/workflow wiring gap so `LIVEAVATAR_IS_SANDBOX` and `LIVEAVATAR_SESSION_MODE` propagate from GitHub repository variables through Terraform into the backend Container App env on the next deploy — mirroring the existing `live_avatar_avatar_id` pattern and touching zero backend Python code.

## Outcome

Four declarative config surfaces are now consistent:

1. **`infra/terraform/variables.tf`** — declares `live_avatar_is_sandbox` (`bool`, default `true`) and `live_avatar_session_mode` (`string`, default `"LITE"`, validated to `LITE|FULL|CUSTOM`). Placed immediately after `live_avatar_avatar_id` to keep LiveAvatar variables grouped.
2. **`infra/terraform/main.tf`** — adds two new `env {}` blocks inside `resource "azurerm_container_app" "backend".template.container`, placed directly after the existing `LIVEAVATAR_AVATAR_ID` block. The bool is stringified with `tostring(...)` because `env.value` is string-typed; `backend/config.py:60` parses the resulting `"true"`/`"false"` correctly with `.lower() == "true"`.
3. **`.github/workflows/deploy-azure.yml`** — adds `TF_VAR_live_avatar_is_sandbox` and `TF_VAR_live_avatar_session_mode` entries in the `Terraform Apply` step's `env:` map, each with a `${{ vars.X || 'default' }}` fallback matching the Terraform defaults.
4. **`infra/terraform/terraform.tfvars.example`** — documents both new variables so operators running `terraform plan` locally outside CI see the intended values.

## Changes by Task

### Task 1 — Variable declarations + tfvars.example (commit `59b1766`)

Added two variable blocks to `variables.tf`:

```hcl
variable "live_avatar_is_sandbox" {
  description = "LiveAvatar sandbox mode flag (free tier). Set via TF_VAR_live_avatar_is_sandbox or LIVE_AVATAR_IS_SANDBOX GitHub Actions variable."
  type        = bool
  default     = true
}

variable "live_avatar_session_mode" {
  description = "LiveAvatar session mode. Set via TF_VAR_live_avatar_session_mode or LIVE_AVATAR_SESSION_MODE GitHub Actions variable."
  type        = string
  default     = "LITE"
  validation {
    condition     = contains(["LITE", "FULL", "CUSTOM"], var.live_avatar_session_mode)
    error_message = "live_avatar_session_mode must be one of: LITE, FULL, CUSTOM."
  }
}
```

Appended to `terraform.tfvars.example`:

```hcl
live_avatar_is_sandbox   = true
live_avatar_session_mode = "LITE"
```

Files modified: `infra/terraform/variables.tf`, `infra/terraform/terraform.tfvars.example`.

### Task 2 — Container App env blocks + workflow TF_VARs (commit `39924a0`)

Added inside `azurerm_container_app.backend.template.container`, directly after `LIVEAVATAR_AVATAR_ID`:

```hcl
env {
  name  = "LIVEAVATAR_IS_SANDBOX"
  value = tostring(var.live_avatar_is_sandbox)
}
env {
  name  = "LIVEAVATAR_SESSION_MODE"
  value = var.live_avatar_session_mode
}
```

Added inside the `Terraform Apply` step's `env:` map:

```yaml
TF_VAR_live_avatar_is_sandbox:  ${{ vars.LIVE_AVATAR_IS_SANDBOX || 'true' }}
TF_VAR_live_avatar_session_mode: ${{ vars.LIVE_AVATAR_SESSION_MODE || 'LITE' }}
```

Files modified: `infra/terraform/main.tf`, `.github/workflows/deploy-azure.yml`.

## Rationale Summary

- **`tostring(var.live_avatar_is_sandbox)`** — Azure Container App `env.value` attribute is string-typed. The bool variable must be coerced. `tostring(true)` → `"true"`, which `backend/config.py:60` (`os.getenv("LIVEAVATAR_IS_SANDBOX", "false").lower() == "true"`) parses correctly.
- **Fallback parity with TF defaults** (D-03) — `'true'` and `'LITE'` fallbacks in the workflow match the Terraform defaults. Missing GitHub repository variables cannot silently regress the tier flag to paid/full.
- **`validation{}` block on session mode** (D-02) — `contains(["LITE", "FULL", "CUSTOM"], ...)` hard-fails at `terraform plan` on unknown values rather than letting a typo reach LiveAvatar as a 422 in prod.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were required; no architectural escalations (Rule 4). All acceptance criteria met on the first pass.

## Verification Results

Full plan `<verification>` block, executed from repo root:

| Check | Expected | Actual |
|-------|---------:|-------:|
| `grep -c 'variable "live_avatar_is_sandbox"' infra/terraform/variables.tf` | 1 | 1 |
| `grep -c 'variable "live_avatar_session_mode"' infra/terraform/variables.tf` | 1 | 1 |
| `grep -c 'name  = "LIVEAVATAR_IS_SANDBOX"' infra/terraform/main.tf` | 1 | 1 |
| `grep -c 'name  = "LIVEAVATAR_SESSION_MODE"' infra/terraform/main.tf` | 1 | 1 |
| `grep -c "TF_VAR_live_avatar_is_sandbox:" .github/workflows/deploy-azure.yml` | 1 | 1 |
| `grep -c "TF_VAR_live_avatar_session_mode:" .github/workflows/deploy-azure.yml` | 1 | 1 |
| `grep -c "live_avatar_is_sandbox" infra/terraform/terraform.tfvars.example` | 1 | 1 |

Scope discipline check — `git diff --name-only HEAD~2 HEAD` returns only the 4 allowed files:

- `.github/workflows/deploy-azure.yml`
- `infra/terraform/main.tf`
- `infra/terraform/terraform.tfvars.example`
- `infra/terraform/variables.tf`

No `backend/*.py` entries present. D-13 honored.

## Commits

| Hash | Task | Message |
|------|------|---------|
| `59b1766` | Task 1 | feat(01-01): declare live_avatar_is_sandbox and live_avatar_session_mode TF variables |
| `39924a0` | Task 2 | feat(01-01): wire LIVEAVATAR_IS_SANDBOX and LIVEAVATAR_SESSION_MODE through Terraform and workflow |

## Known Stubs

None. This plan adds pure declarative wiring; no UI components, no placeholder data. The two new env vars are consumed by existing backend logic (`backend/config.py:60`, `backend/avatar.py:275`) that was already proven on the main path.

## Operator Note

Before handing off to Plan 02, run:

```bash
cd infra/terraform
terraform init    # if not previously initialized
terraform validate
```

`terraform validate` should exit 0. A full `terraform plan` additionally requires sensitive `TF_VAR_qdrant_cloud_url`, `TF_VAR_qdrant_cloud_api_key`, `TF_VAR_live_avatar_api_key` to be set in the environment, and is not required for Plan 02 to proceed.

## Self-Check: PASSED

Claim-by-claim verification (all on-disk after commits `59b1766` and `39924a0`):

- [x] `infra/terraform/variables.tf` exists and contains both new variable blocks — FOUND
- [x] `infra/terraform/main.tf` exists and contains both new env blocks inside `azurerm_container_app.backend` — FOUND
- [x] `.github/workflows/deploy-azure.yml` exists and contains both new `TF_VAR_*` entries — FOUND
- [x] `infra/terraform/terraform.tfvars.example` exists and contains both new example lines — FOUND
- [x] Commit `59b1766` — FOUND in `git log`
- [x] Commit `39924a0` — FOUND in `git log`
- [x] Two new TF variables declared with correct types, defaults, and validation — CONFIRMED
- [x] Two new env blocks in main.tf use `tostring()` for bool, plain `var.` for string — CONFIRMED
- [x] Two new TF_VAR_* lines in workflow with fallbacks `'true'` and `'LITE'` matching TF defaults — CONFIRMED
- [x] tfvars.example updated with both new variables preserving column alignment — CONFIRMED
- [x] Zero `backend/*.py` files modified (D-13 scope discipline) — CONFIRMED via `git diff --name-only HEAD~2 HEAD`
- [x] Zero files outside the four listed in `files_modified` were touched — CONFIRMED

All 7 plan verification grep counts returned 1. All acceptance criteria for both tasks satisfied. Ready for Plan 02.
