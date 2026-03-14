"""Unit tests for the TfL API client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.tfl_client import TfLClient


@pytest.mark.unit
class TestTfLClient:
    """Test TfLClient with mocked HTTP responses."""

    @pytest.fixture
    def client(self) -> TfLClient:
        return TfLClient(app_key="test-key")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_line_status_success(self, client):
        """Should parse line status response correctly."""
        respx.get("https://api.tfl.gov.uk/Line/northern/Status").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "northern",
                        "name": "Northern",
                        "lineStatuses": [
                            {
                                "statusSeverity": 10,
                                "statusSeverityDescription": "Good Service",
                                "reason": None,
                            }
                        ],
                    }
                ],
            )
        )

        result = await client.get_line_status(["northern"])

        assert len(result) == 1
        assert result[0]["lineId"] == "northern"
        assert result[0]["name"] == "Northern"
        assert result[0]["statuses"][0]["severityDescription"] == "Good Service"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_line_status_multiple_lines(self, client):
        """Should handle multiple line IDs in one request."""
        respx.get("https://api.tfl.gov.uk/Line/northern,victoria/Status").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "northern",
                        "name": "Northern",
                        "lineStatuses": [
                            {"statusSeverity": 10, "statusSeverityDescription": "Good Service"}
                        ],
                    },
                    {
                        "id": "victoria",
                        "name": "Victoria",
                        "lineStatuses": [
                            {"statusSeverity": 5, "statusSeverityDescription": "Minor Delays", "reason": "Signal failure"}
                        ],
                    },
                ],
            )
        )

        result = await client.get_line_status(["northern", "victoria"])
        assert len(result) == 2
        assert result[1]["statuses"][0]["reason"] == "Signal failure"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_line_status_api_error(self, client):
        """Should handle API errors gracefully."""
        respx.get("https://api.tfl.gov.uk/Line/fake/Status").mock(
            return_value=httpx.Response(404, json={"message": "not found"})
        )

        result = await client.get_line_status(["fake"])
        assert len(result) == 1
        assert "error" in result[0]

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_disruptions_success(self, client):
        """Should parse disruption data."""
        respx.get("https://api.tfl.gov.uk/Line/Mode/tube/Disruption").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "description": "Northern line: Minor delays due to signal failure",
                        "type": "lineInfo",
                        "affectedRoutes": [{"name": "Northern"}],
                    }
                ],
            )
        )

        result = await client.get_disruptions("tube")
        assert len(result) == 1
        assert "Northern" in result[0]["description"]
        assert result[0]["affectedRoutes"] == ["Northern"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_disruptions_empty(self, client):
        """Should handle no disruptions."""
        respx.get("https://api.tfl.gov.uk/Line/Mode/tube/Disruption").mock(
            return_value=httpx.Response(200, json=[])
        )

        result = await client.get_disruptions("tube")
        assert result == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_plan_journey_success(self, client):
        """Should parse journey planning results."""
        respx.get(
            "https://api.tfl.gov.uk/Journey/JourneyResults/51.5031,-0.1132/to/51.4627,-0.1145"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "journeys": [
                        {
                            "duration": 15,
                            "legs": [
                                {
                                    "mode": {"name": "tube"},
                                    "instruction": {"summary": "Victoria line to Brixton"},
                                    "duration": 12,
                                    "departurePoint": {"commonName": "Waterloo"},
                                    "arrivalPoint": {"commonName": "Brixton"},
                                }
                            ],
                        }
                    ]
                },
            )
        )

        result = await client.plan_journey("51.5031,-0.1132", "51.4627,-0.1145")
        assert "journeys" in result
        assert result["journeys"][0]["duration"] == 15
        assert result["journeys"][0]["legs"][0]["mode"] == "tube"

    @respx.mock
    @pytest.mark.asyncio
    async def test_plan_journey_error(self, client):
        """Should handle journey planning errors."""
        respx.get(
            "https://api.tfl.gov.uk/Journey/JourneyResults/invalid/to/invalid"
        ).mock(return_value=httpx.Response(400, json={"message": "bad request"}))

        result = await client.plan_journey("invalid", "invalid")
        assert "error" in result

    def test_params_with_app_key(self, client):
        """Should include app_key when set."""
        params = client._params()
        assert params["app_key"] == "test-key"

    def test_params_without_app_key(self):
        """Should return empty params when no key."""
        client = TfLClient(app_key=None)
        params = client._params()
        assert params == {}

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Should close without error."""
        await client.close()
