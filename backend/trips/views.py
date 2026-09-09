from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Trip
from .serializers import HEADER_FIELDS, TripCreateSerializer, TripListSerializer
from .services import geocode
from .services.planner import PlanInput, plan_trip


class TripListCreate(ListAPIView):
    """GET  /api/trips        history list (paginated)
    POST /api/trips        plan + persist a new trip, return the full result
    """

    queryset = Trip.objects.all()
    serializer_class = TripListSerializer

    def post(self, request):
        s = TripCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        try:
            payload = plan_trip(PlanInput(
                current_location=data["current_location"],
                pickup_location=data["pickup_location"],
                dropoff_location=data["dropoff_location"],
                current_cycle_used_h=data["current_cycle_used_h"],
                departure_at=data["departure_at"],
                use_split_sleeper=data["use_split_sleeper"],
            ))
        except geocode.GeocodeError as exc:
            return Response({"error": f"Could not locate an address: {exc}"},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        header = {f: data.get(f, "") for f in HEADER_FIELDS}
        payload["header"] = header

        trip = Trip.objects.create(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used_h=data["current_cycle_used_h"],
            departure_at=data["departure_at"],
            use_split_sleeper=data["use_split_sleeper"],
            total_miles=payload["summary"]["total_miles"],
            total_drive_hours=payload["summary"]["total_drive_hours"],
            total_duty_hours=payload["summary"]["total_duty_hours"],
            total_days=payload["summary"]["total_days"],
            num_stops=payload["summary"]["num_stops"],
            num_restarts=payload["summary"]["num_restarts"],
            route_is_estimate=payload["route"]["is_estimate"],
            compliance_ok=payload["compliance"]["ok"],
            payload=payload,
            **header,
        )
        return Response(_detail(trip), status=status.HTTP_201_CREATED)


class TripDetail(APIView):
    def get(self, _request, pk):
        try:
            trip = Trip.objects.get(pk=pk)
        except Trip.DoesNotExist:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_detail(trip))


def _detail(trip: Trip) -> dict:
    return {"id": trip.id, "created_at": trip.created_at.isoformat(), **trip.payload}
