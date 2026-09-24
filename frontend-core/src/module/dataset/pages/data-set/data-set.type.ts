import type { icons } from "lucide-vue-next";

export interface UploadDataSet {
  [key: string]: { icon: keyof typeof icons; name: string; isActive: boolean };
}

export interface DataResult {
  count: number;
  previouse: number | null;
  next: string | null;
  results: Array<DataSetItem>;
}

export interface DataSetItem {
  id: string;
  name: string;
  total_files: number;
  total_size: number;
  status: string;
  created_at: string;
  error_message: string | null;
}

export interface InitFileResponse {
  s3_key: string;
  s3_upload_id: string;
  upload_id: string;
}

export interface StartProcessingItems {
  dataset_id: string;
  resolution_gsd: number;
  radiometric_calibration: boolean;
  analysis_mode: "fast" | "full";
}
