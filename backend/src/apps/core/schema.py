"""OpenAPI 全局约定（规格：全部端点必须有类型化 schema）。

- PageResponse：统一分页信封 {total,page,page_size,items}，配套 ReconPagination。
- paginate(ser_cls, label)：列表端点的 @extend_schema 装饰器工厂，items 内联元素结构。
- 全局约定：状态/类型参数用 Choice 枚举、金额 int64（分）+描述、日期 ISO、
  查询参数用 extend_schema 显式声明——新增端点不带完整 schema 视为不合格。
"""
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ReconPagination(PageNumberPagination):
    """统一分页：PageResponse 信封（items 承载当前页数据）。"""

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


class PageResponse(serializers.Serializer):
    """分页信封（items 元素结构由 paginate() 内联展开）。"""

    total = serializers.IntegerField(help_text="总条数")
    page = serializers.IntegerField(help_text="当前页码（1 起）")
    page_size = serializers.IntegerField(help_text="每页条数")
    items = serializers.ListField(help_text="当前页数据")


def paginate(ser_cls, label: str):
    """列表端点装饰器工厂：响应 schema = PageResponse 信封 + items: ser_cls[]。"""
    from drf_spectacular.utils import inline_serializer

    page_ser = inline_serializer(
        label,
        fields={
            "total": serializers.IntegerField(),
            "page": serializers.IntegerField(),
            "page_size": serializers.IntegerField(),
            "items": ser_cls(many=True),
        },
    )

    def decorator(view):
        from drf_spectacular.utils import extend_schema

        return extend_schema(responses={200: page_ser})(view)

    return decorator
