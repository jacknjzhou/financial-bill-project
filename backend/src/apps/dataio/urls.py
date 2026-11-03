from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash="")
router.register("payments", views.PaymentQueryViewSet, basename="payments")
router.register("clearings", views.ClearingQueryViewSet, basename="clearings")
router.register("settlements", views.SettlementQueryViewSet, basename="settlements")

urlpatterns = [
    path("files", views.files_collection_view),
    path("files/<int:pk>/download", views.download_file_view),
    path("", include(router.urls)),
]
