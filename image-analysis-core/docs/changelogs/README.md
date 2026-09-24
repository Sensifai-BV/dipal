# Image Analysis Core — Changelog Index

All notable changes to the **image-analysis-core** service are documented here.

| Version | Date | Summary |
|---------|--------|---------|
| [v0.10.26](v0.10.26.md) | 2026-06-16 | Upload `fused_utm.ply` as a new `pointcloud_utm` product so the downloadable dense cloud carries usable UTM coordinates (was only the local-frame `fused.ply`). Adds ADR 0004 (MS single-band speckle, analysis only) |
| [v0.10.25](v0.10.25.md) | 2026-06-13 | Multispectral ortho through SFM poses — NDVI "puzzle-pieces" fix: bands now projected through the co-acquired RGB image's SFM pose + FULL_OPENCV intrinsics + DJI DewarpHMatrix/RelativeOpticalCenter instead of GPS direct-georeferencing, so all bands co-register on the DSM. Also fixes a `_reflectance`-stem mismatch that silently fell back to GPS (captures grouped 0→119, coverage 47.6→70.3 %). Opt-in via ORTHO_USE_POSE_ORTHO |
| [v0.10.24](v0.10.24.md) | 2026-06-13 | DSM doming fix — DJI factory intrinsics (FULL_OPENCV + k3) seeded from DewarpData XMP and locked in COLMAP; focal drift 5146→3713 px eliminated; dome curvature 4.5 m→0.21 m (~95 % reduction). Opt-in via COLMAP_SEED_FACTORY_INTRINSICS |
| [v0.10.23](v0.10.23.md) | 2026-06-10 | Inter-band co-registration — spectral bands were warped independently (GPS+yaw, nadir) so the offset M3M lenses misregistered; per-capture phase-correlation alignment to NIR reference cuts NDVI/NDRE/GNDVI noise (RED–NIR corr 0.062→0.201). See ADR 0001 |
| [v0.10.22](v0.10.22.md) | 2026-06-10 | SFM camera-model doming fix — reconstruction was using SIMPLE_RADIAL (k1 only) instead of the configured OPENCV because import_images pre-created cameras, causing DSM doming + MS misalignment; also emit UTM `fused_utm.ply` so coordinates are extractable |
| [v0.10.21](v0.10.21.md) | 2026-06-10 | Irradiance normalisation fix — raw DLS irradiance was used without dividing by its exposure × gain, making reflectance ~12× too low; reflectance now on correct physical scale (verified against M3M sample) |
| [v0.10.20](v0.10.20.md) | 2026-06-09 | Cross-band strip normalisation — one shared per-image gain across all bands fixes the recurring NDVI/NDRE/GNDVI flight-line banding; robust strip detection; reflectance magnitude/clip diagnostics; DSM viewer fixes |
| [v0.10.19](v0.10.19.md) | 2026-06-01 | Camera XMP namespace fix (irradiance now correctly read from DJI M3M); MRK tagged-token parser (RTK positions no longer discarded); gdalwarp UNIFIED_SRC_NODATA (NDVI boundary corruption eliminated) |
| [v0.10.18](v0.10.18.md) | 2026-05-12 | Multispectral alignment hard error, GPS prior fix, NDVI pipeline fix, irradiance warning |
| [v0.10.17](v0.10.17.md) | 2026-05-12 | Strip-level radiometric normalisation: PCA cross-track strip detection + two-pass GPS composite to eliminate inter-strip BRDF banding |
| [v0.10.16](v0.10.16.md) | 2026-05-12 | Multispectral bug fixes: median fallback nodata consistency, vegetation index nodata propagation, DSM mask on fallback path |
| [v0.10.15](v0.10.15.md) | 2026-05-11 | Multispectral mosaic feathering: distance-weighted blending replaces `gdal_merge` last-writer-wins to eliminate band seams |
| [v0.10.14](v0.10.14.md) | 2026-05-11 | Dense fusion fix: move `geo_register` after `compute_depthmaps`; `fusion_input_type` → `photometric` |
| [v0.10.13](v0.10.13.md) | 2026-05-11 | Wire `_filter_misaligned_cameras()` call into `geo_register`; add Scale/RMSE alignment diagnostics |
| [v0.10.12](v0.10.12.md) | 2026-05-11 | Apply geo-registration fixes that were documented in v0.10.9–11 but never committed: ref_images.txt GPS file, COLMAP 3.13 flag corrections (`ecef`, `--alignment_max_error`, `--ref_is_gps`), fusion_max_depth_error 0.05 |
| [v0.10.11](v0.10.11.md) | 2026-05-07 | SFM geo-registration robustness: safe model_aligner staging, 0_original backup, RMSE/scale diagnostics, camera outlier filter, fusion_max_depth_error 0.05 |
| [v0.10.10](v0.10.10.md) | 2026-05-04 | PDAL OOM fix (5 cm default resolution), user-selected GSD wiring, `--alignment_max_error` correction |
| [v0.10.9](v0.10.9.md) | 2026-05-04 | Geo-registration fix: TIFF GPS EXIF via `getexif()`, remove unsupported `model_aligner` flags, symlink `geo_reference.json` |
| [v0.10.8](v0.10.8.md) | 2026-05-03 | Orthomosaic failure reporting fix, DSM no-CRS guard, direct TIFF band upload |
| [v0.10.7](v0.10.7.md) | 2026-05-03 | Docker volume name pinning, container names, COLMAP vocab tree pre-baked / bind-mount |
| [v0.10.6](v0.10.6.md) | 2026-04-28 | Raw band ortho ZIPs — per-band GeoTIFF archives available for download |
| [v0.10.5](v0.10.5.md) | 2026-04-28 | Geotagged calibrated reflectance TIFFs (WGS84 GeoTIFF per image) |
| [v0.10.4](v0.10.4.md) | 2026-04-26 | Geo-registration: geotagged orthomosaic & DSM outputs via `colmap model_aligner` |
| [v0.10.3](v0.10.3.md) | 2026-03-29 | Product upload retry resilience, job cancellation propagation, pipeline concurrency control |
| [v0.10.2](v0.10.2.md) | 2026-03-12 | Healthcheck S3 timeout (3s connect/read) |
| [v0.10.1](v0.10.1.md) | 2026-03-11 | Upload retry, non-blocking uploads, S3 healthcheck diagnostics |
| [v0.10.0](v0.10.0.md) | 2026-03-09 | KPI metrics endpoints, Redis-backed counters, stage timestamps |
| [v0.9.6](v0.9.6.md) | 2026-03-08 | Request ID tracing across all services |
| [v0.9.5](v0.9.5.md) | 2026-03-08 | Parrot manufacturer support, SQS dispatch improvements |
| [v0.9.4](v0.9.4.md) | 2026-03-08 | Fix calibration data not reaching orthomosaic (VI generation) |
| [v0.9.3](v0.9.3.md) | 2026-03-08 | Orthomosaic output path fix (symlink approach) |
| [v0.9.2](v0.9.2.md) | 2026-03-08 | Upload status callback, product metadata extraction |
| [v0.9.1](v0.9.1.md) | 2026-03-07 | Non-blocking uploads, band organizer fix, calibration re-run fix |
| [v0.9.0](v0.9.0.md) | 2026-03-07 | httpx migration, parallel I/O, connection pooling |
| [v0.8.0](v0.8.0.md) | 2026-03-08 | Pipeline benchmarking suite with dataset presets |
| [v0.7.0](v0.7.0.md) | 2026-03-08 | SQS-based job dispatch for autoscaling AI services |
| [v0.6.2](v0.6.2.md) | 2026-03-07 | Health check & metrics endpoints, pipeline metrics recording |
| [v0.6.1](v0.6.1.md) | 2026-03-06 | Upload timeout/retry, upload failure resilience, orthomosaic DNS fix |
| [v0.6.0](v0.6.0.md) | 2026-03-05 | Multispectral analysis pipeline: reflectance, band orthorectification, vegetation indices, analysis_mode |
| [v0.5.0](v0.5.0.md) | 2026-03-05 | Band detection, calibrator refactoring, unittest migration, metadata support |
