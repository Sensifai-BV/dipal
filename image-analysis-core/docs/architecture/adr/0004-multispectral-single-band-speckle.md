# ADR 0004 — Multispectral single-band speckle: DSM-jitter, sensor noise, and super-native sampling

- **Status:** Proposed (plan; no code yet)
- **Date:** 2026-06-15
- **Builds on:** [ADR 0002](0002-multispectral-orthorectification-through-sfm.md) (MS bands
  orthorectified through SFM poses + DSM, shipped v0.10.25) and [ADR 0003](0003-flightline-striping-ppk-vertical-priors.md)
  (residual flight-line DSM striping, deferred).
- **Runs analysed:** run_14_jun (`6e522316-…`, the v0.10.25 pose-ortho run).

---

## 1. Context — what the operator observes

After the pose-ortho fix (v0.10.25) the MS products are correctly placed and the NDVI
is one coherent field. Inspecting an individual **single band** ortho (e.g.
`nir_ortho.tif`, `red_edge_ortho.tif`) over the satellite basemap, the operator sees:

1. **A salt-and-pepper / grainy texture** across the whole field.
2. **Ragged, eroded edges** with detached speckle clumps at the field margins.

The operator asked whether this is caused by GSD / "decreasing the resolution." It is
**not** — coarsening the output GSD averages each pixel over more ground and would make
the band *smoother*, not grainier. The graininess has three distinct sources, surfaced
(not created) by the output grid being finer than the MS sensor can resolve.

This ADR documents the root cause and the remedies; it is **cosmetic for the analysis
products** (see §4) and therefore lower priority than ADR 0003.

---

## 2. Evidence (measured on the v0.10.25 run)

- All MS products share the **identical** UTM grid as the RGB ortho and DSM (EPSG:32634,
  0.05 m px, same extent) — so this is **not** misalignment; it is per-pixel noise
  texture on a correctly-registered raster.
- Single-band high-frequency (gradient) energy is materially higher than the NDVI built
  from the same bands: on run_13_jun_4th the plateau-feather blend measured NIR HF ≈
  0.0177 vs NDVI HF ≈ 0.0555 in absolute terms, but the **band-to-band** texture that
  drives the speckle largely **cancels in the ratio** (RED↔NIR HF correlation ≈ 0.13:
  positive, i.e. the two bands carry the *same* crop-row/jitter texture, which divides
  out of NDVI).
- The MS sensor's **native GSD is coarser** than the 0.05 m RGB-derived output grid
  (the DJI M3M multispectral camera is lower-resolution than its RGB camera). Bands are
  therefore **upsampled** onto the output grid.

---

## 3. Root cause

The single-band speckle is the sum of three contributors, in roughly descending order:

### 3.1 DSM micro-roughness → inverse-projection sampling jitter (dominant)

`pose_ortho.orthorectify_bands_pose` finds each output cell's band value by projecting
its ground point `(E, N, Z)` through the RGB camera, where **`Z` is read from the dense
DSM**. The dense-MVS DSM over a low-texture field carries a few cm of per-cell height
noise. That `Z` wobble shifts the projected sensor pixel by a fraction of a pixel — up to
~1 px — between neighbouring cells, so adjacent cells bilinearly sample slightly
different spots in the band image → salt-and-pepper. This is the characteristic failure
mode of inverse-projection orthorectification driven by a noisy surface.

### 3.2 Genuine MS sensor noise amplified by the display stretch

The single bands carry low reflectance values (≈0.002–0.03 for red/red-edge). QGIS (and
any viewer) stretches that narrow range across the full grayscale ramp, so real sensor
shot/read noise fills the visible range. The same data viewed with a fixed wide range
looks far flatter.

### 3.3 Super-native sampling (the kernel of truth in the GSD question)

Because the output grid (0.05 m) is **finer than the MS native GSD**, the projection
upsamples the band. Upsampling does not add noise, but it **exposes** the §3.1 jitter and
the MS pixel structure at sub-MS-pixel scale, so both read as grain. Coarsening the grid
toward the native MS GSD suppresses this; it does not cause it.

### 3.4 Ragged edges (separate, coverage-driven)

The output is clipped to the real (unfilled) dense-cloud coverage, then eroded. At field
margins the cloud is sparse (low forward/side overlap there), so coverage fragments into
ragged edges and detached clumps. This is reconstruction density at the perimeter, not a
GSD or blending defect.

