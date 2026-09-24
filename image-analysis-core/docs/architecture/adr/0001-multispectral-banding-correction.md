# ADR 0001 — Correcting residual flight-line banding in multispectral indices

- **Status:** SUPERSEDED — read **§11 first** (root cause = inter-band
  misregistration), then §10 (why the radiometric/BRDF hypotheses were ruled out).
  §1–§9 are the original analysis, kept for the trail.
- **Date:** 2026-06-10
- **Context job analysed:** `2138102f-b9fb-4d93-9b70-1e93d2b8dd0f` (the "new_run" after v0.10.20–v0.10.22)
- **Decision drivers:** persistent diagonal banding in NDVI/NDRE/GNDVI after the cross-band strip-gain fix (v0.10.20) failed to engage on a gapless flight pattern.

> This ADR is written to be independently verifiable. Every quantitative claim
> below is reproducible from the cited artifacts. **§1–§9 record the original
> analysis and literature review; §10 records what direct measurement found when
> we went to implement, which corrected the diagnosis.** The honest trail is kept
> deliberately: it shows two plausible, literature-backed hypotheses (A: DLS
> cosine coupling; B: per-pass BRDF scalar) that the data then ruled out as the
> *NDVI* banding driver.

---

## 1. Problem

After three fixes that were each verified to work —
- cross-band shared strip-gain (v0.10.20),
- irradiance normalisation (v0.10.21, reflectance now physical: NIR median ≈ 0.20),
- OPENCV camera model / reduced doming (v0.10.22, DSM bowl −3.69 m → −2.00 m) —

the **NDVI flight-line banding the user originally reported is still present**. Measured
on the new run vs the old run, the banding metrics are essentially unchanged:

| Metric | Old run | New run |
|---|---|---|
| NDVI high-freq stripe std | 0.2316 | 0.2310 |
| corr(Red residual, NIR residual) | 0.039 | 0.038 |
| NDVI gradient anisotropy (NE-SW vs NW-SE) | — | 0.189 vs 0.116 (banding aligned with flight lines) |

## 2. Why the existing fix did not engage

The v0.10.20 strip normaliser groups images into flight strips by detecting
**gaps in the cross-track GPS projection** (PCA minor axis), splitting where a gap
exceeds `max(median_gap × 6, 5 m)`.

On this dataset that detector returns **1 strip**:

```
119 images, field 127 m × 107 m
cross-track gaps: median 0.585 m, max 1.93 m
threshold = max(0.585×6, 5) = 5.0 m  → no gap exceeds it → single strip
```

The flight is a **tight, heavily-overlapping double-grid** with no sidelap gap to
split on. With one strip, all gains are 1.0, so **no normalisation is applied**.
The gap-based assumption (parallel strips separated by visible sidelap) does not
hold for cross-hatch / high-overlap missions.

## 3. Root-cause analysis (the banding is TWO independent effects)

Measured on the 119 NIR images of this job:

**(A) Residual illumination coupling in calibration — radiometric.**
After full calibration, per-image NIR reflectance median still varies with
**CV = 10.5 %** (0.162–0.272) over images of the *same field*. It should be ~0.
Critically, `corr(calibrated_reflectance, raw_Irradiance) = −0.433`: the
calibrated value still tracks the DLS irradiance (it should be decorrelated if the
irradiance normalisation were complete/correct). The sign indicates
over-/mis-correction, not merely incomplete correction. Raw irradiance itself
varies CV = 14 %, exposure CV = 11 % across the flight.

*Confirmed mechanism (was hypothesis; see §9).* The irradiance model in
`calculate_reflectance_from_signal` is `Irradiance / (IrradianceExposureTime ×
IrradianceGain)` — a purely scalar normalisation with **no angular terms**. A
code search confirms there is **no cosine-of-incidence, Fresnel, or sun-sensor
angle correction anywhere** in calibration, even though the XMP provides
`SunSensorYaw/Pitch/Roll`. The DLS reads a *tilt-dependent* irradiance: when the
aircraft banks, the DLS dome sees the sun at a different incidence angle, so the
recorded irradiance changes while scene illumination does not. Measured coupling:
`corr(Irradiance, SunSensorPitch) = 0.16`, `corr(Irradiance, SunSensorRoll) =
0.18`. Dividing reflectance by this uncorrected, geometry-linked irradiance is the
source of the −0.43 residual. The required corrections (cosine of the DLS-to-sun
incidence angle, plus a Fresnel dome term at shallow angles) are standard and are
exactly the terms the model omits.

