from rest_framework.routers import DefaultRouter

from .views import FetchTaskViewSet, ParseRuleViewSet, ReconcileProjectViewSet

router = DefaultRouter(trailing_slash="")
router.register("parse-rules", ParseRuleViewSet, basename="parse-rule")
router.register("fetch-tasks", FetchTaskViewSet, basename="fetch-task")
router.register("reconcile-projects", ReconcileProjectViewSet, basename="reconcile-project")

urlpatterns = router.urls
