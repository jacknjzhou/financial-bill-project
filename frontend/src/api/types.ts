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
  count: number;
  results: T[];
}