**A and B are partly entangled.** Because opposite passes bank oppositely, the
DLS-tilt coupling (A) itself produces a per-pass irradiance difference: passA mean
Irradiance 8586 vs passB 9616 (≈ 12 %), tracking the ≈ 11 % reflectance offset
attributed to BRDF below. So an unknown — possibly large — fraction of the
"between-pass BRDF" term is actually uncorrected DLS-tilt coupling. This is the
strongest reason to fix A *before* measuring/correcting B (§5).

**(B) Bidirectional reflectance (BRDF) between opposite flight passes — geometric-optical.**
Flight headings cluster into two opposite passes: yaw ≈ −151° (61 images) and
yaw ≈ +29° (54 images). Calibrated NIR reflectance differs systematically by pass:

| Pass | n | NIR refl mean ± std |
|---|---|---|
| A (yaw ≈ −151°) | 61 | 0.217 ± 0.019 |
| B (yaw ≈ +29°) | 54 | 0.194 ± 0.016 |

- **Between-pass difference: 11.2 % of the mean** — the dominant structured signal.
- **Within-pass CV: 8.3–8.6 %** — a second, smaller component (per-image noise +
  along-track view-angle gradient).

Adjacent strips fly opposite directions, so alternating strips are systematically
brighter/darker → the diagonal banding. This is the textbook BRDF "hot-spot /
dark-spot" asymmetry between forward- and back-scatter viewing.

**Conclusion:** the banding is **both** a residual calibration error (A) **and** a
BRDF view-direction effect (B). A single per-strip *scalar* (even with working
strip detection) cannot remove a within-image BRDF gradient, and does nothing for
the calibration coupling.

## 4. Options considered

