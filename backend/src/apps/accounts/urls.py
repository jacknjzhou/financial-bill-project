from django.urls import path

from . import views

urlpatterns = [
    path("login", views.login_view),
    path("logout", views.logout_view),
    path("me", views.me_view),
    path("change-password", views.change_password_view),
    path("csrf", views.csrf_view),
    # T2B：config / oidc/login / oidc/callback
]
