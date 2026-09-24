# Operator-Facing Parameters & Processing UX — Design Note

- **Status:** Forward-looking plan (not yet implemented)
- **Date:** 2026-06-13
- **Audience:** product + engineering
- **Question this answers:** *Of all the photogrammetric/SFM parameters in the
  pipeline, which should a non-technical operator actually set from the UI — and
  how do comparable software products handle this?*

---

## 1. The problem

The pipeline exposes dozens of technically-deep knobs: camera model and distortion,
bundle-adjustment refinement flags, the GLOMAP constraint type, feature/match
thresholds, the four-stage resolution chain, dense-fusion consistency, PPK priors,
geo-registration tolerances, and more. Each is real and consequential — but **almost
none of them are meaningful to a non-expert operator**, and exposing them invites
mis-configuration that silently degrades results (the doming and striping issues both
trace to defaults a non-expert would never know to change).

The goal of this note: define a **small, safe operator surface** and push everything
else to **data-driven auto-detection**, matching how mature products behave.

---

## 2. How comparable software works

Across the established drone-photogrammetry tools — **Pix4D / PIX4Dfields, Agisoft
Metashape, DroneDeploy, WebODM/OpenDroneMap, DJI Terra** — the consistent pattern is:

1. **Pick a use-case template, not parameters.** The operator selects something like
   *"Agriculture — Multispectral / Index maps"*, *"3D Maps & Models"*, or
   *"Terrain / DTM"*. The template silently sets the deep parameters.
2. **One quality/resolution dial.** A coarse **Low / Medium / High / Full** (or
   "1/8, 1/4, 1/2, Full image scale") slider. This is the single knob that most
   affects output detail and runtime — it maps internally to image downscale, point
   density, and depth-map resolution.
3. **Auto-detect everything physical.** Camera make/model and its calibration come
   from an internal **camera database** or the image EXIF/XMP; RTK/PPK presence,
   image overlap, and ground footprint are inferred from the data. The user does not
   choose a distortion model or a bundle-adjustment strategy.
4. **A few optional, understandable extras.** Output coordinate system (CRS), Ground
   Control Points (GCPs) / checkpoints, and sometimes a "dense vegetation / surface
   vs terrain" switch. All optional, all in plain language.

What they deliberately **hide**: distortion coefficients, BA refinement toggles,
matching ratios, fusion consistency, the equivalent of our `constraint_type`. These
are chosen by the template/quality preset, never surfaced.

> The throughline: **the operator expresses intent (what they're mapping, how good /
> how fast); the software derives correctness from the data.**

---

## 3. Recommended operator surface for this system

Expose only these; everything else is internal.

| UI control | Plain-language meaning | Maps internally to |
|---|---|---|
| **Quality / resolution preset** (Low / Medium / High / Full) | Detail vs speed/VRAM | the four-stage `*_max_image_size` chain (kept consistent: undistort = patch_match, fusion ≥ patch_match), point density |
| **Analysis mode** (RGB only / Multispectral indices) | What products to make | `analysis_mode`, whether band orthorectification + vegetation indices run |
| **Target GSD** (cm/px) — usually auto from altitude/EXIF | Output ground resolution | `get_colmap_settings_for_gsd`, output raster resolution |
| **Output coordinate system (CRS)** — default auto from GPS | Map projection of deliverables | UTM zone selection / reprojection |
| **Ground Control Points** (optional) | Survey-grade accuracy / anchoring | GCP-constrained alignment (future) |

That is the whole surface. The single most impactful knob is the **quality preset** —
it determines whether crop-row structure resolves (see ADR 0003 §5) and the
runtime/VRAM envelope.

---

## 4. What must stay auto-detected (never operator-set)

These are correctness decisions that depend on the *data*, not on operator taste.
Getting them right is the job of the pipeline, not the user:

| Auto-detected from… | Decision | Reference |
|---|---|---|
| DJI `DewarpData` in XMP present | Seed + lock factory intrinsics (FULL_OPENCV + k3) | ADR 0002 (shipped v0.10.24) |
| `.MRK` / RTK present **and** cm-accurate | Use PPK per-image priors in BA; constraint type → `POINTS_AND_CAMERAS_BALANCED` | ADR 0003 |
| Positioning is consumer-GPS only (~3–5 m) | Stay visual-only (`ONLY_POINTS`) — tight priors would *add* error | ADR 0003 §4.1 |
| Manufacturer / sensor signature | Per-sensor intrinsics descriptor (DJI vs MicaSense vs generic) | ADR 0002 (D8 generic design) |
| Image distortion / camera model | Distortion model + BA refinement flags | ADR 0002 §3.5 |

**`COLMAP_GLOMAP_CONSTRAINT_TYPE` specifically must NOT be an operator field** — it
is degenerate unless paired with the correct (ECEF) prior frame, and the correct
value is drone-dependent. It is an *internal* consequence of PPK auto-detection.

---

## 5. The recommended implementation pattern: "auto-detect with override"

Each correctness feature should follow one pattern (the doming fix already does this):

1. **Detect** the enabling data signature (DewarpData, MRK, RTK flags, accuracy std).
2. **Decide** the dependent internal parameters automatically (intrinsic lock; PPK
   priors + constraint type; distortion model).
3. **Allow an env-var override** for engineers/debugging
   (`COLMAP_SEED_FACTORY_INTRINSICS`, future `COLMAP_USE_PPK_PRIORS`) — default to
   the auto decision, not a hard-coded value.
4. **Log the decision** with its evidence (e.g. *"PPK MRK found, σ_z≈X cm → camera
   priors enabled"*), so a run is self-explaining.

This keeps the operator surface tiny, makes the system correct-by-default across
drone types, and preserves an escape hatch without exposing it.

---

## 6. Suggested phasing (future work)

1. **Auto-detection layer.** Promote the current debug flags
   (`COLMAP_SEED_FACTORY_INTRINSICS`, future PPK flag) to *auto-detect-with-override*
   based on data signatures; pick `constraint_type` internally. (Small, high-value.)
2. **Quality presets.** Define Low/Med/High/Full → the resolution-chain values, VRAM-
   aware for the target GPU (see ADR 0003 §5.3 for the 8 GB GTX 1080 envelope). Expose
   one preset field; retire raw `*_max_image_size` from the operator surface.
3. **Use-case templates.** Bundle (analysis_mode + preset + sensible defaults) into
   named templates ("Agriculture / Multispectral", "Terrain", "3D model").
4. **GCP ingestion** (optional accuracy tier) — the absolute-accuracy lever the
   doming/striping ADRs note we currently lack (no GCPs = D7).

---

## 7. One-line summary

Expose **what to map** (mode/template) and **how good vs how fast** (quality preset) —
plus optional GSD/CRS/GCPs. Derive **everything photogrammetric** (intrinsics, PPK
priors, constraint type, distortion, refinement) from the data, with engineer-only
overrides. That is both what mature tools do and what keeps this pipeline correct
across the range of drones it must support.
