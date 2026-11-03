from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health(request):
    """存活探针：数据库不可用时 503（供 compose healthcheck / 运维）。"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001 —— 探针要吞掉一切异常
        db_ok = False
    return JsonResponse(
        {"status": "ok" if db_ok else "degraded", "db": db_ok},
        status=200 if db_ok else 503,
    )


urlpatterns = [
    path("api/health", health),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.meta.urls")),
    path("api/v1/", include("apps.rules.urls")),
    # OpenAPI 在线文档（挂 /api 级，不进 /api/v1）：Swagger UI 可试调 / ReDoc 只读
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# SSO 开启时才挂 allauth 模板流程（/accounts/{provider_id}/login/ 与回跳 callback）
if settings.OIDC_ENABLED:
    urlpatterns.append(path("accounts/", include("allauth.urls")))
