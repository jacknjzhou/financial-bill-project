import { http } from "./client";
import type { PageResp } from "./types";

export interface DisputeRow {
  id: number;
  project: number;
  project_name: string;
  reconcile_date: string;
  type: "one_a" | "one_b" | "wrong";
  a: number | null;
  b: number | null;
  order_no: string;
  amount: number;
  amount_yuan: string;
  status: "open" | "processing" | "closed";
  dispute_type: number | null;
  dispute_type_name: string;
  handler_name: string;
  handled_at: string | null;
  remark: string;
  superseded: boolean;
  group_no: string;
}

export interface HandleLogRow {
  id: number;
  action: string;
  operator_name: string;
  from_status: string;
  to_status: string;
  remark: string;
  created_at: string;
}

export const disputeApi = {
  list: (params: { project?: number; reconcile_date?: string; status?: string; type?: string; page?: number; page_size?: number }) =>
    http.get<PageResp<DisputeRow>>("/disputes", { params }).then((r) => r.data),
  handle: (id: number, data: { dispute_type_id: number; remark: string; to_processing?: boolean }) =>
    http.post<DisputeRow>(`/disputes/${id}/handle`, data).then((r) => r.data),
  logs: (id: number) => http.get<{ total: number; items: HandleLogRow[] }>(`/disputes/${id}/logs`).then((r) => r.data),
};
