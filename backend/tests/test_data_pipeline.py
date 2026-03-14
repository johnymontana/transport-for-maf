"""Tests for the data download and loading pipeline scripts.

Unit tests mock HTTP/Neo4j calls. Integration tests require a Neo4j instance.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Download script tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDownloadFunctions:
    """Test TfL data download functions."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Temporary data directory."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        return data_dir

    @pytest.mark.asyncio
    async def test_download_stations_saves_json(self, temp_data_dir):
        """download_stations should write stations.json."""
        try:
            from download_tfl_data import download_stations
        except ImportError:
            pytest.skip("download_tfl_data not importable")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"naptanId": "940GZZLUWLO", "commonName": "Waterloo", "lat": 51.5, "lon": -0.11},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("download_tfl_data.DATA_DIR", temp_data_dir):
            await download_stations(mock_client)

        stations_file = temp_data_dir / "stations.json"
        assert stations_file.exists()
        data = json.loads(stations_file.read_text())
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_download_lines_saves_json(self, temp_data_dir):
        """download_lines should write lines.json."""
        try:
            from download_tfl_data import download_lines
        except ImportError:
            pytest.skip("download_tfl_data not importable")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "northern", "name": "Northern", "modeName": "tube"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("download_tfl_data.DATA_DIR", temp_data_dir):
            await download_lines(mock_client)

        lines_file = temp_data_dir / "lines.json"
        assert lines_file.exists()

    @pytest.mark.asyncio
    async def test_download_bikepoints_saves_json(self, temp_data_dir):
        """download_bikepoints should write bikepoints.json."""
        try:
            from download_tfl_data import download_bikepoints
        except ImportError:
            pytest.skip("download_tfl_data not importable")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "BikePoints_1", "commonName": "Test Dock", "lat": 51.5, "lon": -0.1},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("download_tfl_data.DATA_DIR", temp_data_dir):
            await download_bikepoints(mock_client)

        bp_file = temp_data_dir / "bikepoints.json"
        assert bp_file.exists()


# ---------------------------------------------------------------------------
# Load script tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadFunctions:
    """Test Neo4j graph loading functions."""

    @pytest.fixture
    def sample_station_data(self):
        return [
            {
                "naptanId": "940GZZLUWLO",
                "commonName": "Waterloo Underground Station",
                "lat": 51.5031,
                "lon": -0.1132,
                "modes": ["tube"],
                "zone": "1",
                "lines": [{"id": "northern", "name": "Northern"}],
            }
        ]

    @pytest.fixture
    def sample_line_data(self):
        return [
            {"id": "northern", "name": "Northern", "modeName": "tube", "colour": "#000000"},
        ]

    @pytest.mark.asyncio
    async def test_load_stations_executes_cypher(self, sample_station_data, tmp_path):
        """load_stations should run MERGE queries against the driver."""
        try:
            from load_graph import load_stations
        except ImportError:
            pytest.skip("load_graph not importable")

        # Write sample data to temp file
        (tmp_path / "stations.json").write_text(json.dumps(sample_station_data))

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        # Count query session
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"count": 1})
        mock_count_session = AsyncMock()
        mock_count_session.run = AsyncMock(return_value=mock_result)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(side_effect=[mock_ctx, mock_count_session])

        with patch("load_graph.DATA_DIR", tmp_path):
            await load_stations(mock_driver)

        assert mock_session.run.await_count >= 1

    @pytest.mark.asyncio
    async def test_load_lines_executes_cypher(self, sample_line_data, tmp_path):
        """load_lines should run MERGE queries against the driver."""
        try:
            from load_graph import load_lines
        except ImportError:
            pytest.skip("load_graph not importable")

        (tmp_path / "lines.json").write_text(json.dumps(sample_line_data))

        mock_session = AsyncMock()
        mock_session.run = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"count": 1})
        mock_count_session = AsyncMock()
        mock_count_session.run = AsyncMock(return_value=mock_result)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(side_effect=[mock_ctx, mock_count_session])

        with patch("load_graph.DATA_DIR", tmp_path):
            await load_lines(mock_driver)

        assert mock_session.run.await_count >= 1


# ---------------------------------------------------------------------------
# Data file validation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDataFileValidation:
    """Test that downloaded data files have expected structure."""

    DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

    @pytest.fixture(autouse=True)
    def skip_if_no_data(self):
        if not self.DATA_DIR.exists():
            pytest.skip("Data directory not found (run download first)")

    def test_stations_json_structure(self):
        stations_file = self.DATA_DIR / "stations.json"
        if not stations_file.exists():
            pytest.skip("stations.json not downloaded")
        data = json.loads(stations_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0
        # Check first station has required fields
        station = data[0]
        assert "naptanId" in station or "id" in station
        assert "commonName" in station or "name" in station

    def test_lines_json_structure(self):
        lines_file = self.DATA_DIR / "lines.json"
        if not lines_file.exists():
            pytest.skip("lines.json not downloaded")
        data = json.loads(lines_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0
        line = data[0]
        assert "id" in line
        assert "name" in line

    def test_bikepoints_json_structure(self):
        bp_file = self.DATA_DIR / "bikepoints.json"
        if not bp_file.exists():
            pytest.skip("bikepoints.json not downloaded")
        data = json.loads(bp_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0
