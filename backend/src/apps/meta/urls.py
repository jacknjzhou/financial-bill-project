from rest_framework.routers import DefaultRouter

from .views import BizTypeViewSet, ChannelViewSet, DisputeTypeViewSet, FundAccountViewSet

router = DefaultRouter(trailing_slash="")
router.register("channels", ChannelViewSet, basename="channel")
router.register("fund-accounts", FundAccountViewSet, basename="fund-account")
router.register("biz-types", BizTypeViewSet, basename="biz-type")
router.register("dispute-types", DisputeTypeViewSet, basename="dispute-type")

urlpatterns = router.urls
