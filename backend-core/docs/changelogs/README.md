# Backend — Changelog Index

All notable changes to the **backend** service are documented here.

| Version | Date | Summary |
|---------|------|---------|| [v0.10.4](v0.10.4.md) | 2026-04-28 | Raw band ortho ZIP product types (band_green, band_red, band_red_edge, band_nir, band_blue) || [v0.10.3](v0.10.3.md) | 2026-03-29 | Celery task terminal status guard — prevent re-dispatch of cancelled/completed/failed jobs |
| [v0.10.2](v0.10.2.md) | 2026-03-29 | Deprecate radiometric_calibration parameter, derive from analysis_mode |
| [v0.10.1](v0.10.1.md) | 2026-03-12 | Healthcheck S3 resilience: degraded status, 3s timeout, credential fix |
| [v0.10.0](v0.10.0.md) | 2026-03-11 | Consolidate retry into rerun endpoint, remove /retry/ |
| [v0.9.0](v0.9.0.md) | 2026-03-09 | KPI metrics endpoint, auth failure tracking |
| [v0.8.0](v0.8.0.md) | 2026-03-08 | Request ID tracing, retry cancelled jobs |
| [v0.7.0](v0.7.0.md) | 2026-03-08 | Retry/cancel fix, AI Gateway client improvements |
| [v0.6.0](v0.6.0.md) | 2026-03-09 | S3 download reliability, dataset stats pagination, permission fixes |
| [v0.5.0](v0.5.0.md) | 2026-03-08 | Job timing, upload failure handling, duration fix |
| [v0.4.0](v0.4.0.md) | 2026-03-08 | RBAC, security hardening, integration & load tests (389 total) |
| [v0.3.0](v0.3.0.md) | 2026-03-07 | Health check, URL upload fix, job duration, FMIS webhooks, .env.example |
| [v0.2.0](v0.2.0.md) | 2026-03-05 | Analysis mode support (fast/full), multispectral pipeline parameter |
| [v0.1.0](v0.1.0.md) | 2026-03-05 | Dynamic metadata extraction, configurable extensions, metadata presigned URLs |
