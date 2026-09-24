# PhotoGear Benchmark Suite

Benchmark and validate the PhotoGear AI image processing pipeline (calibration, SFM, orthomosaic).

## Quick Start

```bash
# Run full pipeline benchmark
python -m benchmark --dataset-path ./data/images

# Use a known dataset preset (auto-configures stages and GSD)
python -m benchmark --dataset zenodo-eastkazakhstan --dataset-path ./data/zenodo_7749239

# List available dataset presets
python -m benchmark --list-datasets

# Scan a dataset directory to see what's inside
python -m benchmark --detect-layout ./data/zenodo_7749239

# Run with custom GPU and multiple runs for reproducibility
python -m benchmark --dataset-path ./data/images --gpu-count 2 --num-runs 3

# Benchmark specific stages only
python -m benchmark --dataset-path ./data/images --stages sfm,orthomosaic

# Run with validation against ground truth
python -m benchmark --dataset-path ./data/images \
    --validate \
    --ground-truth ./data/ground_truth

# Set target GSD and custom timeout
python -m benchmark --dataset-path ./data/images \
    --target-gsd 2.5 \
    --timeout 7200
```

## CLI Arguments

| Argument              | Default              | Description                                     |
|-----------------------|----------------------|-------------------------------------------------|
| `--dataset-path`      | `None`               | Path to dataset directory with `images/` folder  |
| `--dataset`           | `None`               | Dataset preset name (auto-configures stages/GSD) |
| `--list-datasets`     | —                    | List available dataset presets and exit           |
| `--detect-layout`     | `None`               | Scan a directory and print detected layout        |
| `--output-path`       | `benchmark_results/` | Where to store results and reports               |
| `--ground-truth`      | `None`               | Path to GCPs and reference reflectance           |
| `--gpu-count`         | `1`                  | Number of GPUs (0 = CPU only)                    |
| `--num-runs`          | `1`                  | Runs per stage for reproducibility               |
| `--timeout`           | `3600`               | Timeout per stage in seconds                     |
| `--gateway-url`       | `http://localhost:8080` | API gateway URL                               |
| `--stages`            | `all`                | Stages: `all`, `calibration`, `sfm`, `orthomosaic` |
| `--target-gsd`        | `None`               | Target GSD in cm/px                              |
| `--max-image-size`    | `None`               | Max image dimension in pixels                    |
| `--validate`          | `false`              | Run accuracy validation after benchmark          |
| `--checkpoint-rmse-h` | `0.10`               | Max horizontal RMSE (meters)                     |
| `--checkpoint-rmse-v` | `0.15`               | Max vertical RMSE (meters)                       |
| `--radiometric-r2`    | `0.85`               | Min radiometric R² threshold                     |
| `--reproducibility`   | `0.99`               | Min run-to-run correlation                       |
| `--gsd-accuracy`      | `0.05`               | Max GSD deviation fraction (5%)                  |

## Validation Metrics

When `--validate` is used with `--ground-truth`, the suite runs:

| Metric                 | Threshold   | Standard  | Description                              |
|------------------------|-------------|-----------|------------------------------------------|
| Checkpoint RMSE (H)    | < 10 cm     | ASPRS     | Horizontal positional accuracy            |
| Checkpoint RMSE (V)    | < 15 cm     | ASPRS     | Vertical positional accuracy              |
| Radiometric R²         | > 0.85      | —         | Calibration correlation with reference    |
| Reproducibility        | > 99%       | —         | Run-to-run pixel correlation              |
| GSD Accuracy           | within 5%   | —         | Measured vs. target ground resolution     |
| Visual QA              | > 0.7       | —         | Coverage, blur, color, seam detection     |

## Dataset Layout

```
dataset_path/
├── images/          # Input images (JPG, TIFF, PNG, DNG)
└── sfm_output/      # (optional) Pre-computed SFM results
    └── run_1/

ground_truth/        # (optional, for --validate)
├── gcps.csv         # Columns: id, x, y, z
├── reference_reflectance.csv  # Columns: id, red, green, nir, ...
└── estimated_coords.csv       # Columns: id, x, y, z
```

## Environment Variables

All settings can be configured via `BENCHMARK_*` env vars (see `.env.example`):

```bash
BENCHMARK_DATASET_PATH=./data/images
BENCHMARK_GPU_COUNT=1
BENCHMARK_NUM_RUNS=1
BENCHMARK_GATEWAY_URL=http://localhost:8080
BENCHMARK_RUN_STAGES=all
```

