"""统一分页：PageResponse 信封 {total,page,page_size,items}。

独立模块（避免 DRF 设置解析时引入 spectacular 的循环导入）；
信封 schema 由本类声明，drf-spectacular 自动应用于所有 list 端点。
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ReconPagination(PageNumberPagination):
    """统一分页：items 承载当前页数据（PageResponse 信封）。"""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            {
                "total": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "items": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "total": {"type": "integer", "example": 123, "description": "总条数"},
                "page": {"type": "integer", "example": 1, "description": "当前页码（1 起）"},
                "page_size": {"type": "integer", "example": 20, "description": "每页条数"},
                "items": schema,
            },
            "required": ["total", "page", "page_size", "items"],
        }
