from datetime import datetime

from rest_framework import serializers

from .models import Trip

HEADER_FIELDS = (
    "driver_name", "co_driver_name", "carrier_name", "main_office_address",
    "home_terminal_address", "tractor_number", "trailer_number",
    "shipper_name", "commodity", "shipping_doc_number",
)


class TripCreateSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=255)
    pickup_location = serializers.CharField(max_length=255)
    dropoff_location = serializers.CharField(max_length=255)
    current_cycle_used_h = serializers.FloatField(min_value=0, max_value=70)
    departure_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    use_split_sleeper = serializers.BooleanField(required=False, default=False)

    driver_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    co_driver_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    carrier_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    main_office_address = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    home_terminal_address = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    tractor_number = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")
    trailer_number = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")
    shipper_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    commodity = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    shipping_doc_number = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")

    def validate(self, attrs):
        if not attrs.get("departure_at"):
            attrs["departure_at"] = datetime.now().replace(second=0, microsecond=0)
        return attrs


class TripListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = (
            "id", "created_at", "current_location", "pickup_location", "dropoff_location",
            "current_cycle_used_h", "departure_at", "use_split_sleeper",
            "total_miles", "total_drive_hours", "total_duty_hours", "total_days",
            "num_stops", "num_restarts", "route_is_estimate", "compliance_ok",
        )
