export interface BaseTableProps<T> {
  headers: Array<header<T>>;
  data: Array<T>;
  loading?: boolean;
  hasMore?: string | null;
  dataRowCount: number;
  hidePagination?: boolean;
  initialPageSize?: number;
}

interface header<T> {
  text: string;
  field?: keyof T;
  sortable?: boolean;
  styles?: string;
  span?: number;
}

export interface BaseTableEmits<T> {
  (e: "sort", field: keyof T): void;
  (e: "loadMore"): void;
  (e: "change", page: number, pageSize: number): void | Promise<void>;
}
