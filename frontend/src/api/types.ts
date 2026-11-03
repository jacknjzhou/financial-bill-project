/** 与后端统一错误信封对应的类型（规格 §11）。 */
export interface ErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown | null;
  };
}

export type Role = "admin" | "operator";

export interface UserInfo {
  id: number;
  username: string;
  role: Role;
  must_change_password: boolean;
  is_active: boolean;
  created_at: string;
}

export interface LoginResp {
  user: UserInfo;
  must_change_password: boolean;
}

export interface PageResp<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

/* ===== 基础配置（T4） ===== */
export interface Channel {
  id: number;
  code: string;
  name: string;
  enabled: boolean;
}

export interface FundAccount {
  id: number;
  channel: number;
  channel_name?: string;
  name: string;
  account_no: string;
  start_date: string; // ISO 日期
  start_balance: number; // 单位：分
  enabled: boolean;
}

export interface BizType {
  id: number;
  code: string;
  name: string;
  group: "INCOME" | "REFUND" | "FEE";
}

export interface DisputeType {
  id: number;
  group: "TRANSACTION" | "FUND";
  name: string;
  description: string;
}
