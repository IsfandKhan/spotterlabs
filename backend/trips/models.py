from django.db import models


class Trip(models.Model):
    """One planned trip.

    Queryable summary columns drive the history list; ``payload`` holds the full
    plan_trip() response (route geometry, timeline, stops, per-day log sheets,
    compliance) so GET-by-id is a straight read with no reconstruction.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    # inputs
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used_h = models.FloatField()
    departure_at = models.DateTimeField()
    use_split_sleeper = models.BooleanField(default=False)

    # optional §395.8 log-header fields
    driver_name = models.CharField(max_length=255, blank=True)
    co_driver_name = models.CharField(max_length=255, blank=True)
    carrier_name = models.CharField(max_length=255, blank=True)
    main_office_address = models.CharField(max_length=255, blank=True)
    home_terminal_address = models.CharField(max_length=255, blank=True)
    tractor_number = models.CharField(max_length=64, blank=True)
    trailer_number = models.CharField(max_length=64, blank=True)
    shipper_name = models.CharField(max_length=255, blank=True)
    commodity = models.CharField(max_length=255, blank=True)
    shipping_doc_number = models.CharField(max_length=128, blank=True)

    # computed summary (for the history list)
    total_miles = models.FloatField(default=0)
    total_drive_hours = models.FloatField(default=0)
    total_duty_hours = models.FloatField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    num_stops = models.PositiveIntegerField(default=0)
    num_restarts = models.PositiveIntegerField(default=0)
    route_is_estimate = models.BooleanField(default=False)
    compliance_ok = models.BooleanField(default=True)

    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pickup_location} -> {self.dropoff_location} ({self.created_at:%Y-%m-%d})"
