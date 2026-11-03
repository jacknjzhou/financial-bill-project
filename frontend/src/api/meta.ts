import { http } from "./client";
import type { PageResp } from "./types";

/** 基础字典通用 CRUD（channels/fund-accounts/biz-types/dispute-types）。 */
export function crudApi<T>(resource: string) {
  return {
    list: (page = 1, pageSize = 20) =>
      http.get<PageResp<T>>(`/${resource}`, { params: { page, page_size: pageSize } }).then((r) => r.data),
    create: (data: Partial<T>) => http.post<T>(`/${resource}`, data).then((r) => r.data),
    update: (id: number, data: Partial<T>) => http.patch<T>(`/${resource}/${id}`, data).then((r) => r.data),
    remove: (id: number) => http.delete(`/${resource}/${id}`),
  };
}

export const channelApi = crudApi("channels");
export const fundAccountApi = crudApi("fund-accounts");
export const bizTypeApi = crudApi("biz-types");
export const disputeTypeApi = crudApi("dispute-types");
