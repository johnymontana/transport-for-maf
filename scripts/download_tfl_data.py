"""Download TfL data from the Unified API.

Usage:
    python download_tfl_data.py --all
    python download_tfl_data.py --stations --lines --routes --bikepoints
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = "https://api.tfl.gov.uk"
DATA_DIR = Path(__file__).parent.parent / "data"
MODES = "tube,dlr,overground,elizabeth-line"

# TfL line colors for reference
TFL_LINE_COLORS = {
    "bakerloo": "#B36305",
    "central": "#E32017",
    "circle": "#FFD300",
    "district": "#00782A",
    "hammersmith-city": "#F3A9BB",
    "jubilee": "#A0A5A9",
    "metropolitan": "#9B0056",
    "northern": "#000000",
    "piccadilly": "#003688",
    "victoria": "#0098D4",
    "waterloo-city": "#95CDBA",
    "elizabeth": "#6950A1",
    "london-overground": "#EE7C0E",
    "dlr": "#00A4A7",
}


def get_params() -> dict[str, str]:
    """Get query params including optional app key."""
    params = {}
    app_key = os.getenv("TFL_APP_KEY")
    if app_key:
        params["app_key"] = app_key
    return params


async def download_stations(client: httpx.AsyncClient) -> None:
    """Download all rail stations."""
    print("Downloading stations...")
    resp = await client.get(
        f"{BASE_URL}/StopPoint/Mode/{MODES}",
        params=get_params(),
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract relevant fields
    stations = []
    for stop in data.get("stopPoints", data) if isinstance(data, dict) else data:
        # Handle paginated response
        if isinstance(stop, dict) and "naptanId" in stop:
            station = {
                "naptanId": stop["naptanId"],
                "commonName": stop["commonName"],
                "lat": stop["lat"],
                "lon": stop["lon"],
                "modes": stop.get("modes", []),
                "zone": _extract_zone(stop),
                "lines": [
                    {"id": line["id"], "name": line["name"]}
                    for line in stop.get("lines", [])
                ],
            }
            stations.append(station)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "stations.json").write_text(json.dumps(stations, indent=2))
    print(f"  Saved {len(stations)} stations to data/stations.json")


# Parent-level stop types (not platforms, entrances, or access areas)
PARENT_STOP_TYPES = {
    "NaptanMetroStation",
    "NaptanRailStation",
    "TransportInterchange",
}


async def download_stations_paginated(client: httpx.AsyncClient) -> None:
    """Download all rail stations using paginated StopPoint endpoint.

    Filters to parent-level station types only (not platforms/entrances)
    so naptanIds match those used in the Route Sequence API.
    """
    print("Downloading stations (paginated)...")
    all_stations = []
    seen_ids = set()
    page = 1

    while True:
        params = {**get_params(), "page": str(page)}
        resp = await client.get(
            f"{BASE_URL}/StopPoint/Mode/{MODES}",
            params=params,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        stop_points = data.get("stopPoints", []) if isinstance(data, dict) else data
        if not stop_points:
            break

        for stop in stop_points:
            if not isinstance(stop, dict) or "naptanId" not in stop:
                continue
            # Only keep parent-level stations
            stop_type = stop.get("stopType", "")
            if stop_type not in PARENT_STOP_TYPES:
                continue
            nid = stop["naptanId"]
            if nid in seen_ids:
                continue
            seen_ids.add(nid)

            station = {
                "naptanId": nid,
                "commonName": stop["commonName"],
                "lat": stop["lat"],
                "lon": stop["lon"],
                "modes": stop.get("modes", []),
                "zone": _extract_zone(stop),
                "lines": [
                    {"id": line["id"], "name": line["name"]}
                    for line in stop.get("lines", [])
                ],
            }
            all_stations.append(station)

        total = data.get("total", 0) if isinstance(data, dict) else 0
        page_size = data.get("pageSize", 1000) if isinstance(data, dict) else 1000
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        print(f"  Page {page}/{total_pages} - {len(stop_points)} stops ({len(all_stations)} parent stations)")
        if page >= total_pages:
            break
        page += 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "stations.json").write_text(json.dumps(all_stations, indent=2))
    print(f"  Saved {len(all_stations)} stations to data/stations.json")


def _extract_zone(stop: dict) -> str | None:
    """Extract zone from stop point additional properties."""
    for prop in stop.get("additionalProperties", []):
        if prop.get("key") == "Zone":
            return prop.get("value")
    return None


async def download_lines(client: httpx.AsyncClient) -> None:
    """Download all rail lines."""
    print("Downloading lines...")
    resp = await client.get(
        f"{BASE_URL}/Line/Mode/{MODES}",
        params=get_params(),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()

    lines = []
    for line in data:
        lines.append({
            "id": line["id"],
            "name": line["name"],
            "modeName": line["modeName"],
            "color": TFL_LINE_COLORS.get(line["id"], "#888888"),
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "lines.json").write_text(json.dumps(lines, indent=2))
    print(f"  Saved {len(lines)} lines to data/lines.json")


async def download_routes(client: httpx.AsyncClient) -> None:
    """Download route sequences for each line."""
    print("Downloading route sequences...")

    # First load lines
    lines_file = DATA_DIR / "lines.json"
    if not lines_file.exists():
        print("  Lines data not found, downloading lines first...")
        await download_lines(client)

    lines = json.loads(lines_file.read_text())
    routes_dir = DATA_DIR / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)

    for line in lines:
        line_id = line["id"]
        print(f"  Downloading route for {line['name']}...")
        try:
            resp = await client.get(
                f"{BASE_URL}/Line/{line_id}/Route/Sequence/outbound",
                params=get_params(),
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract station sequences from stopPointSequences
            sequences = []
            for seq in data.get("stopPointSequences", []):
                stop_points = seq.get("stopPoint", [])
                branch_id = seq.get("branchId", 0)
                sequence = []
                for i, sp in enumerate(stop_points):
                    sequence.append({
                        "naptanId": sp.get("stationId", sp.get("id", "")),
                        "name": sp.get("name", ""),
                        "lat": sp.get("lat", 0),
                        "lon": sp.get("lon", 0),
                        "sequence": i,
                    })
                if sequence:
                    sequences.append({
                        "branchId": branch_id,
                        "stops": sequence,
                    })

            route_data = {
                "lineId": line_id,
                "lineName": line["name"],
                "sequences": sequences,
            }
            (routes_dir / f"{line_id}.json").write_text(json.dumps(route_data, indent=2))
        except httpx.HTTPStatusError as e:
            print(f"  Warning: Could not download route for {line_id}: {e}")
        except Exception as e:
            print(f"  Warning: Error downloading route for {line_id}: {e}")

        # Brief pause to avoid rate limiting
        await asyncio.sleep(0.5)

    print(f"  Saved routes to data/routes/")


async def download_bikepoints(client: httpx.AsyncClient) -> None:
    """Download all cycle hire docking stations."""
    print("Downloading bike points...")
    resp = await client.get(
        f"{BASE_URL}/BikePoint",
        params=get_params(),
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()

    bikepoints = []
    for bp in data:
        props = {p["key"]: p["value"] for p in bp.get("additionalProperties", [])}
        bikepoints.append({
            "id": bp["id"],
            "commonName": bp["commonName"],
            "lat": bp["lat"],
            "lon": bp["lon"],
            "nbDocks": int(props.get("NbDocks", 0)),
            "nbBikes": int(props.get("NbBikes", 0)),
            "nbEmptyDocks": int(props.get("NbEmptyDocks", 0)),
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "bikepoints.json").write_text(json.dumps(bikepoints, indent=2))
    print(f"  Saved {len(bikepoints)} bike points to data/bikepoints.json")


async def main(args: argparse.Namespace) -> None:
    async with httpx.AsyncClient() as client:
        if args.all or args.stations:
            await download_stations_paginated(client)
        if args.all or args.lines:
            await download_lines(client)
        if args.all or args.routes:
            await download_routes(client)
        if args.all or args.bikepoints:
            await download_bikepoints(client)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download TfL data")
    parser.add_argument("--all", action="store_true", help="Download all data")
    parser.add_argument("--stations", action="store_true", help="Download stations")
    parser.add_argument("--lines", action="store_true", help="Download lines")
    parser.add_argument("--routes", action="store_true", help="Download route sequences")
    parser.add_argument("--bikepoints", action="store_true", help="Download bike points")

    args = parser.parse_args()
    if not any([args.all, args.stations, args.lines, args.routes, args.bikepoints]):
        args.all = True

    asyncio.run(main(args))
