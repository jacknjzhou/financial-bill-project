"""统一错误信封：{"error": {"code", "message", "details"}}（规格 §11）。"""
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ApiError(Exception):
    """业务异常基类：视图层 raise，由 recon_exception_handler 统一转信封。"""

    status_code = 500
    code = "INTERNAL"
    message = "服务器内部错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status: int | None = None,
        details=None,
    ) -> None:
        self.message = message or self.message
        if code is not None:
            self.code = code
        if status is not None:
            self.status_code = status
        self.details = details
        super().__init__(self.message)

    def to_response(self) -> Response:
        return Response(
            {"error": {"code": self.code, "message": self.message, "details": self.details}},
            status=self.status_code,
        )


class ValidationError(ApiError):
    status_code = 400
    code = "VALIDATION"
    message = "参数或数据不合法"


class NotFoundError(ApiError):
    status_code = 404
    code = "NOT_FOUND"
    message = "资源不存在"


class BusinessRuleError(ApiError):
    """业务规则冲突（409）：如同日已有 run、重复上传、唯一约束。"""

    status_code = 409
    code = "BUSINESS_RULE"
    message = "业务规则不允许该操作"


def _flatten(detail):
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_flatten(x) for x in detail]
    return str(detail)


def recon_exception_handler(exc, context):
    """全局异常 → 统一信封；未识别异常回退 DRF 默认（500）。"""
    if isinstance(exc, ApiError):
        return exc.to_response()
    if isinstance(exc, exceptions.ValidationError):
        return Response(
            {"error": {"code": "VALIDATION", "message": "请求参数不合法", "details": _flatten(exc.detail)}},
            status=400,
        )
    if isinstance(exc, exceptions.NotAuthenticated):
        return Response(
            {"error": {"code": "UNAUTHORIZED", "message": "未登录或会话已过期", "details": None}},
            status=401,
        )
    if isinstance(exc, exceptions.PermissionDenied):
        detail = _flatten(exc.detail)
        if "CSRF" in str(exc.detail):
            return Response(
                {
                    "error": {
                        "code": "CSRF_FAILED",
                        "message": "CSRF 校验失败，请刷新页面重试",
                        "details": detail,
                    }
                },
                status=403,
            )
        return Response(
            {"error": {"code": "FORBIDDEN", "message": "权限不足", "details": detail}},
            status=403,
        )
    if isinstance(exc, exceptions.NotFound):
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "资源不存在", "details": None}},
            status=404,
        )
    return exception_handler(exc, context)
