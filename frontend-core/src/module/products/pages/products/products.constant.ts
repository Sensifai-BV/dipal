export const ProductTableHeaders: Array<{
  text: string;
  field?: string;
  sortable?: boolean;
  styles?: string;
}> = [
  { text: "Type", field: "type_display", styles: "col-span-3" },
  { text: "Category", field: "category", styles: "col-span-2" },
  { text: "Resolution", field: "resolution_cm", styles: "col-span-2" },
  { text: "Created at", field: "created_at", styles: "col-span-3" },
  {
    text: "Actions",
    field: "actions",
    sortable: false,
    styles: "text-right col-span-2",
  },
];

export const EXPECTED_PRODUCTS = [
  { type: "orthomosaic", label: "2D Orthomosaic" },
  { type: "dsm", label: "Digital Surface Model (DSM)" },
  { type: "pointcloud", label: "3D Point Cloud" },
  { type: "pointcloud_utm", label: "3D Point Cloud (UTM)" },
  { type: "ndvi", label: "NDVI Map" },
  { type: "ndre", label: "NDRE Map" },
  { type: "gndvi", label: "GNDVI Map" },
  { type: "calibrated_reflectance", label: "Calibrated Reflectance" },
  { type: "band_manifest", label: "Band Classification Manifest" },
  { type: "band_green", label: "Green Band Ortho" },
  { type: "band_red", label: "Red Band Ortho" },
  { type: "band_red_edge", label: "Red Edge Band Ortho" },
  { type: "band_nir", label: "NIR Band Ortho" },
  { type: "band_blue", label: "Blue Band Ortho" },
];

export const ACTIVE_JOB_STATUSES = new Set(["pending", "queued", "processing"]);

export const STAGE_LABELS: Record<string, string> = {
  radiometric_calibration: "Radiometric Calibration",
  sfm: "Structure from Motion (SFM)",
  orthomosaic_generation: "Orthomosaic Generation",
  uploading: "Uploading Results",
  publishing: "Publishing",
};

export const MULTISPECTRAL_PRODUCT_TYPES = [
  "ndvi",
  "ndre",
  "gndvi",
  "calibrated_reflectance",
  "band_green",
  "band_red",
  "band_red_edge",
  "band_nir",
  "band_blue",
];

export const DOWNLOAD_ONLY_TYPES = [
  "band_manifest",
  "statistics",
  "preview",
];
