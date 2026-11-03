import { http } from "./client";
import type { ReconcileRun } from "./engine";

export interface Overview {
  reconcile_date: string;
  runs: ReconcileRun[];
  pending_disputes: number;
  alerts_unread: number;
  failed_runs: ReconcileRun[];
}

export interface AlertRow {
  id: number;
  project_name: string;
  reconcile_date: string;
  kind: "failed" | "dispute";
  message: string;
  read: boolean;
  created_at: string;
}

export const dashboardApi = {
  overview: () => http.get<Overview>("/dashboard/overview").then((r) => r.data),
  alerts: (all = false) => http.get<AlertRow[]>("/alerts", { params: all ? { all: 1 } : {} }).then((r) => r.data),
  markRead: (id?: number) => http.post("/alerts/read", id ? { id } : {}).then((r) => r.data),
};
