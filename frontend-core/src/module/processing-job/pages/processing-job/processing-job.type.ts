export interface ProcessingJobItem {
  id: string;
  job_name: string;
  dataset_name: string;
  status: string;
  progress: number;
  created_at: string;
  end_time?: string;
  stage: string;
  duration_seconds: string;
  actions: string;
  resolution_gsd: string;
  error_message: string | null;
}

// resolution_gsd:string;
