import { http } from "./client";
import type { PageResp } from "./types";

export interface ReconcileRun {
  id: number;
  project: number;
  project_name: string;
  reconcile_date: string;
  status: "pending" | "running" | "success" | "failed";
  a_total: number;
  b_total: number;
  match_cnt: number;
  one_a_cnt: number;
  one_b_cnt: number;
  wrong_cnt: number;
  trigger: "auto" | "manual" | "rerun";
  triggered_by_name: string;
  started_at: string | null;
  finished_at: string | null;
  error: string;
}

export const runApi = {
  list: (params: { project?: number; status?: string; reconcile_date?: string; page?: number; page_size?: number }) =>
    http.get<PageResp<ReconcileRun>>("/runs", { params }).then((r) => r.data),
  trigger: (projectId: number, data: { date?: string; rerun?: boolean }) =>
    http.post<{ run_id: number }>(`/reconcile-projects/${projectId}/runs`, data).then((r) => r.data),
};
