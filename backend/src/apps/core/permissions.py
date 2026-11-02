from rest_framework.permissions import BasePermission


class RoleRequired(BasePermission):
    """仅允许指定角色（与 IsAuthenticated 组合使用；未登录由后者拦截）。"""

    message = "权限不足"

    def __init__(self, roles) -> None:
        self.roles = set(roles)

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user.is_authenticated and user.role in self.roles)


class IsAdmin(RoleRequired):
    def __init__(self) -> None:
        super().__init__(["admin"])


class IsAdminOrOperator(RoleRequired):
    def __init__(self) -> None:
        super().__init__(["admin", "operator"])
