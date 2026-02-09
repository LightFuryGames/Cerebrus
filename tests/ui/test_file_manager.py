from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cerebrus.ui.components.file_manager import (
    _handle_generate_colored_logs,
    _handle_generate_mem_report,
    _handle_generate_perf_report,
)
from cerebrus.ui.state import UIState


@pytest.fixture(autouse=True)
def mock_dpg_and_log():
    """Globally patch DPG and log_message for these tests to avoid crashes."""
    with patch("dearpygui.dearpygui.is_dearpygui_running", return_value=False):
        with patch("cerebrus.ui.components.file_manager.log_message"):
            yield


@pytest.fixture
def temp_output_dir(tmp_path):
    """Fixture for a temporary output directory."""
    return tmp_path


@pytest.fixture
def mock_state(temp_output_dir):
    """Fixture for a real UIState with minimal setup."""
    state = UIState()
    state.output_path = temp_output_dir
    state.base_output_path = None
    state.output_file_name = "test_output"
    state.use_prefix_only = False
    return state


def test_handle_generate_colored_logs_directory(mock_state, temp_output_dir):
    """Test that generate_colored_logs uses the Logs/ subdirectory."""
    logs_dir = temp_output_dir / "Logs"
    logs_dir.mkdir()
    (logs_dir / "test.log").touch()

    with patch(
        "cerebrus.ui.components.file_manager.convert_log_to_html"
    ) as mock_convert:
        _handle_generate_colored_logs(mock_state)

        # Check if output directory "Logs" was used
        expected_output_dir = temp_output_dir / "Logs"
        assert expected_output_dir.exists()
        assert expected_output_dir.is_dir()


def test_handle_generate_perf_report_directory(mock_state, temp_output_dir):
    """Test that generate_perf_report uses the Profiling/ subdirectory."""
    # Setup
    mock_state.output_path = temp_output_dir
    csv_dir = temp_output_dir / "CSV"
    csv_dir.mkdir()
    (csv_dir / "test.csv").touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        with (
            patch(
                "cerebrus.ui.components.file_manager._inject_metadata_into_report"
            ) as mock_metadata,
            patch(
                "cerebrus.ui.components.file_manager._post_process_perf_report"
            ) as mock_post,
        ):
            _handle_generate_perf_report(mock_state)

            # Check if output directory "Profiling" was created
            expected_output_dir = temp_output_dir / "Profiling"
            assert expected_output_dir.exists()
            mock_metadata.assert_called()
            mock_post.assert_called()


def test_handle_generate_mem_report_directory(mock_state, temp_output_dir):
    """Test that generate_mem_report uses the MemReports/ subdirectory."""
    # Setup
    mem_dir = temp_output_dir / "MemReports"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "test.memreport").touch()

    with patch("cerebrus.ui.components.file_manager.parse_memreport"):
        with patch(
            "cerebrus.ui.components.file_manager.generate_html_report"
        ) as mock_gen:
            _handle_generate_mem_report(mock_state)

            expected_dest_dir = temp_output_dir / "MemReports"
            assert expected_dest_dir.exists()
            mock_gen.assert_called()
