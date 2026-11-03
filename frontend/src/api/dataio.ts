import { http } from "./client";
import type { PageResp } from "./types";
import type { FetchTask } from "./rules";

export interface InFile {
  id: number;
  fetch_task: number;
  fetch_task_name: string;
  file_name: string;
  size: number;
  size_mb: number;
  status: "pending" | "parsing" | "parsed" | "failed";
  total_rows: number;
  failed_rows: number;
  error_msg: string;
  uploaded_by_name: string;
  created_at: string;
  created_date: string;
}

export interface PaymentRow {
  id: number;
  order_no: string;
  pay_no: string;
  channel_name: string;
  biz_type_code: string;
  amount: number; // 分
  amount_yuan: string;
  status: string;
  tx_time: string | null;
  reconcile_date: string;
}

export interface ClearingRow extends Omit<PaymentRow, "pay_no"> {
  channel_order_no: string;
  order_no: string;
}

export interface SettlementRow {
  id: number;
  fee_item: string;
  amount: number;
  fee_amount: number | null;
  actual_amount: number | null;
  settle_date: string;
  reconcile_date: string;
}

export const filesApi = {
  list: (params: { fetch_task?: number; status?: string; page?: number; page_size?: number }) =>
    http.get<PageResp<InFile>>("/files", { params }).then((r) => r.data),
  upload: (taskId: number, file: File, overwrite = false) => {
    const form = new FormData();
    form.append("fetch_task", String(taskId));
    form.append("file", file);
    return http.post<InFile>(`/files${overwrite ? "?overwrite=true" : ""}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
  downloadUrl: (id: number) => `/api/v1/files/${id}/download`,
};

function queryApi<T>(resource: string) {
  return {
    list: (params: Record<string, string | number | undefined>) =>
      http.get<PageResp<T>>(`/${resource}`, { params }).then((r) => r.data),
  };
}

export const paymentsApi = queryApi<PaymentRow>("payments");
export const clearingsApi = queryApi<ClearingRow>("clearings");
export const settlementsApi = queryApi<SettlementRow>("settlements");
export type { FetchTask };
