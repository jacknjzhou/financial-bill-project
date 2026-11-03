import { http } from "./client";
import type { PageResp } from "./types";

export interface ReconcileResultRow {
  id: number;
  run: number;
  project_name: string;
  reconcile_date: string;
  status: "match" | "one_a" | "one_b" | "wrong";
  a: number | null;
  b: number | null;
  order_no: string;
  match_key: string;
  diff_amount: number;
  diff_amount_yuan: string;
  diff_type: "none" | "amount" | "status" | "both";
  group_no: string;
  biz_type: number | null;
}

export interface ResultDetail {
  result: ReconcileResultRow;
  a_row: Record<string, unknown> | null;
  b_rows: Array<Record<string, unknown>>;
}

export const resultApi = {
  list: (params: { project?: number; date?: string; status?: string; page?: number; page_size?: number }) =>
    http.get<PageResp<ReconcileResultRow>>("/reconcile-results", { params }).then((r) => r.data),
  get: (id: number) => http.get<ResultDetail>(`/reconcile-results/${id}`).then((r) => r.data),
};
