import api from "@/core/services/axios";
import { toastService } from "@/core/services/toast.service";
import { generateUUID } from "@/core/utils/utils";
import to from "await-to-js";
import { useDatasetSocket } from "../composable/useDatasetSocket";
import type {
  DataResult,
  InitFileResponse,
  StartProcessingItems,
} from "../pages/data-set/data-set.type";
import { DATA_SET_ROUTE } from "./data-set.route";
import type { DatasetFileUpload } from "./data-set.type";

export const uploadDataSet = async (data: DatasetFileUpload) => {
  const body: DatasetFileUpload = {
    dataset_name: data.dataset_name,
    batch_id: generateUUID(),
    file_name: data.file_name,
    file_type: "ARCHIVE",
    content_type: "application/zip",
    file_size: data.file_size,
    retry_upload_id: null,
  };
  const [err, res] = await to(api.post(DATA_SET_ROUTE.upload.presigned, body));
  if (err) {
    throw err;
  }
  // TODO: fix toast message
  // toastService.success("Success!", res.data || "File uploaded successfully");
  return res.data;
};

export const getDataSet = async (
  page: number,
  size: number,
): Promise<DataResult> => {
  const params = {
    page: page,
    page_size: size,
  };

  const [err, res] = await to(api.get(DATA_SET_ROUTE.datasetStats, { params }));

  if (err) {
    throw err;
  }
  return res.data;
};

export const uploadDataSetInBucket = async (
  data: InitFileResponse,
  file: File,
  onProgress?: (progress: number) => void,
): Promise<void> => {
  if (!file) throw new Error("No file provided");
  if (!data.s3_key) throw new Error("Invalid S3 key");

  const CHUNK_SIZE = 500 * 1024 * 1024;
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

  const uploadedParts: Array<{ ETag: string; PartNumber: number }> = [];
  let totalUploadedBytes = 0;

  try {
    for (let partNumber = 1; partNumber <= totalChunks; partNumber++) {
      const start = (partNumber - 1) * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      // presigned url
      const presignedRes = await api.post(DATA_SET_ROUTE.upload.chunkUpload, {
        upload_id: data.upload_id,
        s3_upload_id: data.s3_upload_id,
        s3_key: data.s3_key,
        part_number: partNumber,
      });

      const presigned = presignedRes.data;

      let lastChunkUploaded = 0;

      const etag = await uploadChunkWithProgress(
        presigned.url,
        chunk,
        (uploaded) => {
          const diff = uploaded - lastChunkUploaded;
          lastChunkUploaded = uploaded;

          totalUploadedBytes += diff;

          const percent = Math.floor((totalUploadedBytes / file.size) * 100);

          onProgress?.(percent);
        },
      );

      uploadedParts.push({
        ETag: etag,
        PartNumber: partNumber,
      });
    }
    const completeUplaod = await api.post(DATA_SET_ROUTE.upload.complete, {
      upload_id: data.upload_id,
      s3_upload_id: data.s3_upload_id,
      s3_key: data.s3_key,
      parts: uploadedParts,
    });
    useDatasetSocket(completeUplaod.data.dataset_id);
    onProgress?.(100);
    toastService.success("Success!", "File uploaded successfully");
  } catch (err: any) {
    if (!err?._toastShown) {
      toastService.error("Error", "Error uploading file to S3 bucket");
    }
    console.error("Upload error:", err);
    throw err;
  }
};

const uploadChunkWithProgress = (
  url: string,
  chunk: Blob,
  onProgress: (uploadedBytes: number) => void,
): Promise<string> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open("PUT", url);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded);
      }
    };

    xhr.onload = () => {
      const etag = xhr.getResponseHeader("etag")?.replace(/"/g, "");
      if (!etag) return reject(new Error("Missing ETag"));
      resolve(etag);
    };

    xhr.onerror = () => reject(new Error("Upload failed"));

    xhr.send(chunk);
  });
};

export const downloadDataset = async (dataset_id: string) => {
  const [err, res] = await to(
    api.post(`${DATA_SET_ROUTE.exportDataSet}${dataset_id}/`),
  );
  if (err) {
    throw err;
  }
  toastService.success("Success!", res.data.message);
  return res.data.job_id;
};

export const getExportJobStatus = async (job_id: string) => {
  const [err, res] = await to(
    api.get(`${DATA_SET_ROUTE.upload.jobStatus}${job_id}/`),
  );
  if (err) {
    throw err;
  }
  return res.data;
};

export const uploadAmazonS3Link = async (link: string, datasetName: string, datasetId?: string) => {
  const cleanUrl = link.split("?")[0];
  const fileName = cleanUrl.split("/").pop() || `import_${generateUUID().slice(0, 6)}.zip`;

  const body: Record<string, any> = {
    dataset_name: datasetName,
    file_url: link,
    file_name: fileName,
    batch_id: generateUUID(),
  };

  if (datasetId) {
    body.dataset_id = datasetId;
  }

  const [err, res] = await to(api.post(DATA_SET_ROUTE.upload.url, body));
  if (err) {
    throw err;
  }
  toastService.success("Success!", res.data.message);
  return res.data;
};

export const startDataSetProcess = async (body: StartProcessingItems) => {
  const [err, res] = await to(api.post(DATA_SET_ROUTE.startProcess, body));
  if (err) {
    throw err;
  }
  toastService.success("Success!", res.data.message);
  return res.data;
};

export const deleteDataset = async (datasetId: string) => {
  const url = DATA_SET_ROUTE.deleteDataset.replace("{dataset_id}", datasetId);
  const [err, res] = await to(api.delete(url));
  if (err) {
    throw err;
  }
  toastService.success("Deleted", res.data?.message || "Dataset deleted successfully");
  return res.data;
};
