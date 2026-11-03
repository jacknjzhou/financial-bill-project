import { http } from "./client";
import type { PageResp } from "./types";

export interface ParseRule {
  id?: number;
  name: string;
  target: "payment" | "clearing" | "settlement";
  file_format: "xlsx" | "csv" | "txt";
  encoding: string;
  delimiter: string;
  header_row: number;
  column_map: Record<string, string>;
  value_maps: Record<string, Record<string, string>>;
  amount_scale: number;
  time_format: string;
}

export interface FetchTask {
  id?: number;
  name: string;
  side: "platform" | "channel";
  channel?: number | null;
  account?: number | null;
  parse_rule: number;
  mode?: string;
  channel_name?: string;
  account_name?: string;
  parse_rule_name?: string;
}

export interface FilterCond {
  field: string;
  op: "eq" | "in" | "neq";
  value: string;
}

export interface ReconcileProject {
  id?: number;
  name: string;
  type: "transaction" | "fund" | "balance";
  a_source: string;
  a_filter: FilterCond[];
  b_source: string;
  b_filter: FilterCond[];
  match_key: string;
  a_status_set: string[];
  b_status_set: string[];
  b_sum: boolean;
  start_date: string;
  last_date?: string | null;
  exec_time: string;
  alert_users?: number[];
  enabled: boolean;
}

export const parseRuleApi = {
  list: (page = 1, pageSize = 20) =>
    http.get<PageResp<ParseRule>>("/parse-rules", { params: { page, page_size: pageSize } }).then((r) => r.data),
  get: (id: number) => http.get<ParseRule>(`/parse-rules/${id}`).then((r) => r.data),
  create: (data: ParseRule) => http.post<ParseRule>("/parse-rules", data).then((r) => r.data),
  update: (id: number, data: ParseRule) => http.patch<ParseRule>(`/parse-rules/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/parse-rules/${id}`),
};

export const fetchTaskApi = {
  list: (page = 1, pageSize = 20) =>
    http.get<PageResp<FetchTask>>("/fetch-tasks", { params: { page, page_size: pageSize } }).then((r) => r.data),
  create: (data: FetchTask) => http.post<FetchTask>("/fetch-tasks", data).then((r) => r.data),
  update: (id: number, data: FetchTask) => http.patch<FetchTask>(`/fetch-tasks/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/fetch-tasks/${id}`),
};

export const projectApi = {
  list: (page = 1, pageSize = 20) =>
    http.get<PageResp<ReconcileProject>>("/reconcile-projects", { params: { page, page_size: pageSize } }).then((r) => r.data),
  get: (id: number) => http.get<ReconcileProject>(`/reconcile-projects/${id}`).then((r) => r.data),
  create: (data: ReconcileProject) => http.post<ReconcileProject>("/reconcile-projects", data).then((r) => r.data),
  update: (id: number, data: ReconcileProject) =>
    http.patch<ReconcileProject>(`/reconcile-projects/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/reconcile-projects/${id}`),
};
