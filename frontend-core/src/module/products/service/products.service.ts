import api from "@/core/services/axios";
import to from "await-to-js";
import { Products_ROUTE } from "./products.route";

export const getProductListWithFilter = async (
  jobId: string,
  page: number,
  size: number,
  type?: string,
  createdAfter?: string | Date,
  createdBefore?: string | Date,
) => {
  const params: Record<string, any> = { page: page, page_size: size };

  params.job_id = jobId;

  if (type) params.type = type;

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

  const [err, res] = await to(
    api.get(Products_ROUTE.getProductList, { params }),
  );

  if (err) {
    throw err;
  }

  return res.data;
};

export const getProductDetail = async (productId: string) => {
  const url = Products_ROUTE.getProductDetail.replace(
    "{product_id}",
    String(productId),
  );

  const [err, res] = await to(api.get(url));

  if (err) {
    throw err;
  }

  return res.data;
};

export const getCompletedJobList = async () => {
  const params: Record<string, any> = {
    status: "completed",
    page_size: 100,
  };

  const [err, res] = await to(
    api.get(Products_ROUTE.getJobList, { params }),
  );

  if (err) {
    throw err;
  }

  return res.data;
};

export const getJobDetail = async (jobId: string) => {
  const url = Products_ROUTE.getJobDetail.replace("{job_id}", jobId);

  const [err, res] = await to(api.get(url));

  if (err) {
    throw err;
  }

  return res.data;
};
