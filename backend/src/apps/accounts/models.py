from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户：角色 + 强制改密标志（规格 §6）。

    角色语义：
    - admin：全权限（含用户管理 / 基础配置写 / 解析规则写）
    - operator：业务全权限，无系统管理与解析规则写（后端按端点权限卡，前端隐藏菜单）

    is_staff / is_superuser 保留用于 Django admin 救援入口，不参与业务鉴权。
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        OPERATOR = "operator", "对账员"

    role = models.CharField("角色", max_length=16, choices=Role.choices, default=Role.OPERATOR)
    must_change_password = models.BooleanField("强制改密中", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN
