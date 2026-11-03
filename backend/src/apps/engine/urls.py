from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash="")
router.register("runs", views.RunViewSet, basename="run")

urlpatterns = [
    path("reconcile-projects/<int:project_id>/runs", views.trigger_run_view),
    path("", include(router.urls)),
]
