"""OpenAPI 全局约定（规格：全部端点必须有类型化 schema）。

- 分页信封由 apps.core.pagination.ReconPagination 声明
  （get_paginated_response_schema），spectacular 对所有 list 端点自动套用，
  无需在每个 list 上手写响应——响应形状与实际返回严格一致。
- crud_schema(ser_cls)：ViewSet 标准 CRUD 的 retrieve/create/update/destroy
  schema 装饰器（list 交给分页器自动处理）。
- 全局约定：状态/类型参数用 Choice 枚举、金额 int64（分）+描述、日期 ISO、
  查询参数用 extend_schema 显式声明——新增端点不带完整 schema 视为不合格。
"""
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers

detail_pk = [OpenApiParameter(name="id", type=int, location=OpenApiParameter.PATH)]


def crud_schema(ser_cls, label: str):
    """ViewSet 类装饰器：为 retrieve/create/update/destroy 补类型化 schema。

    注意：不能直接改 viewset_cls.xxx——所有 ModelViewSet 共享 mixin 的同一个
    函数对象，extend_schema 写在其上的 kwargs['schema'] 会相互覆盖。
    这里用 SchemaMixin 生成"每个 viewset 独享"的方法副本。
    """

    class SchemaMixin:
        @extend_schema(parameters=detail_pk, responses={200: ser_cls}, summary="详情")
        def retrieve(self, request, *args, **kwargs):
            return super().retrieve(request, *args, **kwargs)

        @extend_schema(
            request=ser_cls,
            responses={201: ser_cls, 400: OpenApiResponse(response=None), 409: OpenApiResponse(response=None)},
            summary="新增",
        )
        def create(self, request, *args, **kwargs):
            return super().create(request, *args, **kwargs)

        @extend_schema(parameters=detail_pk, request=ser_cls, responses={200: ser_cls}, summary="更新")
        def update(self, request, *args, **kwargs):
            return super().update(request, *args, **kwargs)

        @extend_schema(parameters=detail_pk, request=ser_cls, responses={200: ser_cls}, summary="部分更新")
        def partial_update(self, request, *args, **kwargs):
            return super().partial_update(request, *args, **kwargs)

        @extend_schema(
            parameters=detail_pk,
            responses={204: OpenApiResponse(response=None), 409: OpenApiResponse(response=None)},
            summary="删除（被引用时 409）",
        )
        def destroy(self, request, *args, **kwargs):
            return super().destroy(request, *args, **kwargs)

    def deco(viewset_cls):
        return type(viewset_cls.__name__, (SchemaMixin, viewset_cls), {})

    return deco


def paginate(ser_cls, label: str):
    """函数视图列表端点的 schema 装饰器（信封由分页器自动提供，这里只声明 items 结构）。"""
    page_ser = inline_serializer(
        f"{label}Page",
        fields={"items": ser_cls(many=True)},
    )

    def decorator(view):
        return extend_schema(responses={200: page_ser})(view)

    return decorator
