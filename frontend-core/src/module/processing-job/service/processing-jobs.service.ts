import api from "@/core/services/axios";
import { toastService } from "@/core/services/toast.service";
import to from "await-to-js";
import type { StartProcessingRequestRequest } from "./processing-jobs.type";
import { Processing_Jobs_ROUTE } from "./processing-jobs.route";

export const getJobList = async (
  searchText?: string,
  statuses?: string[],
  stages?: string[],
  createdAfter?: string | Date,
  createdBefore?: string | Date,
  page?: number,
  pageSize?: number,
) => {
  const params: Record<string, any> = {};

  if (searchText) params.search = searchText;

  if (statuses && statuses.length) params.status = statuses.join(",");

  if (stages && stages.length) params.stage = stages.join(",");

  if (createdAfter) {
    params.created_after =
      createdAfter instanceof Date
        ? createdAfter.toISOString()
        : String(createdAfter);
  }
  if (createdBefore) {
    params.created_before =
      createdBefore instanceof Date
        ? createdBefore.toISOString()
        : String(createdBefore);
  }

  if (page) params.page = page;
  if (pageSize) params.page_size = pageSize;

  const [err, res] = await to(api.get(Processing_Jobs_ROUTE.list, { params }));

  if (err) {
    throw err;
  }

  return res.data;
};

export const startJob = async (body: StartProcessingRequestRequest) => {
  const [err, res] = await to(api.post(Processing_Jobs_ROUTE.startJob, body));
  if (err) {
    throw err;
  }

  toastService.success("Success!", res.data.message);
  return res.data;
};

export const deleteJob = async (jobId: string | number) => {
  const url = Processing_Jobs_ROUTE.Delete.replace("{job_id}", String(jobId));
  const [err, res] = await to(api.delete(url));

  if (err) {
    throw err;
  }

  toastService.success(
    "Deleted",
    res.data?.message || "Job deleted successfully",
  );
  return res.data;
};

export const cancelJob = async (jobId: string) => {
  const url = Processing_Jobs_ROUTE.cancel.replace("{job_id}", jobId);
  const [err, res] = await to(api.post(url));
  if (err) throw err;
  toastService.success(
    "Cancelled",
    res.data?.message ?? "Job cancelled successfully",
  );
  return res.data;
};

export const retryJob = async (jobId: string, forceRestart: boolean) => {
  const url = Processing_Jobs_ROUTE.rerun.replace("{job_id}", jobId);

  const [err, res] = await to(
    api.post(url, null, {
      params: { resume: !forceRestart },
    }),
  );

  if (err) throw err;

  toastService.success(
    "Success!",
    res.data?.message ?? "Job retried successfully",
  );

  return res.data;
};