CLI arguments override env variables.

## Output

Results are saved to `--output-path` as:

```
benchmark_results/
├── benchmark_report_YYYYMMDD_HHMMSS.json
├── calibration/
│   └── run_0/result.json
├── sfm/
│   └── run_0/result.json
└── orthomosaic/
    └── run_0/result.json
```

## Reference Datasets

Two published multispectral datasets are supported as presets.

### 1. East Kazakhstan (Zenodo)

- **Source:** <https://zenodo.org/records/7749239>
- **Sensor:** DJI Phantom 4 Multispectral (Blue, Green, Red, RedEdge, NIR)
- **Expected GSD:** ~3 cm/px
- **Contents:**
  - Flight sessions by date: `2022-05-17`, `2022-05-18`, `2022-06-08`, `2022-06-09`
  - Each session contains raw multispectral TIFFs
  - Pre-processed reference products: orthomosaics / DEMs / NDVI maps
- **Ground truth:** No separate GCP file. Reference products serve as comparison targets for spatial accuracy and vegetation index validation.

```bash
# Example: benchmark the East Kazakhstan dataset
python -m benchmark \
    --dataset zenodo-eastkazakhstan \
    --dataset-path /path/to/zenodo_7749239 \
    --validate \
    --ground-truth /path/to/zenodo_7749239/reference_products
```

### 2. WUR Dataverse

- **Source:** <https://dataverse.nl> (Wageningen University)
- **Sensor:** Multi-sensor (multispectral + thermal)
- **Contents:**
  - Split archive (`dataset.zip.001` through `.016`); extract first:
    ```bash
    cat dataset.zip.* > dataset_combined.zip
    unzip dataset_combined.zip -d wur_extracted
    ```
  - Contains raw drone imagery + handheld spectrometer measurements
- **Ground truth:** Handheld spectrometer CSV with per-plot reflectance values (use for radiometric R² validation).

```bash
# Example: benchmark the WUR dataset (calibration only)
python -m benchmark \
    --dataset wur-dataverse \
    --dataset-path /path/to/wur_extracted \
    --validate \
    --ground-truth /path/to/wur_extracted/spectrometer
```

### Discovering Dataset Layout

Use `--detect-layout` to scan a dataset directory before benchmarking:

```bash
python -m benchmark --detect-layout /path/to/dataset
```

This prints:
- Detected image directories and file counts
- Ground truth files (CSV, GeoJSON)
- Reference products (orthomosaics, DEMs, NDVI)
- Detected sensor types

### Dataset Location

Datasets are stored on the data server:

```
omidsa@192.168.11.2:/media/omidsa/Data5/PhotoGearData/benchmark_datasets/
├── zenodo_7749239/          # East Kazakhstan
│   └── Component 1 - part 1-2/
│       ├── 2022-05-17/      # Flight sessions with raw TIFFs
│       ├── 2022-05-18/
│       ├── 2022-06-08/
│       └── 2022-06-09/
└── wur_dataset/             # WUR (split archive, needs extraction)
    ├── dataset.zip.001
    ├── ...
    └── dataset.zip.016
```

## Architecture

```
benchmark/
├── __init__.py
├── __main__.py          # CLI entry point (argparser)
├── settings.py          # Pydantic settings (BENCHMARK_* env prefix)
├── report.py            # JSON report generator
├── runners/
│   ├── base.py          # BaseRunner with timing & error handling
│   ├── pipeline.py      # Orchestrates all stages
│   ├── calibration.py   # Radiometric calibration runner
│   ├── sfm.py           # Structure from Motion runner
│   └── orthomosaic.py   # Orthomosaic generation runner
├── validators/
│   ├── checkpoint.py    # GCP RMSE validation
│   ├── radiometric.py   # Reflectance R² validation
│   ├── spatial.py       # GSD accuracy & reproducibility
│   └── visual.py        # Visual QA (coverage, blur, seams)
├── docker-compose-colmap.yaml
└── docker-compose-opensfm.yaml
```

## Standalone COLMAP/OpenSfM Benchmarks

For standalone reconstruction benchmarking (without the full pipeline):

1. Clone the repositories:
   ```bash
   cd benchmark
   git clone https://github.com/colmap/colmap.git
   git clone https://github.com/mapillary/OpenSfM.git
   ```

2. Place images in `data/images/`

3. Run:
   ```bash
   docker compose -f docker-compose-colmap.yaml up --build
   docker compose -f docker-compose-opensfm.yaml up --build
   ```
