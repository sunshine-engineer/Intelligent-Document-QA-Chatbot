# GCP Production-Style Deployment v1 Plan

## Classification

This is a hardened, production-style portfolio deployment: one Compute Engine VM with best-effort recovery. It is not highly available and must not be described as production-ready until formal RPO/RTO, application-consistent backups, redundancy, capacity testing, and incident procedures exist.

## Architecture

- Cloud Shell Bash entrypoint wrapping Terraform with remote GCS state.
- Default `asia-south1`, `e2-standard-4`, and a 100 GB persistent data disk.
- Artifact Registry images tagged by commit SHA and deployed by immutable digest.
- GitHub Actions keyless authentication through Workload Identity Federation.
- Ubuntu Shielded VM, OS Login, IAP-only SSH, least-privilege service accounts, and Secret Manager.
- Caddy HTTPS plus OAuth2 Proxy restricted to approved Google accounts.
- Internal Ollama, Streamlit, future FastAPI/worker, and PostgreSQL services; no direct backend ports.
- Health-gated restart with automatic rollback to the prior verified release.
- Cloud Monitoring runtime alerts and GitHub failed-workflow email notifications.
- Daily retained disk snapshots and a documented best-effort restore procedure.

## Interactive bootstrap inputs

Project/billing details, GitHub repository, region/zone, VM name/type, disk size, domain/DNS, alert email, allowed Google accounts, OAuth client ID/secret, Groq key, model settings, and an explicit billable-apply confirmation. Secrets are entered without echo and never stored in Terraform state.

## Dependency-ordered GitHub issues

1. **[GCP-01] Add the Cloud Shell bootstrap and Terraform state foundation** — validated prompts, API enablement, remote state, secret-safe plan/apply, and no implicit destroy.
2. **[GCP-02] Provision the network, registry, VM, static IP, and persistent storage** — custom VPC, reserved IP, Artifact Registry, Shielded VM, persistent disk, labels, and restricted ingress.
3. **[GCP-03] Add least-privilege identity, secrets, and keyless GitHub authentication** — VM/CI service accounts, WIF restricted to this repository/main, Secret Manager access, OS Login, IAP, and protected GitHub environment.
4. **[GCP-04] Install and supervise the VM container runtime** — idempotent startup, pinned Docker/Compose, mounted data disk, release directories, log rotation, systemd supervision, and reboot recovery.
5. **[GCP-05] Add HTTPS, Google OAuth, and the production Compose topology** — Caddy, OAuth2 Proxy, secure cookies, internal networks, persistent FAISS/PDF/Ollama data, image pinning, and health contracts.
6. **[GCP-06] Build and publish immutable images after protected CI** — deploy only the exact successful `main` SHA, publish digest/SBOM/provenance, and retain active/previous releases.
7. **[GCP-07] Automatically deploy main with health gates and rollback** — serialized production environment, IAP delivery, host lock, digest verification, smoke checks, rollback, manual redeploy, and sanitized audit logs.
8. **[GCP-08] Add monitoring, failure emails, and best-effort recovery** — uptime/VM/disk/service alerts, verified Cloud Monitoring email, GitHub failure notifications, disk snapshots, and restore instructions.
9. **[GCP-09] Prove the deployment workflow and publish the operations guide** — clean bootstrap, automatic redeploy, injected failure rollback, VM restart, OAuth, alert, restore, teardown, and honest documentation.

## Closure gates

- Create milestone `GCP Production-Style Deployment v1` with no due date.
- Create the epic `[EPIC] Automate the GCP production-style single-VM deployment` and all nine child issues.
- Apply `enhancement` to the epic and GCP-01 through GCP-08; apply `enhancement` and `documentation` to GCP-09.
- Link this epic to FastAPI epic #33 and API-10 issue #43.
- Replace dependency placeholders with actual issue links and audit ordering/labels/open state.
- Use one `CXOED/gcp-XX-*` branch and focused PR per issue; close only after protected CI passes and the PR merges.
- Do not create a branch until the GitHub issue audit passes.
