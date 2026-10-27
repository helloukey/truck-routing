from django.urls import path

from .views import GeocodeView, HeatmapView, PlanView

urlpatterns = [
    path("geocode", GeocodeView.as_view()),
    path("plan", PlanView.as_view()),
    path("heatmap", HeatmapView.as_view()),
]
