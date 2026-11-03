"""用户管理路由（挂 /api/v1/users，避免与 auth/ 前缀混淆）。"""
from rest_framework.routers import DefaultRouter

from .admin_views import UserAdminViewSet

router = DefaultRouter(trailing_slash="")
router.register("users", UserAdminViewSet, basename="user")

urlpatterns = router.urls
