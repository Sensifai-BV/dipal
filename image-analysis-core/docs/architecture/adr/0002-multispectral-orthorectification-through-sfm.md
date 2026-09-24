# ADR 0002 — Multispectral orthorectification must go through SFM (not GPS direct-georeferencing)

- **Status:** Accepted (design finalised — Option B with manufacturer-defined MS→RGB
  model, §3.5; build order de-dome→project, §4). No code yet — implementation is the
  next step.
- **Date:** 2026-06-11 (design verified & finalised 2026-06-12)
- **Supersedes the dominant-cause claim of:** [ADR 0001](0001-multispectral-banding-correction.md)
  §11.8. ADR 0001 correctly identified *inter-band* misregistration and fixed it
  (v0.10.23), but treated that as "the dominant index-noise driver." Inspection of
  the JOB_11_JUN full run shows a larger, upstream defect that ADR 0001 did not
  address: the multispectral products are not built from the SFM reconstruction at
  all. This ADR documents that root cause and the plan to fix it.
- **Job analysed:** `7f548bca-9ee2-462f-b332-358a82ec1121` (JOB_11_JUN), 119
  captures, DJI M3M, near Sidirokastro GR (lat 41.1296, lon 23.4275, UTM 34N /
  EPSG:32634).

---

## 1. Context — what the user observed

On the v0.10.23 full run, three independent visual problems were reported and then
reproduced against the data:

1. **NDVI / single-band orthos look like "a puzzle whose pieces are placed in the
   wrong locations."** Circled regions in QGIS show individual image footprints
   that do not line up with their neighbours — sawtooth strip edges, duplicated /
   offset ground features. All four single bands show the *same* puzzle pattern.
2. **DSM elevation distribution "looks wrong."** The magnitude (~70–74 m) is
   plausible but the spatial pattern is not the expected field relief.
3. **Point cloud position uncertain in MeshLab.** Coordinates read in the millions;
   the ground renders tilted; no easy way to confirm geospatial correctness.

The user also asked the decisive architectural question:

> *"If multispectral are a different resolution than RGB — and for any drone this
> is similar — shouldn't we pass one of the bands through the SFM stage too?"*

This ADR's conclusion is: **yes — and not doing so is the root cause of (1).**

---

## 2. Investigation (all measured on JOB_11_JUN, not assumed)

### 2.1 The pipeline is asymmetric: RGB uses SFM, multispectral does not

| Product | Build method | Uses SFM poses / 3D? | File / function |
|---|---|---|---|
| RGB orthomosaic | Rasterise the dense **point cloud** (`fused_georef.ply`, ECEF) → PDAL reproject → UTM | **Yes** | `orthomosaic_service.generate_rgb_orthomosaic` |
| DSM | Rasterise the same point cloud (`writers.gdal`, `output_type=max`, 0.05 m) | **Yes** | `orthomosaic_service.generate_dsm_from_pointcloud` |
| **MS bands → NDVI/NDRE/GNDVI** | **GPS direct-georeferencing**: drop each band image at its EXIF GPS point, scale by a *guessed* AGL + *guessed* HFOV, rotate by *yaw only* | **No** | `ms_orthorectification._warp_reflectance_image` |

Confirmed by code (`_warp_reflectance_image` reads no `images.bin` / `cameras.bin`,
imports no `pycolmap`) and by logs:
- SFM ingests **only RGB**: `Extracting metadata … images: …/rgb`.
- 595 input images = 119 captures × (1 RGB + 4 MS). Only the 119 RGB enter SFM
  (`num_images: 119, num_reg_images: 119`).

### 2.2 Why this produces the "puzzle pieces"

`_warp_reflectance_image` is direct georeferencing with three compounding
approximations, each documented in its own KNOWN-LIMITATION docstring:

1. **Raw EXIF GPS** per image as the footprint centre — not the PPK/MRK-refined,
   bundle-adjusted camera centre SFM computes. Absolute GPS scatter on the M3M is
   ~1–3 m; each tile is positioned independently, so neighbours disagree by metres.
2. **Nadir assumption** — only `FlightYawDegree` is applied; **roll and pitch are
   ignored**. The M3M's MS sensors are body-fixed (only RGB is gimballed), so they
   tilt with attitude. A ~10° roll at low AGL shifts/skews a footprint by ~2 m.
3. **Guessed scale** — AGL from `RelativeAltitude` (or AMSL − DSM-mean fallback)
   and a per-model HFOV constant give the GSD. Any error scales the whole tile.

None of these are tied together by tie-points or a bundle adjustment, so errors do
**not** cancel between images — each tile lands wherever its own GPS/attitude/scale
estimate puts it. That is precisely a "puzzle with misplaced pieces." The RGB
ortho does not show this because it is reconstructed from one globally-consistent
point cloud.

### 2.3 This reframes ADR 0001

ADR 0001's v0.10.23 fix aligned the **four bands within a single capture** to each
other (phase-correlation to NIR; validated RED–NIR mosaic corr 0.006→0.114). That
is real and worth keeping — but it is a sub-GSD correction sitting on top of a
multi-metre, per-capture placement error. The mosaic RED–NIR correlation stalled
at 0.114 (vs the 0.199 single-capture ceiling, §2.6) precisely because the
**warp/placement stage re-scatters** what registration aligned: per-capture corr is
fine (~0.20), the mosaic loses ~40% of it. ADR 0001 attributed the residual to the
"spectral-texture floor"; the larger contributor is actually 2.2's placement error.

> **Corrected attribution:** inter-band misregistration (ADR 0001) is a *secondary*
> driver. The *dominant* driver of the puzzle-piece geometry is that MS
> orthorectification bypasses SFM and uses GPS+nadir direct georeferencing.

### 2.4 DSM doming — measured

Quadratic-surface fit to `dsm_filled.tif` (valid pixels):
- **89.9 % of elevation variance is a smooth quadratic** (low-order bowl/tilt).
- Real micro-relief residual: **σ ≈ 0.27 m**, vs total swing 70.01→74.46 m.
- Centre higher than all corners (centre 73.05 m; corners 70.80–72.82 m) — the
  classic SFM **doming / bowl** signature, not field terrain.

This is an SFM reconstruction-quality problem (weak model: 93,805 points, mean
track length 3.81, mean reprojection error 0.84 px for 119 images; nadir-only
geometry under-constrains radial self-calibration). It also *feeds* the MS problem:
the AMSL→AGL fallback in 2.2(3) uses the DSM mean, and accurate orthorectification
of any band needs an accurate surface. Doming was partly addressed in v0.10.22
(OPENCV camera model) but clearly persists.

### 2.5 Point cloud is ECEF, not UTM — and PDAL is missing in the SFM container

- `fused_georef.ply` coordinates (X≈4.41e6, Y≈1.91e6, Z≈4.17e6) are **ECEF
  (EPSG:4978)**. Back-transforming the centroid gives lat 41.1295 / lon 23.4274,
  matching `geo_reference.json` (41.1296 / 23.4275) to ~10 m → **geo-registration
  is correct**; the cloud is simply stored in ECEF.
- In MeshLab, ECEF renders the ground **tilted** (Earth-centred axes) and you cannot
  read easting/northing/elevation — this is expected, not an error.
- The v0.10.22 `_write_utm_pointcloud` step that should emit a flat, MeshLab-friendly
  `fused_utm.ply` (E≈703 764, N≈4 555 983, Z=elevation) **failed**: SFM log says
  `PDAL reprojection to UTM failed (non-fatal) … Command not found: pdal`. **PDAL is
  not installed in the SFM container image.**
- The 543 MB `.ply` the user flagged is `meshed-poisson.ply` (the Poisson mesh) —
  normal.

### 2.6 Supporting measurements (carried from the v0.10.23 validation)

- RGB–NIR / band-pair per-capture phase-correlation: red_edge→NIR consistent
  (−20, 3) px, σ(0.3, 0.7); red/green→NIR noisier (σ ≈ 5 px) — low shared texture.
- Per-capture RED–NIR corr ≈ 0.199 (ceiling); mosaic ≈ 0.114 (0.159 plain) → the
  placement/warp stage is where alignment is lost.
