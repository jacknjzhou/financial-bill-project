from django.urls import path

from . import views

urlpatterns = [
    path("login", views.login_view),
    path("logout", views.logout_view),
    path("me", views.me_view),
    path("change-password", views.change_password_view),
    path("csrf", views.csrf_view),
    path("config", views.auth_config_view),
    path("oidc/login", views.oidc_login_view),
    # OIDC 回跳由 allauth 接管：/accounts/{provider_id}/login/callback/（挂载见 financial_bill.urls）
]
