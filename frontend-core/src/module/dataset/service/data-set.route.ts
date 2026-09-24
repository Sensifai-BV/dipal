export const DATA_SET_ROUTE = {
  upload: {
    presigned: "api/uploads/multipart/init/",
    chunkUpload: "api/uploads/multipart/sign-part/",
    complete: "api/uploads/multipart/complete/",
    list: "api/uploads/list/",
    jobStatus: "api/uploads/export/status/",
    url: "api/uploads/upload/url/",
  },
  datasetStats: "api/uploads/datasets/stats/",
  startProcess: "api/jobs/start-job/",
  exportDataSet: "api/uploads/export/dataset/",
  deleteDataset: "api/uploads/datasets/{dataset_id}/delete/",
  datasetDetail: "api/uploads/datasets/{dataset_id}/",
};
