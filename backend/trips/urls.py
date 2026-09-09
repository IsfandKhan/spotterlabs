from django.urls import path

from .views import TripDetail, TripListCreate

urlpatterns = [
    path("trips", TripListCreate.as_view(), name="trip-list-create"),
    path("trips/<int:pk>", TripDetail.as_view(), name="trip-detail"),
]
