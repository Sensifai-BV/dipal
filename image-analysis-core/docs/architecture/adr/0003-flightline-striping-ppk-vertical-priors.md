# ADR 0003 — Eliminate flight-line DSM striping via per-image PPK priors (+ resolution guidance)

- **Status:** Proposed (plan; no code yet)
- **Date:** 2026-06-13
- **Builds on:** [ADR 0002](0002-multispectral-orthorectification-through-sfm.md) Phase 1 (DSM
  doming fixed in v0.10.24 by seeding/locking factory intrinsics as FULL_OPENCV+k3).
  This ADR addresses the **residual** DSM defect that remained *after* doming was fixed.
- **Jobs analysed:** JOB_2nd_12_JUN (`e08a7ab4-…`, the de-domed v0.10.24 run).

---

## 1. Context — what remains after the doming fix

With doming removed (dome curvature ~4.5 m → 0.21 m), the user inspected the new
`dsm_filled.tif` and observed a residual directional pattern — annotated with arrows
along the flight/row direction — expecting the elevation to reflect the field's real
structure rather than a smooth tilt + faint streaks. Two distinct phenomena were
separated by measurement:

1. **A flight-line striping artifact** (the streaks the arrows trace).
2. **The crop-row micro-topography is largely unresolved** (the pattern the user
   *expected* to see but doesn't).

This ADR addresses both: **PPK per-image priors** for (1), **resolution** for (2).

---

## 2. Evidence (measured on the v0.10.24 DSM)

After removing the real planar ground tilt (a genuine ~3 m slope, 82% of variance):

- Residual std **0.226 m**; fine-scale (high-pass) residual std **0.070 m**.
- **Directional anisotropy 3.4×** at ~125°; **dominant wavelength 15.3 m**, amplitude
  ~0.13–0.155 m; coarse 2–30 m band residual std 0.130 m.
- Flight geometry (from image GPS): heading **61°**, flight-line spacing **~5.4 m** →
  the 15.3 m stripe ≈ every ~3rd line (a fusion beat), squarely in the **flight-strip
  regime**, NOT crop-row spacing (sub-metre). ⇒ **flight-line striping artifact**,
  distinct from the (now-fixed) intrinsic doming.
- Crop rows are sub-metre and vegetated; at 5 cm GSD with ~7–20 cm reconstruction
  noise their elevation signal is at/below the noise floor → **not resolved**.

---

## 3. Root cause — PPK is used only as a *global* post-hoc alignment

Verified in `colmap_service.py`:

- **Reconstruction is visual-only.** GLOMAP runs with
  `glomap_constraint_type = "ONLY_POINTS"` — camera GPS/PPK priors are **ignored
  during global positioning + bundle adjustment**. The relative geometry therefore
  accumulates small **per-strip vertical drift** (each flight line's depth maps fuse
  with a slightly different height bias).
- **PPK is applied only afterwards, globally.** `_parse_mrk_file` +
  `_upgrade_gps_with_ppk` produce cm-level positions, but they are consumed in
  `geo_register()` to build `ref_images.txt` for `model_aligner`, which fits a single
  **7-parameter similarity transform** (3 translation + 3 rotation + 1 scale) to the
  whole block. A global similarity **cannot correct per-strip biases** — it rotates/
  scales/shifts the entire cloud rigidly, so the relative inter-strip wobble survives.
- `mapper_use_prior_position=True` / `prior_position_loss_scale=15.0` exist, but with
  `ONLY_POINTS` the priors do not enter the objective (and the stored priors are
  lat/lon/alt, degenerate for GLOMAP's metric solver — see the in-code comment).

> So the cm-accurate PPK heights we already have are **never used to constrain
> individual camera elevations during reconstruction** — only to place the finished
> block. That is exactly the gap that leaves ~13 cm flight-aligned stripes.

---

## 4. Decision — feed PPK as per-image position priors *during* bundle adjustment

Use the PPK `.MRK` positions as **per-image camera-centre priors inside the
reconstruction/BA**, in a **metric (ECEF) frame**, with **anisotropic weights**, so
each camera's elevation is pinned to cm-level truth and per-strip vertical drift cannot
form. This is the principled, data-available fix (we already parse the PPK).

### 4.1 Mechanics

1. **Convert PPK lat/lon/ellh → ECEF** (EPSG:4326→4978) and store as each image's
   `prior_t` (the metric position GLOMAP/COLMAP expect). Reuse `_parse_mrk_file` /
   `_upgrade_gps_with_ppk`; add the geographic→ECEF step and write `prior_t` (ECEF)
   into the database `pose_priors`.
2. **Enable camera priors in the solver.** Set
   `glomap_constraint_type = "POINTS_AND_CAMERAS_BALANCED"` (visual + camera priors;
   valid now that `prior_t` is ECEF/metric, resolving the degeneracy the current
   `ONLY_POINTS` default works around). Keep intrinsics fixed (ADR 0002 / v0.10.24).

   > **The constraint type is NOT a standalone operator toggle — it is code-coupled
   > to PPK availability and frame.** Flipping `COLMAP_GLOMAP_CONSTRAINT_TYPE` to
   > `POINTS_AND_CAMERAS_BALANCED` *without* the ECEF-prior conversion (step 1) feeds
   > GLOMAP lat/lon/alt priors, which are **degenerate** for its metric solver — it
   > will triangulate ~0 points (the exact failure the in-code `ONLY_POINTS` comment
   > warns about). The implementation must therefore gate the two together: a single
   > operator flag (e.g. `COLMAP_USE_PPK_PRIORS`) writes ECEF `prior_t` **and**
   > selects `POINTS_AND_CAMERAS_BALANCED` internally — mirroring how
   > `COLMAP_SEED_FACTORY_INTRINSICS` auto-disables intrinsic refinement (v0.10.24).
   >
   > **It is also data/drone-dependent.** Tight camera priors are only correct when
   > the positions are cm-accurate (RTK/PPK). For a drone with consumer GPS
   > (~3–5 m), tightly constraining BA to noisy positions would *introduce* error —
   > those datasets should stay `ONLY_POINTS`. So the right behaviour is
   > **auto-detection**: PPK/RTK present + accurate → camera priors; otherwise →
   > visual-only. Not a fixed value to ship for all drones (cf. the generic
   > per-sensor design, ADR 0002 D8).
3. **Anisotropic weighting.** Weight each axis by 1/σ² from the per-image MRK/RTK
   std (`RtkStd{Lat,Lon,Hgt}` / MRK std columns). The vertical prior is the one that
   suppresses striping; even a few-cm PPK vertical σ is far tighter than the ~13 cm
   strip drift, so the prior dominates the wobble. (Confirm the MRK std **units**
   before trusting them as metres; set `prior_position_loss_scale` from the real σ
   rather than the current flat 15.0.)
4. **Re-evaluate `geo_register`.** With cameras already ECEF-anchored in BA, the
   post-hoc `model_aligner` step becomes a near-identity check rather than the sole
   georeferencing mechanism (keep it as a guard / for `geo_reference.json`).

### 4.2 Validation gate (measured on the DSM, like ADR 0002)

- Flight-aligned stripe amplitude **0.13 m → < 0.05 m**; the 15 m directional
  anisotropy drops toward isotropic (≈1–1.5×).
- Per-image camera-height residual vs PPK **< a few cm** (BA actually honoured the
  priors).
- The real planar tilt and ~0.2 m micro-relief are preserved (we suppress the
  *artifact*, not real terrain).

---

## 5. Resolution & aspect-ratio parameters (the crop-row detail the user expected)

PPK fixes the *striping*; **resolution** is what would surface the **crop-row
micro-topography** (§2, item 2). Guidance, grounded in the M3M inputs and the
GTX 1080 (8 GB) box this runs on:

### 5.1 Native input geometry — set processing to it, don't invent an aspect ratio
- **RGB (what SFM uses): 5280 × 3956 px, aspect 4:3 (1.334).** MS bands: 2592 × 1944
  (also 4:3).
- COLMAP **always preserves aspect ratio** — `max_image_size` caps the **long edge**
  only and downscales proportionally. There is no separate aspect-ratio knob and none
  is needed; the fix is simply to stop capping below native. The `.env` values of
  1000 / 2048 throw away ~⅔–½ of the linear resolution (≈90 %/75 % of the pixels),
  which is why sub-metre rows wash out. **Target the native 5280**, or a clean integer
  fraction of it (2640 = ½, 3520 = ⅔) to keep resampling clean.

### 5.2 The resolution CHAIN (must stay consistent — see rules/sfm-colmap.md memory)
`feature_extraction → undistort → patch_match → fusion`, with hard rules:
- **undistort == patch_match** (patch-match cannot upsample undistorted images).
- **fusion ≥ patch_match** (else it downsamples the depth maps — detail lost).
- feature_extraction ≥ patch_match (more features help matching; cheap on GPU).

### 5.3 Concrete `.env` recommendation (GTX 1080, 8 GB — VRAM-bound at patch-match)
Patch-match stereo is the VRAM bottleneck. Two viable profiles:

| Setting | Quality profile (recommended) | Memory-safe profile |
|---|---|---|
| `COLMAP_FEATURE_EXTRACTION_MAX_IMAGE_SIZE` | 5280 | 3520 |
| `COLMAP_UNDISTORT_MAX_IMAGE_SIZE` | 3200 | 2560 |
| `COLMAP_PATCH_MATCH_MAX_IMAGE_SIZE` | 3200 *(= undistort)* | 2560 *(= undistort)* |
| `COLMAP_FUSION_MAX_IMAGE_SIZE` | 3520 *(≥ patch_match)* | 2560 |
| `COLMAP_PATCH_MATCH_GEOM_CONSISTENCY` | 0 *(halves VRAM at 3200)* | 1 |

- Going to **patch_match = 5280** (true native dense) likely **OOMs an 8 GB 1080**;
  feasible only with `GEOM_CONSISTENCY=0`, small `PATCH_MATCH_CACHE_SIZE`, and possibly
  windowed processing — try the 3200 profile first and watch `nvidia-smi`.
- `*_CACHE_SIZE` (currently 24) and `fusion_min/max_num_pixels`, `check_num_images`
  are **counts, not resolutions — do not scale them with image size.**

### 5.4 Honest limit
Even at native resolution, **vegetated** crop rows reconstruct poorly (thin, moving
foliage). Expect bare-soil/ridge structure to emerge; dense-canopy rows may stay soft.
Resolution sharpens what is recoverable — it does not beat the canopy-reconstruction
limit.

---

## 6. Alternatives considered

- **Fusion-consistency tuning** (stricter `PATCH_MATCH_GEOM_CONSISTENCY`, more views per
  fused point): cheap, may reduce per-strip bias somewhat; does **not** fix the
  underlying unconstrained reconstruction. Keep as a complementary knob.
- **DSM destriping post-process** (FFT notch / per-strip levelling at the 15 m
  wavelength): cosmetic, fast, but risks removing real terrain at that wavelength and
  doesn't improve the point cloud or ortho geometry. Last resort.
- **Cross-strips + varying altitude** (new flights): the textbook cure for *both*
  residual doming and striping (ADR 0002 §7) — best long-term, not retroactive.
- **GCPs:** would anchor vertical absolutely; not available for this dataset (D7).

---

## 7. Consequences & priority

- **Positive:** removes the flight-line striping at its source using data already on
  disk; tightens absolute vertical accuracy; the resolution bump also sharpens the
  whole DSM/ortho and surfaces recoverable row structure.
- **Cost/risk:** touches the reconstruction constraint path (ONLY_POINTS →
  POINTS_AND_CAMERAS_BALANCED) and the prior frame (lat/lon → ECEF); must be validated
  on a full run. Higher resolution increases SFM/dense runtime and VRAM — tune to the
  1080. Mis-set MRK std units would mis-weight priors (validate units first).
- **Priority (honest):** **low for the multispectral/NDVI goal** — orthorectification
  is near-nadir, so 13 cm of DSM height error → ~1 px (5 cm) of band displacement; it
  does **not** materially affect the vegetation maps. It matters when the **DSM
  elevation is itself a deliverable** (volumetrics, drainage, terrain). Recommend
  sequencing this **after ADR 0002 Phase 2 (MS-through-SFM)** unless the DSM is a
  standalone product.

---

## 8. External validation (2026-06-13)

A photogrammetry-source review confirmed all three pillars:
- **Root cause (§3):** a 7-parameter similarity transform is purely rigid and *cannot
  correct internal relative deformation* between strips; unconstrained visual-only BA
  lets systematic vertical error accumulate (the solver "hallucinates" small elevation
  changes between opposing flight lines to satisfy reprojection). Confirmed.
- **PPK-in-BA fix (§4):** standard GPS is too noisy to constrain a block, but
  carrier-phase differential positioning (PPK/MRK) is **"accurate enough to contribute
  to a block adjustment"**; injecting it as a weighted per-image prior forces the
  solver to respect true exposure-time elevation, preventing the drift. Confirmed —
  and this **resolves the ADR 0002 C5 paradox** (SFM-internal vs PPK-absolute): feeding
  PPK *into* the solver yields internal visual consistency *and* absolute anchoring
  simultaneously, instead of having to choose.
- **Resolution (§5):** the *BAWSeg* study — same DJI P4-Multispectral class, barley
  fields, ~120 m → ~6.35 cm GSD native — found crop-row structure and multi-row weed
  patches **remain spatially resolved at native resolution**; downsampling the long
  edge to 1000–2048 px discards up to ~90 % of pixels and washes the ~0.2 m row relief
  (near the noise floor) into a blurred surface. Confirmed.

## 9. Operator-facing vs auto-detected parameters (product guidance)

Most of these knobs should **not** reach a non-technical operator. Commercial tools
(Pix4D, Agisoft Metashape, DroneDeploy, WebODM) expose a small surface and auto-detect
the rest:
- **Operator sets:** a **quality/resolution preset** (Low/Med/High/Full → the
  `*_max_image_size` chain), the **analysis mode** (RGB vs multispectral), target
  **GSD** (often from EXIF), output **CRS**, and optional **GCPs**.
- **Auto-detected from the data (never operator-set):** camera intrinsics seeding
  (DewarpData present → ADR 0002), **PPK priors + constraint type** (MRK/RTK present +
  accurate → this ADR), distortion model, BA refinement flags, matching thresholds.

⇒ Ship `COLMAP_USE_PPK_PRIORS` and `COLMAP_SEED_FACTORY_INTRINSICS` as
**auto-detect-with-override** (detect the data, let an env var force on/off), and keep
`COLMAP_GLOMAP_CONSTRAINT_TYPE` an *internal* value, not an operator field.

## 10. References
- [ADR 0002](0002-multispectral-orthorectification-through-sfm.md) — doming fix (Phase 1,
  v0.10.24) and MS-through-SFM design (Phase 2).
- *BAWSeg* (DJI P4-Multispectral, barley, native-GSD crop-row resolvability); carrier-
  phase block-adjustment contribution (supplied source, 2026-06-13).
- Doming/striping literature: nadir single-altitude blocks need GPS/INS priors or
  cross-strips to constrain weak vertical (same family as the doming report, ADR 0002 §2.10).
- Code touch-points: `colmap_service.py` — `_parse_mrk_file`, `_upgrade_gps_with_ppk`,
  `compute_reconstruct` (constraint_type), `geo_register`; resolution settings
  `*_max_image_size`.
