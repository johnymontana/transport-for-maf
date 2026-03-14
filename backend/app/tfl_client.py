"""TfL Unified API client for live data."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tfl.gov.uk"


class TfLClient:
    """Async client for the TfL Unified API."""

    def __init__(self, app_key: str | None = None):
        self._app_key = app_key
        self._client = httpx.AsyncClient(timeout=30.0)

    def _params(self) -> dict[str, str]:
        params = {}
        if self._app_key:
            params["app_key"] = self._app_key
        return params

    async def get_line_status(self, line_ids: list[str]) -> list[dict]:
        """Get current status for one or more lines."""
        ids = ",".join(line_ids)
        try:
            resp = await self._client.get(
                f"{BASE_URL}/Line/{ids}/Status",
                params=self._params(),
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "lineId": line["id"],
                    "name": line["name"],
                    "statuses": [
                        {
                            "severity": s["statusSeverity"],
                            "severityDescription": s["statusSeverityDescription"],
                            "reason": s.get("reason"),
                        }
                        for s in line.get("lineStatuses", [])
                    ],
                }
                for line in data
            ]
        except Exception as e:
            logger.warning(f"Error fetching line status: {e}")
            return [{"error": str(e)}]

    async def get_disruptions(self, mode: str = "tube") -> list[dict]:
        """Get current disruptions for a mode."""
        try:
            resp = await self._client.get(
                f"{BASE_URL}/Line/Mode/{mode}/Disruption",
                params=self._params(),
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "description": d.get("description"),
                    "type": d.get("type"),
                    "affectedRoutes": [
                        r.get("name") for r in d.get("affectedRoutes", [])
                    ],
                }
                for d in data
            ]
        except Exception as e:
            logger.warning(f"Error fetching disruptions: {e}")
            return [{"error": str(e)}]

    async def plan_journey(
        self, from_loc: str, to_loc: str
    ) -> dict:
        """Plan a journey between two locations."""
        try:
            resp = await self._client.get(
                f"{BASE_URL}/Journey/JourneyResults/{from_loc}/to/{to_loc}",
                params=self._params(),
            )
            resp.raise_for_status()
            data = resp.json()
            journeys = []
            for j in data.get("journeys", [])[:3]:
                legs = []
                for leg in j.get("legs", []):
                    legs.append({
                        "mode": leg.get("mode", {}).get("name"),
                        "summary": leg.get("instruction", {}).get("summary"),
                        "duration": leg.get("duration"),
                        "departurePoint": leg.get("departurePoint", {}).get("commonName"),
                        "arrivalPoint": leg.get("arrivalPoint", {}).get("commonName"),
                    })
                journeys.append({
                    "duration": j.get("duration"),
                    "legs": legs,
                })
            return {"journeys": journeys}
        except Exception as e:
            logger.warning(f"Error planning journey: {e}")
            return {"error": str(e)}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
