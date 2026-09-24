type FileType =
  | "ARCHIVE"
  | "IMAGE"
  | "VIDEO"
  | "AUDIO"
  | "DOCUMENT"
  | "OTHER"
  | "zip";

export interface DatasetFileUpload {
  dataset_name?: string;
  batch_id?: string;
  file_name?: string;
  file_type?: FileType;
  content_type?: string;
  file_size?: number;
  retry_upload_id?: string | null;
  source_url?: string;
}
