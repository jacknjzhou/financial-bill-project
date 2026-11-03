from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash="")
router.register("runs", views.RunViewSet, basename="run")
router.register("reconcile-results", views.ResultViewSet, basename="reconcile-result")

urlpatterns = [
    path("reconcile-projects/<int:project_id>/runs", views.trigger_run_view),
    path("dashboard/overview", views.dashboard_overview_view),
    path("alerts", views.alerts_list_view),
    path("alerts/read", views.alerts_read_view),
    path("", include(router.urls)),
]
