"""强制改密闸门：must_change_password 期间会话只允许进入认证白名单端点。

规格 §7：登录 must_change_password=True 后，会话只允许 /auth/change-password、
/auth/logout；/me 放行（前端刷新页面后需据此渲染强制改密对话框）。
"""
from django.http import HttpRequest, HttpResponse, JsonResponse

API_PREFIX = "/api/"
AUTH_PREFIX = "/api/v1/auth/"


class MustChangePasswordGate:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        blocked = (
            user is not None
            and user.is_authenticated
            and getattr(user, "must_change_password", False)
            and request.path.startswith(API_PREFIX)
            and not request.path.startswith(AUTH_PREFIX)
        )
        if blocked:
            return JsonResponse(
                {
                    "error": {
                        "code": "MUST_CHANGE_PASSWORD",
                        "message": "请先修改密码后再继续操作",
                        "details": None,
                    }
                },
                status=403,
            )
        return self.get_response(request)
