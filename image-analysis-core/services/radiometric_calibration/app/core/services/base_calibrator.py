"""Base calibrator with shared radiometric correction algorithms.

All vendor-agnostic image processing steps live here.  Vendor-specific
subclasses override metadata extraction while re-using the mathematical
corrections.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from infrastructure.logging import get_logger

from .interfaces import CalibrationMetadata, IDroneImageProcessor

logger = get_logger(__name__)


class BaseDroneCalibrator(IDroneImageProcessor):
    """
    Base calibrator implementing shared radiometric correction algorithms.

    Subclasses must implement:
      - extract_calibration_metadata()
      - get_supported_bands()
      - _parse_vendor_metadata()  (helper for load_image)
    """

    def __init__(self) -> None:
        self.band_data: dict[str, dict] = {}

    def load_image(self, image_path: str | Path, band_name: str) -> None:
        """
        Load an image and extract vendor-specific metadata.

        Args:
            image_path: Path to the image file
            band_name: Spectral band name
        """
        image_path = Path(image_path)
        img = Image.open(image_path)
        img_array = np.array(img)

        cal_meta = self.extract_calibration_metadata(image_path)
        cal_meta.image_height, cal_meta.image_width = img_array.shape[:2]

        self.band_data[band_name] = {
            "image": img_array,
            "metadata": cal_meta,
            "corrected_image": None,
            "image_path": str(image_path),
        }

    def get_corrected_image(self, band_name: str) -> np.ndarray | None:
        """
        Return the corrected image for a band if available.

        Args:
            band_name: Band name

        Returns:
            Corrected image array or None
        """
        data = self.band_data.get(band_name)
        if data is None:
            return None
        return data.get("corrected_image")

    # ------------------------------------------------------------------
    # Universal correction steps
    # ------------------------------------------------------------------

    def vignetting_correction(
        self,
        image: np.ndarray,
        meta: CalibrationMetadata,
    ) -> np.ndarray:
        """
        Apply vignetting correction using polynomial model.

        Args:
            image: Input image as float64
            meta: Calibration metadata with vignetting params

        Returns:
            Vignetting-corrected image
        """
        img = image.astype(np.float64)
        h, w = img.shape[:2]

        cx = meta.vignetting_center_x if meta.vignetting_center_x is not None else w / 2
        cy = meta.vignetting_center_y if meta.vignetting_center_y is not None else h / 2

        k = meta.vignetting_coefficients
        if not k or len(k) < 6:
            return img

        y, x = np.ogrid[:h, :w]
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

        correction = (
            k[5] * r**6
            + k[4] * r**5
            + k[3] * r**4
            + k[2] * r**3
            + k[1] * r**2
            + k[0] * r
            + 1.0
        )

        return img * correction

    def distortion_correction(
        self,
        image: np.ndarray,
        meta: CalibrationMetadata,
    ) -> np.ndarray:
        """
        Apply lens distortion correction using camera intrinsics.

        Args:
            image: Input image
            meta: Calibration metadata with dewarp params

        Returns:
            Undistorted image
        """
        params = meta.dewarp_params
        if not params or len(params) < 9:
            return image

        fx, fy, cx, cy, k1, k2, p1, p2, k3 = params[:9]

        h, w = image.shape[:2]
        opt_cx = meta.vignetting_center_x if meta.vignetting_center_x is not None else w / 2
        opt_cy = meta.vignetting_center_y if meta.vignetting_center_y is not None else h / 2

        camera_matrix = np.array([
            [fx, 0, opt_cx + cx],
            [0, fy, opt_cy + cy],
            [0, 0, 1],
        ])
        dist_coeffs = np.array([k1, k2, p1, p2, k3])

        return cv2.undistort(image, camera_matrix, dist_coeffs, None, camera_matrix)

    def homography_alignment(
        self,
        image: np.ndarray,
        meta: CalibrationMetadata,
    ) -> np.ndarray:
        """
        Apply perspective transformation for band-to-band alignment.

        Args:
            image: Input image
            meta: Calibration metadata with homography matrix

        Returns:
            Aligned image
        """
        h_values = meta.homography_matrix
        if not h_values or len(h_values) != 9:
            return image

        H = np.array(h_values, dtype=np.float64).reshape(3, 3)
        h, w = image.shape[:2]
        return cv2.warpPerspective(image, H, (w, h))

    def exposure_alignment(
        self,
        reference: np.ndarray,
        target: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Align two images using Enhanced Correlation Coefficient (ECC).

        Args:
            reference: Reference image array
            target: Target image to align

        Returns:
            Tuple of (reference, aligned_target)
        """
        ref_8 = cv2.normalize(reference, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        tgt_8 = cv2.normalize(target, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        ref_smooth = cv2.GaussianBlur(ref_8, (5, 5), 0)
        tgt_smooth = cv2.GaussianBlur(tgt_8, (5, 5), 0)

        warp_mode = cv2.MOTION_AFFINE
        warp_matrix = np.eye(2, 3, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 5000, 1e-10)

        try:
            _, warp_matrix = cv2.findTransformECC(
                ref_smooth, tgt_smooth, warp_matrix, warp_mode, criteria,
            )
            h, w = reference.shape[:2]
            aligned = cv2.warpAffine(
                target, warp_matrix, (w, h),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            )
        except cv2.error:
            logger.warning("ECC alignment failed, returning original target")
            aligned = target

        return reference, aligned

    def calculate_camera_signal(
        self,
        image: np.ndarray,
        meta: CalibrationMetadata,
    ) -> np.ndarray:
        """
        Normalised camera signal value (Eq. 9 in DJI calibration spec).

        Args:
            image: Corrected image
            meta: Calibration metadata

        Returns:
            Camera signal array
        """
        i_norm = image / (2 ** meta.bit_depth)
        i_black = meta.black_level / (2 ** meta.bit_depth)
        signal = (i_norm - i_black) / (meta.sensor_gain * meta.exposure_time_us / 1e6)
        return signal

    def calculate_reflectance_from_signal(
        self,
        camera_signal: np.ndarray,
        meta: CalibrationMetadata,
    ) -> np.ndarray:
        """
        Convert camera signal to reflectance using irradiance.

        Args:
            camera_signal: Output of calculate_camera_signal
            meta: Calibration metadata

        Returns:
            Reflectance array (0-1 range, clipped)
        """
        # The DLS Irradiance value is a raw sensor count captured with its own
        # exposure time and gain.  Dividing the camera signal by the *raw*
        # irradiance leaves a constant (exposure × gain) factor in the
        # denominator, producing reflectance ~10-12× too small (e.g. NIR median
        # 0.011 instead of the physical ~0.13).  Normalise the irradiance to the
        # same per-unit basis as the camera signal before dividing.
        irradiance_norm = meta.irradiance / (
            meta.irradiance_exposure_time * meta.irradiance_gain + 1e-10
        )
        reflectance = (camera_signal * meta.sensor_gain_adjustment) / (
            irradiance_norm + 1e-10
        )
        clipped = np.clip(reflectance, 0, 1)
        self._log_reflectance_scale(reflectance, clipped, meta)
        return clipped

    def _log_reflectance_scale(
        self,
        reflectance: np.ndarray,
        clipped: np.ndarray,
        meta: CalibrationMetadata,
    ) -> None:
        """
        Emit a diagnostic summarising the reflectance magnitude and clip rate.

        Physically meaningful vegetation reflectance is roughly 0.05 (red) to
        0.5 (NIR).  A median far below that range indicates the irradiance
        normalisation or the exposure/gain unit conversion is off; a high
        clip-high fraction indicates the opposite (irradiance too small).  These
        values are otherwise invisible, which is why the persistent low-reflectance
        problem went undiagnosed — so log them once per band.

        Args:
            reflectance: Reflectance before clipping
            clipped: Reflectance after ``np.clip(.., 0, 1)``
            meta: Calibration metadata (band, irradiance, exposure, gain)
        """
        finite = reflectance[np.isfinite(reflectance)]
        if finite.size == 0:
            return
        clip_hi = float(np.mean(finite > 1.0))
        clip_lo = float(np.mean(finite < 0.0))
        irradiance_norm = meta.irradiance / (
            meta.irradiance_exposure_time * meta.irradiance_gain + 1e-10
        )
        logger.info(
            f"[{meta.band_name}] reflectance median={float(np.median(clipped)):.4f} "
            f"p99={float(np.percentile(clipped, 99)):.4f} "
            f"clip>1={clip_hi:.1%} clip<0={clip_lo:.1%} | "
            f"irradiance_raw={meta.irradiance:.4g} "
            f"irradiance_norm={irradiance_norm:.4g} "
            f"(irr_exp={meta.irradiance_exposure_time:.4g} irr_gain={meta.irradiance_gain:.4g}) "
            f"exposure_us={meta.exposure_time_us:.4g} "
            f"sensor_gain={meta.sensor_gain:.4g} gain_adj={meta.sensor_gain_adjustment:.4g}"
        )

    # ------------------------------------------------------------------
    # Default process_all_steps (subclasses may override)
    # ------------------------------------------------------------------

    def process_all_steps(self, band_name: str) -> np.ndarray:
        """
        Apply vignetting → distortion → alignment corrections.

        Args:
            band_name: Band to process

        Returns:
            Corrected image array
        """
        data = self.band_data.get(band_name)
        if data is None:
            raise ValueError(f"Band '{band_name}' not loaded")

        meta: CalibrationMetadata = data["metadata"]
        img = data["image"].astype(np.float64)

        img = self.vignetting_correction(img, meta)
        img = self.distortion_correction(img, meta)
        img = self.homography_alignment(img, meta)

        data["corrected_image"] = img
        return img

    def calculate_reflectance(self, band_name: str) -> np.ndarray:
        """
        Calculate reflectance for a single band.

        Args:
            band_name: Band name

        Returns:
            Reflectance array
        """
        data = self.band_data.get(band_name)
        if data is None:
            raise ValueError(f"Band '{band_name}' not loaded")

        if data["corrected_image"] is None:
            self.process_all_steps(band_name)

        meta: CalibrationMetadata = data["metadata"]
        signal = self.calculate_camera_signal(data["corrected_image"], meta)
        return self.calculate_reflectance_from_signal(signal, meta)

    # ------------------------------------------------------------------
    # Vegetation indices  (shared maths)
    # ------------------------------------------------------------------

    def calculate_ndvi(self) -> np.ndarray:
        """
        NDVI = (NIR - Red) / (NIR + Red).

        Returns:
            NDVI array clipped to [-1, 1]
        """
        nir_ref = self._ensure_reflectance("NIR")
        red_ref = self._ensure_reflectance("Red")

        nir_aligned, red_aligned = self.exposure_alignment(nir_ref, red_ref)
        ndvi = (nir_aligned - red_aligned) / (nir_aligned + red_aligned + 1e-10)
        return np.clip(ndvi, -1, 1)

    def calculate_ndre(self) -> np.ndarray:
        """
        NDRE = (NIR - RedEdge) / (NIR + RedEdge).

        Returns:
            NDRE array clipped to [-1, 1]
        """
        nir_ref = self._ensure_reflectance("NIR")
        re_ref = self._ensure_reflectance("RedEdge")

        nir_aligned, re_aligned = self.exposure_alignment(nir_ref, re_ref)
        ndre = (nir_aligned - re_aligned) / (nir_aligned + re_aligned + 1e-10)
        return np.clip(ndre, -1, 1)

    def calculate_gndvi(self) -> np.ndarray:
        """
        GNDVI = (NIR - Green) / (NIR + Green).

        Returns:
            GNDVI array clipped to [-1, 1]
        """
        nir_ref = self._ensure_reflectance("NIR")
        green_ref = self._ensure_reflectance("Green")

        nir_aligned, green_aligned = self.exposure_alignment(nir_ref, green_ref)
        gndvi = (nir_aligned - green_aligned) / (nir_aligned + green_aligned + 1e-10)
        return np.clip(gndvi, -1, 1)

    def calculate_vegetation_indices(self) -> dict[str, np.ndarray]:
        """
        Calculate all available vegetation indices based on loaded bands.

        Returns:
            Dictionary of index_name → array
        """
        indices: dict[str, np.ndarray] = {}
        loaded = set(self.band_data.keys())

        if {"NIR", "Red"}.issubset(loaded):
            try:
                indices["ndvi"] = self.calculate_ndvi()
            except Exception as exc:
                logger.error(f"NDVI calculation failed: {exc}")

        if {"NIR", "RedEdge"}.issubset(loaded):
            try:
                indices["ndre"] = self.calculate_ndre()
            except Exception as exc:
                logger.error(f"NDRE calculation failed: {exc}")

        if {"NIR", "Green"}.issubset(loaded):
            try:
                indices["gndvi"] = self.calculate_gndvi()
            except Exception as exc:
                logger.error(f"GNDVI calculation failed: {exc}")

        return indices

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_reflectance(self, band_name: str) -> np.ndarray:
        """
        Ensure a band has been processed and return its reflectance.

        Args:
            band_name: Band name

        Returns:
            Reflectance array

        Raises:
            ValueError: If band is not loaded
        """
        if band_name not in self.band_data:
            raise ValueError(f"Band '{band_name}' must be loaded first")
        return self.calculate_reflectance(band_name)
