from rest_framework.routers import DefaultRouter

from .views import DisputeViewSet

router = DefaultRouter(trailing_slash="")
router.register("disputes", DisputeViewSet, basename="dispute")

urlpatterns = router.urls
