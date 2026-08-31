"""
Campus geofencing: complaints may only be tagged inside the DSVV campus.

The boundary is the real OpenStreetMap outline of the university
(way/1152422760), stored as `constants.CAMPUS_POLYGON`. Validation uses the
padded bounding box around it so ordinary GPS drift near the fence still
passes, while another city never does.
"""

import pytest

from constants import CAMPUS_BOUNDS, CAMPUS_CENTER, CAMPUS_POLYGON
from utils.validators import in_campus_bounds, point_in_polygon, validate_location


# Points that must be accepted: the centre and a few polygon interior points.
ON_CAMPUS = [
    (CAMPUS_CENTER["latitude"], CAMPUS_CENTER["longitude"]),
    (29.9994, 78.1937),   # near the OSM-reported centroid
    (30.0010, 78.1940),   # northern half of the campus
    (29.9975, 78.1955),   # eastern arm
]

# Points that must be rejected, at increasing distance from campus.
OFF_CAMPUS = [
    (29.9457, 78.1642),   # the project's previous centre, ~6.5 km south-west
    (29.9800, 78.1800),   # between that point and the campus, still outside
    (28.6139, 77.2090),   # New Delhi
    (19.0760, 72.8777),   # Mumbai
    (0.0, 0.0),           # null island - the classic bad default
]


def _location(latitude, longitude, address="Gayatri Bhavan, Room 214"):
    return {"latitude": latitude, "longitude": longitude, "address": address}


class TestCampusPolygon:
    def test_polygon_is_closed(self):
        assert CAMPUS_POLYGON[0] == CAMPUS_POLYGON[-1]

    def test_centre_is_inside_the_polygon(self):
        assert point_in_polygon(CAMPUS_CENTER["latitude"], CAMPUS_CENTER["longitude"])

    def test_bounds_contain_every_polygon_vertex(self):
        for latitude, longitude in CAMPUS_POLYGON:
            assert CAMPUS_BOUNDS["minLatitude"] <= latitude <= CAMPUS_BOUNDS["maxLatitude"]
            assert CAMPUS_BOUNDS["minLongitude"] <= longitude <= CAMPUS_BOUNDS["maxLongitude"]

    @pytest.mark.parametrize("latitude,longitude", OFF_CAMPUS)
    def test_far_points_are_outside_the_polygon(self, latitude, longitude):
        assert not point_in_polygon(latitude, longitude)


class TestCampusBounds:
    @pytest.mark.parametrize("latitude,longitude", ON_CAMPUS)
    def test_campus_points_pass(self, latitude, longitude):
        assert in_campus_bounds(latitude, longitude)

    @pytest.mark.parametrize("latitude,longitude", OFF_CAMPUS)
    def test_off_campus_points_fail(self, latitude, longitude):
        assert not in_campus_bounds(latitude, longitude)


class TestValidateLocation:
    @pytest.mark.parametrize("latitude,longitude", ON_CAMPUS)
    def test_campus_location_is_valid(self, latitude, longitude):
        assert validate_location(_location(latitude, longitude)) == {}

    @pytest.mark.parametrize("latitude,longitude", OFF_CAMPUS)
    def test_off_campus_location_is_rejected(self, latitude, longitude):
        errors = validate_location(_location(latitude, longitude))
        assert "location" in errors
        assert "DSVV campus" in errors["location"]

    def test_missing_coordinates_still_report_the_original_message(self):
        errors = validate_location(_location(None, None))
        assert errors["location"] == "Capture or enter the complaint location"

    def test_missing_address_still_reported_for_a_campus_point(self):
        errors = validate_location(_location(*ON_CAMPUS[0], address="   "))
        assert errors == {"address": "Enter a landmark or building name"}

    def test_out_of_range_coordinates_keep_their_own_message(self):
        errors = validate_location(_location(120.0, 500.0))
        assert errors["location"] == "Coordinates are out of range"


class TestComplaintApiRejectsOffCampus:
    """The geofence must hold at the API, not just in the browser."""

    def test_submission_outside_campus_is_rejected(self, client, student_token):
        response = client.post(
            "/api/complaints",
            json={
                "title": "Broken street light near my house",
                "description": "The light outside my home has been off for a week now.",
                "category": "Electrical",
                "department": "Vidyut Vibhag",
                "location": _location(28.6139, 77.2090, "Connaught Place, New Delhi"),
            },
            headers={"Authorization": f"Bearer {student_token}"},
        )
        # 422 is this API's validation-failure code (see test_complaints.py).
        assert response.status_code == 422
        body = response.get_json()
        assert "DSVV campus" in str(body)
