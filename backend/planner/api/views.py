from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.providers.errors import NoRouteError, ProviderError
from planner.providers.geocoding import geocode
from planner.services.heatmap import build_heatmap
from planner.services.plan import plan_trip

from .serializers import HeatmapRequestSerializer, PlanRequestSerializer, serialize_heatmap, serialize_plan

MIN_QUERY_LEN = 3


def _provider_error(exc: ProviderError) -> Response:
    if isinstance(exc, NoRouteError):
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response({"detail": "Upstream service unavailable. Please retry."}, status=status.HTTP_502_BAD_GATEWAY)


class GeocodeView(APIView):
    throttle_scope = "geocode"

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < MIN_QUERY_LEN:
            return Response({"results": []})
        try:
            return Response({"results": geocode(q)})
        except ProviderError as exc:
            return _provider_error(exc)


class PlanView(APIView):
    throttle_scope = "plan"

    def post(self, request):
        req = PlanRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        data = req.validated_data
        try:
            plan = plan_trip(
                origin=(data["origin"]["lat"], data["origin"]["lon"]),
                destination=(data["destination"]["lat"], data["destination"]["lon"]),
                departure=data["departure"],
                load_lb=data["load_lb"],
                interval_mi=data["interval_mi"],
            )
        except ProviderError as exc:
            return _provider_error(exc)
        return Response(serialize_plan(plan))


class HeatmapView(APIView):
    throttle_scope = "heatmap"

    def post(self, request):
        req = HeatmapRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            heatmap = build_heatmap(req.validated_data["lines"], req.validated_data["load_lb"])
        except ProviderError as exc:
            return _provider_error(exc)
        return Response(serialize_heatmap(heatmap))