- Index residual/mean: NDVI 57 %, NDRE 95 %, GNDVI 49 % (down from 65/148/59 %
  pre-v0.10.23, but still high — consistent with 2.2's placement error dominating).

### 2.7 RGB↔MS capture pairing is unambiguous (enables pose transfer)

DJI M3M fires RGB + 4 MS on one trigger with a shared timestamp **and** 4-digit
sequence. Verified, capture 0050:
`DJI_20240719091600_0050_D.JPG` (RGB) ↔
`DJI_20240719091600_0050_MS_{NIR,R,G,RE}_reflectance.tif`. The
`(timestamp, sequence)` key pairs each MS band to exactly one RGB image whose SFM
pose is known. This makes "pose transfer from RGB" (Option B below) directly
feasible.

Even stronger pairing key found in XMP: RGB and all 4 MS bands of a capture share
the **same `drone-dji:CaptureUUID`** (capture 0050: `47208f04…` on both `_D.JPG`
and `_MS_NIR.TIF`). Use CaptureUUID as the primary join, with (timestamp, sequence)
as fallback.

### 2.8 External technical review — independent confirmation + the two-flaws distinction

A photogrammetry review supplied by the user (2026-06-11) independently reaches the
same conclusion and adds an important precision that changes how Option B must be
implemented:

> *"To map the multispectral images onto an RGB-derived DSM without running SfM on
> them, you must have highly precise exterior orientation data (exact X, Y, Z **plus
> roll, pitch, and yaw**) for the multispectral sensor… standard drone GPS can have
> multi-meter errors, and EXIF data often lacks precise camera attitude… Without
> bundle adjustment… you risk geometric mismatch and 'dislocations and fractures'."*

This validates the decision (RGB-DSM + master-band grouping is "valid and common",
exactly what Metashape does) **and** clarifies that the §2.2 problem is **two
distinct flaws**, not one:

| # | Flaw (in current code) | Naive "fix" that is INSUFFICIENT | Correct fix |
|---|---|---|---|
| 1 | **Attitude:** yaw-only, roll/pitch ignored (nadir) | Read `FlightRoll/PitchDegree` from XMP and add them | full R/P/Y **projected through the DSM**, not a 2-D geotransform |
| 2 | **Position:** raw EXIF GPS centre (multi-metre, no tie-points) | — | **bundle-adjusted camera centre** (= SFM pose), or PPK/MRK-refined centre |

> **Key clarification for the user's question:** reading roll/pitch from EXIF fixes
> flaw 1 but leaves flaw 2 — and the multi-metre GPS position error is the *larger*
> contributor to the puzzle-piece geometry. The real fix is therefore "take the
> exterior orientation from the bundle adjustment", which delivers accurate X,Y,Z
> *and* R,P,Y together, sub-pixel. This is why the fix is "route MS through SFM"
> (Option A) or "transfer the bundle-adjusted RGB pose + model the RGB→MS rotational
> offset" (Option B), **not** "parse two more XMP angles into the existing GPS warp".

The review also flags two items **out of scope for the geometry fix** but recorded
here so they are not lost (future work, see §7): (i) **CRP / Empirical Line Method**
for *absolute* reflectance accuracy (the pipeline uses DLS irradiance only — see
ADR 0001 §9); (ii) **seamline detection + Laplacian/multiband blending** to remove
ghosting/double-mapping of tall objects (current composite is distance-weighted
feathering). Neither is required to fix the puzzle-piece *geometry*.

### 2.9 What the M3M XMP actually provides (measured from the raws)

Read directly from `DJI_20240719091600_0050_*` raws (RGB `_D.JPG` + MS `.TIF`):

- **Drone-body attitude** `FlightRoll/Pitch/YawDegree` is present and **identical on
  RGB and MS** of a capture (e.g. +0.80 / −0.50 / +29.00). Since the MS array is
  body-fixed, this **is** the MS sensor attitude (plus a fixed mount offset). This
  is the clean, physical attitude signal — and it is exactly what the current warp
  discards (yaw only).
- **Gimbal attitude** `GimbalYaw/Pitch/RollDegree` on the MS frames is **erratic /
  convention-coded**, not a smooth boresight: across captures `GimbalRoll` toggles
  between `+0.00` and `+180.00` and `GimbalYaw` flips ~+29°↔−151° with flight
  direction. ⚠️ **Do not** treat MS gimbal angles as the MS absolute pose. The RGB
  gimbal *is* stabilised (`GimbalYaw≈FlightYaw`, `GimbalPitch≈−90`).
- **Intrinsics / distortion:** `DewarpData` (fx, fy, cx, cy + distortion) and
  `CalibratedFocalLength` for both cameras — RGB ≈ 3725 px @ 5280 px wide; MS ≈ 2170
  px @ 2592 px wide. MS frames also carry **`DewarpHMatrix`** (the inter-band
  homography) and `RelativeOpticalCenterX/Y`.
- **Positioning:** `GpsStatus="RTK"`, `RtkFlag=16`, per-image `RtkStd{Lat,Lon,Hgt}`
  ≈ (1.27, 1.06, 2.85) m — i.e. RTK but ~1 m horizontal std on these images.
- **PPK present:** the dataset root has `…_PPK{NAV,OBS,RAW}` + `…_Timestamp.MRK`
  (event marks with cm-level Lat/Lon/Ellh per exposure). This is a path to cm-level
  camera centres independent of SFM, relevant to flaw 2.
- **Existing parsing:** only `FlightYawDegree` (calibration endpoint regex) and
  `CalibratedFocalLength` are read today; roll/pitch, DewarpData distortion,
  DewarpHMatrix, RelativeOpticalCenter, and the MRK are **not** consumed by the
  ortho path.

### 2.10 External technical reports — doming mechanism + cross-drone metadata

Two technical reports supplied by the user (2026-06-12) directly inform Phases 1
and the generic design. Verified against this dataset + code where checkable.

**(a) Doming report** ("Bending the doming effect… through bundle adjustment").
Attributes the bowl to **uncorrected interior-orientation error absorbed by
exterior orientation** during BA — confirmed present in our pipeline (Phase 1):

| IO parameter error | EO deformation it induces |
|---|---|
| Camera constant `f` | erroneous model scale, compensated in flying height `Z_L` (vertical bowl) |
| Principal point `x0,y0` | false ω/φ tilts → systematic curvature |
| Uncorrected radial distortion `k1,k2,k3` | object-space surface warps to absorb ray residuals |

Mitigations and their availability **on this already-flown dataset**:
- *Self-calibration / fix known additional parameters* (§4.3) → **AVAILABLE** — seed
  + fix factory `DewarpData` (Phase 1 primary lever). Verified our RGB carries real
  distortion (k1=−0.1126) that SFM currently re-estimates from scratch.
- *GCPs to anchor Z and break IO↔EO correlation* (§4.1) → **NOT available** (no GCPs,
  D7).
- *Varying altitude + cross-strips to diversify ray geometry* (§4.2) → **NOT
  available** retroactively (single-altitude grid); future-flight guidance (§7).
- *Fix DSM before orthorectification* (§4.4) → this is exactly the C6 build-order
  decision (Phase 1 before Phase 2).

**(b) Cross-drone metadata report.** Validates the generic per-sensor descriptor
(D8) and clarifies tag families across manufacturers. Verified on the M3M:
- M3M exposes **only** `RelativeOpticalCenterX/Y` (no `Z`), `DewarpHMatrix`, and
  `DewarpData`. It has **no** `CalibratedHMatrix`, **no** `RigRelatives`, **no**
  `RigTranslations` — those are the **MicaSense / modular-rig** path (relative
  rotation matrix + 3-D lever-arm, solved as the Coplanarity/RigRelatives condition
  inside SfM). This cleanly splits the descriptor source: **DJI integrated →
  homography + RelativeOpticalCenter from XMP; MicaSense/modular → RigRelatives +
  RigTranslations (or Option A in COLMAP).**
- The report prefers an **affine** (not similarity) boresight model in general, to
  absorb non-orthogonality/thermal warp. Our §3.5 measurement shows the M3M factory
  `DewarpHMatrix` is *specifically* a pure similarity (scale+translation, rotation≈
  identity) — i.e. DJI already resolved non-orthogonality into the factory matrix,
  so for the M3M the similarity is correct as given; the affine generalisation is
  retained for the generic/other-sensor descriptor, not forced on the M3M.
- Note `RelativeOpticalCenter` units: the report frames these as the lever-arm
  translation; our values are in **pixels** on the MS plane (NIR=origin), applied in
  §3.5 step (1). Consistent — pixel offset on the common MS plane *is* the projected
  inter-sensor translation at the M3M's fixed geometry.

---

## 3. Decision

**Multispectral orthorectification must be driven by the SFM reconstruction, the
same way RGB already is, instead of GPS+nadir direct georeferencing.** The user's
own question — *should a band go through SFM?* — is answered **yes**.

The *mechanism* for giving MS bands SFM-grade poses has two viable options. This
ADR analyses both and recommends one, but **leaves the final choice to the user**
(per decision on 2026-06-11). No code is written until that choice is made.

### Option A — Register MS band images into the COLMAP reconstruction

Add MS images (one band, or all four) into the existing RGB model via
`image_registrator` (register-against-known-model), so bundle adjustment solves
their poses directly; then orthorectify each band by projecting through the DSM
using its solved pose.

- **+** Most rigorous; MS poses are globally consistent with the RGB model and each
  other; naturally absorbs lens offset and tilt.
- **+** One uniform code path (everything is "ortho from poses + DSM").
- **−** Heavier compute (feature extraction + matching + registration on up to
  4×119 extra images).
- **−** MS frames are lower-resolution, noisier, narrower-band → feature matching
  to the RGB model can be less stable; risk of some MS images failing to register.
- **−** Larger change to the SFM stage and its inputs/outputs.

### Option B — Pose transfer from the co-acquired RGB image (recommended)

Exploit the rigid M3M capture geometry (§2.7): for each capture, take the SFM pose
of its RGB image, apply the **fixed RGB→MS-sensor extrinsic offset** (small lens
baseline + boresight; calibratable once from XMP `DewarpHMatrix`/`CalibratedHMatrix`
or estimated empirically), and orthorectify each MS band by projecting through the
DSM with that derived pose.

- **+** Reuses the accurate, already-computed RGB reconstruction; **no extra SFM
  compute**.
- **+** Exploits the M3M's deterministic RGB↔MS pairing (§2.7) — every MS image
  gets a pose, none can "fail to register."
- **+** Replaces all three approximations of §2.2 at once (true pose instead of raw
  GPS, real tilt instead of nadir, reconstruction scale instead of guessed GSD).
- **+** Inter-band offset (ADR 0001) becomes a single fixed extrinsic, not a
  per-capture phase-correlation guess.
- **−** Requires the RGB→MS extrinsic calibration (one-time; M3M provides the data).
- **−** Assumes RGB and MS share the capture instant closely enough that one pose
  serves both (true for the M3M; the gimballed RGB vs body-fixed MS boresight
  difference must be modelled, not ignored).

> **MANDATORY for Option B (per §2.8 external review):** the RGB pose is *gimbal-
> stabilised* (≈nadir) while the MS array is *body-fixed* (tilts with the drone).
> The transfer therefore is **not** "MS pose = RGB pose"; it is `MS_pose =
> RGB_position ⊕ body-attitude(FlightR/P/Y) ⊕ fixed_RGB→MS_boresight`. Per §2.9 the
> MS *gimbal* angles are convention-coded and unusable as absolute attitude — the
> body `FlightRoll/Pitch/Yaw` (identical RGB↔MS, physical) is the correct attitude
> source. Getting this rotation right is the crux of Option B; omitting it would
> re-introduce flaw 1.
- **−** Slightly less "pure" than A (poses are transferred, not independently
  solved), but far lower risk for this sensor.

**Recommendation:** **Option B.** It is the lowest-risk, lowest-compute route that
fully removes the §2.2 root cause, and the M3M's rigid RGB↔MS pairing is exactly
the condition under which pose transfer is sound. Option A is the fallback if the
RGB→MS boresight proves unstable or other (gimballed-RGB) drones must be supported
without a per-model extrinsic.

> The pipeline is *generic over drones*: Option B needs a per-model RGB→MS extrinsic;
> Option A needs none but costs compute. The recommendation is B for M3M with A kept
> as the documented escape hatch.

### 3.5 DECISION: Option B, with a fully manufacturer-defined MS→RGB model (verified)

After empirical investigation of the M3M XMP (2026-06-12, capture 0050 and across
the flight), **Option B is selected**, and the open algorithm questions (§A–D from
the implementation review) are resolved as follows. Critically, the RGB→MS geometry
turned out to be **entirely manufacturer-supplied — no empirical boresight fit is
needed**.

**What the data proved (each link tested on real files):**

1. **Inter-band MS↔MS offset = `RelativeOpticalCenterX/Y`** (manufacturer constant,
   pixels, NIR = origin (0,0)). Measured cap 0050: RED (11.32, 3.06), GREEN
   (7.26, 16.83), RED_EDGE (1.15, 24.70). This *replaces* ADR 0001's empirical
   phase-correlation — the inter-band shift is a known constant, not a guess.

2. **MS plane → RGB image = `DewarpHMatrix`** (manufacturer 3×3, identical across
   all four bands — it maps the common MS plane, not a per-band map). **Verified
   directionally:** applying H to the MS centre (1296, 972) yields (2639.9, 1978.0),
   which equals the RGB principal point `CalibratedOpticalCenter` (2640, 1978) to
   <0.1 px. MS corners map inside the 5280×3956 RGB frame. So H maps **MS pixel →
   RGB pixel**, exactly as the second external source stated.

3. **H is a pure similarity (scale + translation), rotation ≈ identity.** H's 2×2 is
   isotropic scale **1.7162** with zero off-diagonal; bottom row [0,0,1] (affine, no
   perspective). The scale **equals the focal ratio** RGB/MS = 3725.15 / 2170.0 =
   1.7167. ⇒ The MS array and RGB lens are a **rigid, co-axial payload**: the
   MS→RGB **boresight rotation is effectively identity**, the lever-arm is sub-pixel
   at the principal plane (absorbed in H's translation). This is why no empirical
   global fit is required — the manufacturer "Direct EXIF Alignment" is sufficient.

4. **MS gimbal angles are unusable** (convention-coded 0°/180° toggles, §2.9); they
   are *not* needed under this model, because MS never gets its own ground pose — it
   rides into the RGB frame and inherits the RGB camera's SFM pose.

**The resulting projection model (per MS band image, per capture):**

```
MS_band pixel
  → (1) shift by −RelativeOpticalCenter[band]        # align band onto NIR/MS plane  [mfr]
  → (2) undistort with MS DewarpData (Brown-Conrady) # remove MS lens distortion     [mfr]
  → (3) apply DewarpHMatrix                          # MS plane → RGB image plane     [mfr]
  → (4) treat as an RGB-frame observation: use the RGB camera's
        SFM pose (R,t) + RGB intrinsics + the DSM, via INVERSE projection            [SFM]
```

Step (4) is the *existing, correct* RGB orthorectification geometry. Steps (1)–(3)
are three manufacturer constants read from XMP. There is **no empirical boresight
fit and no separate MS bundle adjustment** in the baseline.

**Implementation will be INVERSE projection (B3, confirmed by source):** for each
target UTM ortho grid cell → read DSM Z → form 3D point → project into the RGB
camera (RGB pose+intrinsics) → invert (1)–(3) to land in the raw MS band → sample.
Gap-free, no interpolation of scattered points.

**B4 — distortion-convention validation gate (mandatory before trusting output):**
the MS `DewarpData` is assumed Brown-Conrady (k1,k2,p1,p2,k3). Sign/unit
conventions differ between libraries, so before relying on it the implementation
**must** verify that `undistort(MS) → DewarpHMatrix` reproduces the
already-validated MS-centre→RGB-centre mapping (and a few off-centre points) to
<1 px. If it does not, flip the documented convention until it does. This is the
one step that silently corrupts everything if wrong.

**Generic-over-drones (D8):** the model is parameterised by a small per-sensor
descriptor — `{inter_band_offsets, intra_to_master_homography, master_camera_ref,
distortion_model}`. For the M3M these come from XMP (`RelativeOpticalCenter`,
`DewarpHMatrix`, RGB = master, `DewarpData`). For a drone that does **not** publish
these, the same descriptor is filled by Option A (register MS in COLMAP) or by the
first source's empirical global fit. The orthorectification core is drone-agnostic;
only the descriptor source varies. Option A remains the documented fallback.

**No ground truth (D7):** validation is relative/internal only — band-to-band
high-freq correlation (target: mosaic RED–NIR 0.114 → toward the 0.20 single-capture
ceiling, ideally higher once placement error is gone) and visual footprint alignment
in QGIS (no sawtooth). Absolute geometric accuracy cannot be certified without GCPs.

---

## 4. Plan (priority order; implementation gated on §3 choice)

**Build order reordered per the C6 decision (2026-06-12): de-dome the DSM BEFORE
the MS projection.** Inverse projection samples DSM height to place each ray; a
domed DSM bends the rays and would recreate the spatially-varying misregistration
this ADR exists to remove. Both the user's source and §2.4 confirm the dependency
("orthomosaic accuracy is directly related to DEM accuracy"). So:

**Phase 1 — Reduce DSM doming (prerequisite for correct projection).**
Root cause (confirmed against code + the doming report, §2.10): the SFM stage
**self-calibrates intrinsics from scratch** — `DewarpData` is parsed into metadata
but never seeded into COLMAP, and the bundle adjuster runs with
`refine_focal_length` / `refine_principal_point` / `refine_extra_params` **all
True** (`colmap_service.py` ~L1227). Under the dataset's **single-altitude,
nadir-only grid** (weak ray-intersection diversity), focal length trades against
flying height `Z_L` and principal-point offset trades against ω/φ tilt (doming
report Table 1), producing the §2.4 bowl.

*Primary lever — the only doming mitigation available on already-flown data:*
**seed the camera from the factory `DewarpData` intrinsics and FIX them** (RGB:
f≈3713.29, cx≈2640+7.02, cy≈1978−8.72, k1=−0.1126, k2=0.0149, k3=−0.0271; MS lenses
carry zero distortion). Disabling refinement of focal/principal/distortion removes
the free parameters that the weak geometry otherwise "trades" into the dome — the
manufacturer's known calibration replaces an under-constrained self-calibration.
- *Validation gate:* quadratic-explained variance drops well below 89.9 %;
  centre-vs-corner elevation bias shrinks toward the ±0.27 m real-relief scale.
- *Why first:* every later projection samples this surface; AND Phase 2 projects MS
  *through the RGB camera model* (§3.5 step 4), so fixing the RGB intrinsics here
  directly improves Phase 2 too. The two phases are coupled through the RGB camera.
- *Not retroactively available (doming report §4.1–4.2):* GCPs and
  varying-altitude/cross-strip geometry are the report's other two mitigations but
  require **new flights** — recorded as flight-planning guidance for future
  acquisitions (§7), not usable on this dataset.
- *Risk:* GLOMAP's global positioning still estimates camera params; fixing
  intrinsics is cleanest in the **post-GLOMAP COLMAP bundle-adjuster** step. If the
  factory focal proves slightly off the SFM scale, allow a single global focal
  refine but keep distortion + principal point fixed. Re-measure either way.

**Phase 2 — MS orthorectification through SFM (fixes the puzzle pieces).**
Implement Option B per §3.5: replace `_warp_reflectance_image`'s GPS+nadir placement
with the manufacturer-defined MS→RGB model + inverse projection through the
(now de-domed) DSM using the RGB camera's SFM pose. Keep the RGB ortho /
point-cloud path as the reference implementation. Gate B4 (distortion-convention
check) is part of this phase.
- *Validation gate:* per-band ortho footprints align (no sawtooth offsets in QGIS);
  RED–NIR **mosaic** high-freq corr rises from 0.114 toward / past the ~0.20
  single-capture ceiling; NDVI/NDRE/GNDVI residual/mean drops materially below
  today's 57/95/49 %.

**Phase 3 — Container & coordinate hygiene (low-risk; can run anytime, enables
inspection).** Install PDAL in the SFM container image so `_write_utm_pointcloud`
succeeds and `fused_utm.ply` (UTM, flat, Z=elevation) is emitted for MeshLab.
Document the ECEF-vs-UTM distinction for users. *(Independent of 1–2; could be done
first as a quick win to let the user inspect the cloud correctly.)*

**Phase 4 — Retire / demote band co-registration (ADR 0001 / v0.10.23).**
Under §3.5 the inter-band offset is the manufacturer `RelativeOpticalCenter`
constant applied in projection step (1), so the v0.10.23 phase-correlation becomes
redundant. Remove it or demote to a guarded residual-cleanup fallback. Re-measure to
confirm no regression.

---

## 5. Consequences

- **Positive:** MS products inherit RGB-grade geometric accuracy; vegetation
  indices stop showing puzzle-piece banding; one consistent orthorectification
  model; inter-band alignment becomes a calibrated constant; DSM becomes usable as
  true terrain; point cloud viewable/measurable in UTM.
- **Negative / risk:** Option A adds SFM compute and a registration-failure mode;
  Option B adds a per-drone-model extrinsic calibration dependency. Either is a
  non-trivial change to the orthomosaic stage and must be validated against this job
  before shipping. DSM doming (Phase 2) is a separate, historically stubborn SFM
  problem and may need several iterations.
- **Validation discipline (carried from ADR 0001's lesson):** every phase has a
  numeric gate measured on real data (JOB_11_JUN) before it is declared fixed. No
  "should be better" claims.

---

## 6. How to inspect the current outputs (reference for the user)

- **RGB ortho:** `gdal_translate -of PNG -outsize 1500 0 orthomosaic_rgb.tif out.png`,
  or open in QGIS (it is correct / SFM-derived).
- **NDVI/NDRE/GNDVI:** QGIS → Singleband pseudocolor (Spectral, −1…1). The
  puzzle-piece offsets are the §2.2 defect.
- **Single bands:** load `bands/red_ortho.tif` + `bands/nir_ortho.tif`, swipe to see
  inter-image misregistration.
- **DSM:** `visualization/visualize_dsm.py` on `dsm_filled.tif`; the smooth
  centre-high bowl is the §2.4 doming.
- **Point cloud (now):** `fused_georef.ply` is **ECEF** — correct but tilted in
  MeshLab; coordinates ≈ (4.41e6, 1.91e6, 4.17e6) confirm the right location.
- **Point cloud (after Phase 3):** `fused_utm.ply` will be UTM 34N — flat ground,
  Z = elevation, coordinates ≈ (E 703 764, N 4 555 983).

---

## 7. Out-of-scope future work (recorded from the §2.8 review, not part of this fix)

These improve *absolute radiometric accuracy* and *cosmetic seam quality*; they do
**not** fix the puzzle-piece geometry (§2.2) and are deliberately deferred:

1. **CRP / Empirical Line Method.** The pipeline converts to reflectance using DLS
   irradiance only. The scientific standard adds a Calibrated Reflectance Panel shot
   before/after flight and an empirical-line fit for absolute reflectance. (See
   ADR 0001 §9; M3M datasets may include panel captures.) — *radiometric, not
   geometric.*
2. **Seamline detection + Laplacian/multiband blending.** The current composite is
   distance-weighted feathering. Routing seamlines around tall objects + pyramid
   blending removes ghosting/double-mapping over trees/structures. Lower priority on
   near-flat agricultural fields. — *cosmetic, post-geometry.*
3. **PPK-refined camera centres.** The dataset ships `…PPK{NAV,OBS,RAW}` +
   `…Timestamp.MRK` (cm-level event marks). Feeding PPK positions into the SFM GPS
   prior (or directly to the MS ortho centres) addresses flaw 2's *absolute*
   position independent of, and complementary to, the bundle adjustment.
4. **Flight-planning guidance for future acquisitions (doming report §4.1–4.2).**
   The two strongest doming mitigations cannot be applied to already-flown data and
   are guidance for the *next* survey: (i) place **GCPs** to anchor Z and break the
   IO↔EO correlation; (ii) fly **varying altitudes + perpendicular cross-strips** to
   diversify ray-intersection geometry so `f` cannot trade against `Z_L`. These
   would reduce doming at the source rather than relying on fixed factory intrinsics.

## 8. References

- Doming report — *Bending the Doming Effect in Structure-from-Motion
  reconstructions through bundle adjustment* (ResearchGate 319415319); Frontiers
  Built Environment 2025.1517379; arXiv 2501.14277v2. (Supplied 2026-06-12.)
- Cross-drone geometry/metadata report — *Geometric Models and Calibration
  Protocols for Multispectral Agricultural Drones* (supplied 2026-06-12).
- [ADR 0001](0001-multispectral-banding-correction.md) — inter-band registration
  (now demoted to Phase 4 here).