---

## 4. Why this is cosmetic for the deliverables

The speckle lives in the **single bands**. The vegetation indices (NDVI, NDRE, GNDVI)
are **ratios of two bands that share the same pose, DSM, blend weight, and jitter**, so
the per-pixel texture in §3.1–§3.3 **largely cancels** — which is exactly why the NDVI is
coherent while a lone band is grainy. The operator's analysis products are therefore not
materially affected. The single-band exports are the ones that look noisy.

---

## 5. Decision — remedies (opt-in, ordered by cost/benefit)

Address the *source* where cheap, and smooth the *symptom* otherwise. Each is gated and
defaults off so current behaviour is preserved.

| # | Remedy | Targets | Cost | Notes |
|---|---|---|---|---|
| A | **Light per-band smoothing** (small median or Gaussian, e.g. 3×3) applied to each band ortho after projection | §3.1, §3.2 | tiny | Cheapest, most effective for single-band appearance; median preserves edges and kills salt-and-pepper. Apply to bands only; recompute indices from smoothed bands or leave indices unchanged. |
| B | **Project/export bands at ~native MS GSD** (coarser output for the MS layer), optionally upsampled for display only | §3.3, §3.1 | low | Stops super-native upsampling; one MS pixel ≈ one ground sample. Keeps RGB/DSM at fine GSD. |
| C | **Smooth/regularise the DSM `Z` used for MS projection** (light low-pass on the surface fed to the inverse projection) | §3.1 (at source) | medium | Crops are near-planar, so a lightly smoothed surface barely changes geometry but removes the jitter at its origin. Does not alter the published DSM. |
| D | **Wider blend feather / more captures averaged per cell** (`_FEATHER_FRAC`) | §3.1, §3.2 | tiny | More views per cell → more noise averaging; trade-off is mild loss of nadir sharpness. |
| E | **Larger coverage erosion / minimum-overlap threshold** for the paint mask | §3.4 | tiny | Trims ragged margins (cosmetic); or accept margins as the true coverage limit. |

**Recommended default:** **A (light median smoothing of single bands)** as the primary
fix — it is one cheap operation that resolves the dominant visual complaint — with **C
(DSM regularisation for the projection)** as the principled deeper fix if smoothing is
judged to soften real detail. **B** is the correct long-term posture (don't claim
resolution the MS sensor doesn't have) and pairs naturally with the future quality-preset
work in `docs/plan-for-future-developments/operator-facing-parameters.md`. Indices remain
unchanged regardless (they already cancel the texture).

**Explicitly rejected:** "lower the output resolution to fix grain." Coarsening the whole
output GSD would smooth the grain but also throw away the genuine RGB/DSM detail; the
targeted remedies above achieve the smoothing without that cost.

---

## 6. Consequences

- Smoothing (A/D) trades a small amount of true high-frequency band detail for a much
  cleaner single-band appearance; because indices already cancel the texture, index
  fidelity is unaffected.
- B changes the MS band raster resolution, which downstream consumers must tolerate
  (the bands would no longer be pixel-identical in size to the RGB ortho; they remain
  co-registered in CRS/extent).
- C touches only the surface fed to MS projection, not the published `dsm_filled.tif`.
- All remedies are opt-in flags; default behaviour is byte-for-byte unchanged.

---

## 7. Validation plan

1. Quantify single-band HF energy before/after each remedy (gradient-magnitude mean over
   the valid mask), targeting a visible reduction without flattening crop-row structure.
2. Confirm **NDVI/NDRE/GNDVI are unchanged** (or improved) — the indices must not regress.
3. Confirm RED↔NIR HF correlation stays positive (bands remain co-registered).
4. Visual check over the basemap: grain gone, crop rows still legible, edges acceptable.

---

## 8. Relationship to other ADRs

- [ADR 0002](0002-multispectral-orthorectification-through-sfm.md): this speckle is a
  property of the inverse-projection path that ADR 0002 introduced; it does not change
  that decision.
- [ADR 0003](0003-flightline-striping-ppk-vertical-priors.md): both ADR 0003 (DSM
  striping) and this ADR's §3.1 trace to DSM quality; a better-regularised / PPK-improved
  surface would reduce both, so the two are complementary.
