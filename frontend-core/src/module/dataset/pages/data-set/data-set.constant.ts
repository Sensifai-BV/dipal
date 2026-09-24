export const DataSetTableHeaders: Array<{
  text: string;
  field?: any;
  sortable?: boolean;
  styles?: string;
}> = [
  { text: "Name", field: "name", sortable: true, styles: "col-span-3" },
  { text: "Images", field: "total_files", sortable: true, styles: "col-span-1" },
  { text: "Size", field: "total_size", sortable: true, styles: "col-span-2" },
  {
    text: "Uploaded Date",
    field: "created_at",
    sortable: true,
    styles: "col-span-2",
  },
  { text: "Status", field: "status", sortable: true, styles: "col-span-2" },
  { text: "Actions", field: "actions", styles: "text-right" },
];