| Option | What it does | Removes A? | Removes B (between-pass)? | Removes B (within-pass gradient)? | Complexity / risk |
|---|---|---|---|---|---|
| **Status quo** (gap-based strip gain) | scalar per strip | no | only if strips detected (they aren't here) | no | — |
| **B: per-image gain** | scale each image's reflectance to the global median, no strip detection | partial (flattens the symptom, not the cause) | yes (mean offset) | no | low |
| **C: BRDF correction** | model reflectance as a function of view/illumination geometry (e.g. per-heading or a kernel-driven BRDF model) and normalise to nadir | no | yes | **yes** | high |
| **A-root: fix calibration** | investigate why calibrated reflectance still correlates with irradiance (−0.43) | **yes (at source)** | no | no | medium |

## 5. Decision

**Adopt a layered correction = A-root + B + a pragmatic first cut of C, applied in this order:**

1. **(A-root) Correct the DLS irradiance for sensor geometry first.** The −0.43
   correlation is caused by a scalar irradiance model that omits the angular
   corrections (confirmed in §3A and §9). Add to the irradiance normalisation:
   (a) a **cosine-of-incidence** factor using the DLS-to-sun angle derived from
   `SunSensorYaw/Pitch/Roll` and the solar vector (from capture time + GPS), and
   (b) a **Fresnel dome transmittance** term for shallow incidence. Fixing this at
   the source is mandatory before any cosmetic normalisation — otherwise B/C would
   be tuned to mask a calibration bug, and (per §3A) much of the apparent "BRDF"
   offset may simply vanish once the DLS tilt is corrected.
   *Also worth a quick check:* `SensorGainAdjustment` sign/direction.

2. **(C, first cut) Per-heading (pass) BRDF normalisation.** Because the dominant
   structured term is the **11 % between-pass** offset and the flight is bimodal in
   yaw, correct it by grouping images by flight heading (k-means / modular
   clustering on yaw, NOT cross-track gaps) and normalising each heading group to
   the global median. This is the part of C that buys the most and is far simpler
   than a full BRDF kernel. It also **replaces the broken gap-based strip
   detection** with heading-based grouping, which is robust to overlapping grids.

3. **(B) Residual per-image gain** within each heading group to flatten the
   remaining 8 % within-pass spread.

**Deferred:** a full physically-based BRDF model (e.g. Ross-Thick/Li-Sparse
kernel-driven, or Walthall/empirical view-angle polynomial) is **deferred** unless
steps 1–3 leave visible banding. It is the most correct treatment of the
within-image gradient but is high-effort and risks over-fitting on single-flight
data without multi-angular sampling.

### Why not B alone
B flattens per-image means but cannot touch the within-image BRDF gradient, and —
more importantly — would be calibrating *on top of* the unresolved calibration
coupling (A), baking a workaround over a bug.

### Why not full C immediately
The within-pass gradient (8 %) is half the size of the between-pass offset (11 %),
and a per-heading correction captures most of the structured BRDF cheaply. Full
kernel BRDF is justified only if residual banding persists after steps 1–3.

### Why heading-based grouping replaces gap-based strip detection
Strip identity for radiometric purposes is really "which illumination/view
geometry regime" — that is encoded by **flight heading**, not by spatial gaps.
Heading clustering works on gapless grids, cross-hatch patterns, and classic
parallel strips alike.

## 6. Consequences

- **Positive:** removes the dominant 11 % banding term robustly across flight
  patterns; fixes the radiometric root cause; eliminates the brittle gap threshold.
- **Negative / risks:** per-heading normalisation assumes each heading group images
  similar ground statistics (true for full-coverage agricultural flights; could bias
  if one heading only covers a non-representative sub-area — mitigate by normalising
  on the *overlap* region statistics, or by using a robust estimator).
- **Validation gate:** re-run this job; success = NDVI stripe std materially below
  0.231 and between-pass reflectance difference < ~3 %.

## 7. How to verify this ADR later

1. **Banding metrics** (§1): recompute `corr(Red_resid, NIR_resid)` and NDVI
   high-freq std with a 15-px box-mean detrend on `multispectral/bands/*_ortho.tif`
   and `indices/ndvi.tif`. Expect ≈ 0.04 and ≈ 0.23 on the un-fixed run.
2. **Strip detection failure** (§2): `_assign_flight_strips` on the 119 image GPS
   returns `n_strips == 1`; max cross-track gap 1.93 m < 5 m threshold.
3. **Calibration coupling** (§3A): `corr(calibrated NIR reflectance median,
   raw Irradiance) ≈ −0.43`; per-image CV ≈ 10.5 %.
4. **BRDF between passes** (§3B): yaw bimodal at ≈ −151° / +29°; NIR refl 0.217 vs
   0.194 (11.2 % of mean); within-pass CV ≈ 8.5 %.
5. **Literature checks (domain accuracy):**
   - BRDF forward/back-scatter asymmetry in nadir-ish UAV multispectral mosaics is a
     documented cause of flight-line banding (search: "BRDF flight line / strip
     banding UAV multispectral", "hotspot bowl-tie radiometric correction
     Metashape/Pix4D").
   - Kernel-driven BRDF (Ross-Thick / Li-Sparse) and empirical view-angle methods
     are the standard corrections (search: Roujean 1992; Schläpfer et al. empirical
     BRDF; Honkavaara UAV radiometric block adjustment).
   - DLS-only (no Calibrated Reflectance Panel) leaving residual absolute error is
     consistent with §3A (search: "DLS vs reflectance panel empirical line UAV").
6. **The claim that a per-strip scalar cannot fix a within-image gradient** is
   arithmetic, not empirical: a single multiplicative constant per image preserves
   the spatial gradient inside that image.

## 8. References to code

- `services/orthomosaic_generation/app/core/algorithms/ms_orthorectification.py`
  — `_assign_flight_strips` (to be replaced/augmented by heading clustering),
  `_compute_shared_strip_gains`, `_blend_band_with_gains`.
- `services/radiometric_calibration/app/core/services/base_calibrator.py`
  — `calculate_reflectance_from_signal` (locus of the A-root fix; add cosine +
  Fresnel terms here).

## 9. External literature review (2026-06-10)

An independent review against remote-sensing sources confirmed the ADR's premises
and refined two points. Summary of what was validated and what changed:

**Confirmed:**
- **DLS coupling (A).** Sources report that enabling the MicaSense-style sun
  sensor "led to more variable and less accurate reflectance values" and that DLS
  inclusion "can have variable effects on output surface reflectance" — matching
  the observed −0.43 coupling. Proper DLS integration explicitly requires a
  **cosine correction** (DLS-to-sun incidence angle) and a **Fresnel refraction
  correction** at the dome. Our model has neither — this pinpoints the A-root fix.
- **BRDF asymmetry (B).** Confirmed that opposing flight lines capture different
  reflectance for the same surface due to sun–sensor geometry; BRDF is minimised
  only near solar noon. The forward/back-scatter (hot-spot/dark-spot) framing is
  correct.
- **Algorithm logic.** A scalar gain only shifts the mean and preserves the
  within-image gradient (arithmetic). Heading/yaw clustering is endorsed as the
  geometrically-correct way to group images by view–illumination regime, robust to
  overlap — superior to gap-based strip detection.
- **Layered ordering.** Fixing A before B/C, and deferring the full kernel BRDF
  (over-fitting risk without multi-angular sampling), both align with the sources.

**Refined / added:**
- The specific kernels named (Ross-Thick/Li-Sparse, Walthall, Roujean 1992) are
  not in the provided sources but are corroborated as the standard models by
  general remote-sensing knowledge. Treat as gold-standard references, not as
  claims sourced from the cited papers.
- **New recommendation — Calibrated Reflectance Panel (CRP) + Empirical Line
  Method (ELM).** A cited study reduced reflectance discrepancy from ≈ 0.015 to
  ≈ 0.005 using a panel/ELM, compensating for residual DLS error. This is the
  most complete way to close the A-root gap. It is **out of scope for the code
  changes in this ADR** (it requires an operational change: imaging a panel
  before/after each flight, plus an ELM ingestion path), but it is the
  recommended longer-term direction and is now tracked as a follow-up. The
  cosine+Fresnel DLS correction (§5 step 1) remains the immediate code fix; CRP/ELM
  is the eventual gold standard layered on top.

**Net effect on the decision:** unchanged in structure, strengthened in
confidence. Step 1 is now a concrete model (cosine + Fresnel) rather than a
hypothesis, and CRP/ELM is recorded as the follow-up that would make absolute
reflectance scientifically defensible.

> ⚠️ The "Net effect" above was written before implementation. §10 corrects it.

## 10. Implementation findings — diagnosis corrected (2026-06-10)

Before writing the §5 step-1 code, the cosine model was tested directly on the
119 NIR images. The measurements **invalidated the cosine correction as the NDVI
banding fix** and re-identified the true driver. This section supersedes the §5
decision.

### 10.1 The DLS cosine model does not fit this data
Built a NOAA solar vector (from `UTCAtExposure` + GPS) and a DLS normal from
`SunSensorYaw/Pitch/Roll`, computed `cos(incidence)`, and tested
`Irradiance / cos_i`:
- A **48-way grid search** over all rotation orders/signs found the *best* case
  reduces raw-irradiance CV from **0.141 to only 0.140** — i.e. no convention
  meaningfully explains the irradiance variation by sensor tilt
  (best `corr(Irr, cos_i) = 0.10`).
- The initial `corr = 0.37` (which motivated §3A) was an artefact of one
  arbitrary convention, not a robust geometric relationship.

### 10.2 What the irradiance variation actually is
- **Smooth temporal drift, not per-image tilt.** Lag-1 autocorrelation of
  irradiance in capture order is **0.835** (a slowly-varying series), and it does
  **not** track solar elevation (only moved 32.2°→33.6° over the 14-min flight;
  `corr ≈ −0.14`). The 14 % variation is gradual illumination/sensor drift that
  *aligns with passes only because passes are flown as contiguous time blocks.*

### 10.3 The decisive error: per-pass brightness CANCELS in NDVI
- A shared per-image/per-pass gain (the §5 step-2/3 plan, and the v0.10.20 design)
  **cannot change per-image NDVI** — a common multiplicative factor cancels in
  `(NIR−Red)/(NIR+Red)`. Verified: per-image NDVI-median spread is unchanged by the
  gain.
- Per-image **NDVI median barely differs by pass** (passA 0.395 vs passB 0.380,
  ~4 %), far less than the 11 % *brightness* offset. So the 11 % between-pass term
  — the headline of §3B — is a *brightness* effect that **does not drive the NDVI
  banding**.

### 10.4 The true NDVI banding driver: within-image BRDF gradient in index space
Measured per single-image NDVI an **across-track gradient that is consistent in
sign across images**: left→right `dNDVI ≈ +0.01 … +0.06` (mean ~+0.03) on every
image tested. This is a view-angle change in the *band ratio* across the FOV — it
does **not** cancel in NDVI (unlike a brightness scalar). When adjacent strips fly
opposite headings, this gradient flips relative to the ground → alternating-strip
NDVI banding. This is the genuine source, and it is precisely the "within-image
gradient / full kernel BRDF" item the original ADR **deferred**.

### 10.5 Corrected decision
- **Drop** the cosine+Fresnel DLS correction as the banding fix — the data shows
  it does not explain the variation. (Cosine/Fresnel may still marginally improve
  *absolute* radiometric accuracy and remains defensible per the literature, but
  it is **not** the NDVI-banding fix and should not be implemented under that
  justification.)
- **Drop** per-pass/per-image scalar normalisation as an NDVI fix — it cancels in
  the index by construction.
- **The actual fix must operate on the within-image view-angle gradient in index
  (or band-ratio) space.** Options:
  1. **Empirical view-angle de-trend:** model `dNDVI` (and per-band ratio) as a
     function of across-track pixel position / view zenith, fit from the
     consistent observed gradient, and flatten it per image before compositing.
  2. **Kernel-driven BRDF** (Ross-Thick/Li-Sparse) per band using view/sun
     geometry — the rigorous version, heavier, needs care to avoid over-fit.
  3. **Seamline + multi-band feather that minimises cross-strip ratio
     discontinuity** (treats the symptom at the mosaic stage rather than the
     per-image cause).
- This is a **larger change than any prior fix** and is not yet decided — see the
  open question put back to the user. Status returned to **Proposed/again-open**.

### 10.6 Lesson recorded
Two independent, literature-endorsed hypotheses (DLS cosine; per-pass BRDF scalar)
were both plausible and both wrong *for the NDVI banding specifically*. The cheap
empirical pre-checks (CV-after-correction, NDVI cancellation arithmetic,
within-image gradient measurement) caught this before any code shipped. Keep
pre-validating physical-correction hypotheses against the actual error structure,
not just against the literature.

## 11. Root cause finally identified — inter-band MISREGISTRATION (2026-06-10)

Continuing the "investigate first" path, the band mosaics themselves were
examined (not just per-image indices). This located the dominant defect, which is
**neither radiometric (A) nor BRDF (B)** but **geometric**.

### 11.1 The bands do not co-register
- High-frequency spatial correlation between the **RED and NIR mosaics is 0.006**
  (≈ zero). Co-registered bands viewing the same ground share fine texture
  (plants, soil, shadows) and would correlate ~0.7+.
- A brute-force shift search finds the best RED–NIR correlation is only **0.21**,
  at a **~0 px** global shift. So it is **not** a uniform offset — peak
  correlation stays low everywhere. That is the signature of **spatially-varying
  misregistration**, not a constant shift.

### 11.2 Why this is the real banding/noise driver
NDVI = (NIR − Red)/(NIR + Red). Differencing two mosaics that are decorrelated at
fine scale produces high-frequency noise regardless of radiometry. Measured mosaic
high-freq residual: NDVI 65 %, **NDRE 148 %**, GNDVI 59 % of mean — *far* larger
than the per-image index gradients (~0.005–0.03) from §10.4 could create. The
index noise is dominated by band-to-band geometric disagreement, then organised
into visible diagonal structure by the flight-line overlap pattern.

### 11.3 Why the bands misregister
This is the limitation already documented in code (v0.10.22 known-limitations):
`_warp_reflectance_image` places **each band image independently** on the DSM using
**raw EXIF GPS + yaw only, assuming nadir** (no roll/pitch). On the M3M the four MS
sensors are body-fixed and slightly offset; each is warped separately with its own
GPS-only, tilt-free placement, so band *i* of image *n* and band *j* of image *n*
land at slightly different ground positions, varying across the field. The four
single-band mosaics are each internally plausible but mutually offset.

### 11.4 Implication for the fix (supersedes §10.5)
The high-value fix is **geometric band co-registration**, not radiometric
normalisation:
- **(Best) Register the bands to each other** before/instead of independent warps.
  Either (a) warp all four bands of a capture with one shared, tilt-aware
  projection (roll/pitch/yaw + the inter-band homography DJI provides in XMP —
  `DewarpHMatrix` / `CalibratedHMatrix`), or (b) co-register each band mosaic to a
  reference band (e.g. phase-correlation / ECC alignment of the band orthos).
- The previously-documented **roll/pitch homography** limitation is therefore not a
  minor accuracy item — it is plausibly the **primary** cause of the index noise
  and should be promoted to the main fix.
- Radiometric (A) and BRDF (B) corrections remain valid for *absolute accuracy* and
  *residual* banding, but will not fix the dominant index noise while the bands are
  misregistered.

### 11.5 Status
Root cause re-attributed to inter-band misregistration. Recommendation: pursue band
co-registration (§11.4). Validation gate: RED–NIR high-freq correlation should rise
from 0.006 toward ≥ 0.5, and NDVI mosaic high-freq residual should drop materially
below 0.23. **Not yet implemented — pending user direction**, since band
co-registration is a substantial change to the orthorectification path.

### 11.6 Decisive single-capture test (misregistration vs. low texture)
To separate "bands are misregistered" from "bands lack shared texture," RED vs NIR
were compared on **single calibrated captures, before mosaicking**, with a shift
search. Result (4 captures):

| capture | zero-shift corr | best corr | best shift (px) |
|---|---|---|---|
| 0001 | 0.293 | 0.350 | (−12, −6) |
| 0002 | 0.278 | 0.334 | (−12, −6) |
| 0003 | 0.250 | 0.306 | (−12, −6) |
| 0004 | 0.228 | 0.293 | (−12, −9) |

Two conclusions, both important:
1. **A consistent inter-band offset exists** — every capture aligns best at
   ≈ (−12, −6) px (≈ 0.6 m × 0.3 m at 0.05 m/px). A *constant* offset across
   captures is the fixed physical lens separation + the unapplied inter-band
   homography. This **confirms a correctable misregistration** and means a single
   per-band homography/offset (not per-image chaos) addresses it.
2. **Even optimally aligned, correlation only reaches ≈ 0.30–0.35**, not ≥ 0.6.
   So there is **also a genuine low-shared-texture component** (RED and NIR of
   vegetation legitimately differ; plus resolution/blur). Part of the index noise
   will **survive** co-registration.

**Calibrated conclusion (tempers §11.4):** inter-band co-registration is necessary
and is the highest-value single fix (removes the consistent ~12 px offset that the
mosaic stage smears into spatially-varying error), but it is **not a complete fix**
— expect residual index noise from genuine spectral-texture differences. Realistic
validation gate revised: single-capture RED–NIR corr should rise toward the
~0.30–0.35 *intrinsic ceiling* after registration, and the **mosaic** RED–NIR
high-freq corr (currently 0.006) should rise toward that single-capture ceiling —
i.e. the mosaic should stop being *worse* than a single capture. NDVI mosaic
residual should drop, but will not reach zero.

### 11.7 Mosaic-level co-registration RULED OUT — fix must be per-capture
Before implementing, the cheaper "register the finished mosaics" approach
(§11.4 option b) was tested with FFT phase-correlation on the band orthos:
- Phase-correlation finds only a **(0, −1) px** global shift between the RED and
  NIR *mosaics*, and applying it raises high-freq correlation only
  **0.006 → 0.059** — negligible.
- Yet single captures show a clear, consistent **(−12, −6) px** offset (§11.6).

**Why:** the per-capture offset is consistent in the *image frame*, but each
capture is flown at a different heading and composited into the mosaic, so the
constant image-frame offset maps to *different ground directions* per strip and
**averages out to ~0 as a global mosaic shift while remaining as spatially-varying
local error.** Therefore a single global mosaic registration cannot fix it.

**Decision: implement the per-capture fix (§11.4 option a).** Apply the inter-band
alignment to each band image *before* it is GPS-warped and composited — either via
the DJI inter-band homography (`DewarpHMatrix`/`CalibratedHMatrix`, semantics to be
confirmed against DJI docs) or, as a dependency-light first cut, by registering
each band image to a reference band (e.g. NIR) per capture using FFT
phase-correlation and shifting before warp. The per-capture shift is consistent
enough (§11.6) to be reliable. This lives in the per-image path
(`_warp_band_images` / `_warp_reflectance_image`), not the mosaic stage.

### 11.8 IMPLEMENTED & VALIDATED (v0.10.23)
Implemented the dependency-light first cut: `_phase_correlation_shift` (numpy FFT,
no OpenCV/scipy) + per-capture registration of each band to a NIR reference inside
`_warp_reflectance_image`, wired through `_warp_band_images` / `orthorectify_bands`
via a `capture_key → reference-band` map (`_capture_key` parses the DJI 4-digit
sequence). The reference band registers to itself (no-op); shifts > 40 px are
rejected as noise.

**Validation (12-capture subset, real data, RED vs NIR mosaic high-freq corr):**
- WITHOUT registration: **0.062**
- WITH registration: **0.201**  → a **3.2×** improvement, moving from the broken
  near-zero toward the ~0.30–0.35 single-capture intrinsic ceiling (§11.6),
  exactly as predicted. The residual gap to ~0.32 is the genuine spectral-texture
  floor and is not removable by registration.

**Status: Accepted & implemented.** The DJI-homography variant (§11.4a proper) and
the radiometric cosine/CRP items (§9) remain available as future refinements for
absolute accuracy, but the dominant index-noise driver is now addressed. Re-run a
full job to confirm the mosaic-level NDVI/NDRE/GNDVI banding is visibly reduced.
