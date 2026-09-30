from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cerebrus.tools.adb import AdbError
from cerebrus.ui.components.file_manager import (
    _inject_cerebrus_metadata_script,
    _inject_raw_csv_into_report,
    _handle_generate_colored_logs,
    _handle_generate_mem_report,
    _handle_generate_perf_report,
    _move_files_from_device,
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
    csv_file = csv_dir / "test.csv"
    csv_file.write_text("FrameTime\n16.0\n", encoding="utf-8")
    profiling_dir = temp_output_dir / "Profiling"
    profiling_dir.mkdir()
    generated_report = profiling_dir / "test.html"
    final_report = profiling_dir / "test_output.html"
    generated_report.write_text("<html><body>Report</body></html>", encoding="utf-8")

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
            assert not csv_file.exists()
            assert not generated_report.exists()
            assert "rawCsvDataHidden" in final_report.read_text(encoding="utf-8")


def test_generate_perf_report_preserves_csv_when_report_is_missing(
    mock_state, temp_output_dir
):
    """A missing PerfReport output must not delete the only raw telemetry."""
    csv_dir = temp_output_dir / "CSV"
    csv_dir.mkdir()
    csv_file = csv_dir / "test.csv"
    csv_file.write_text("FrameTime\n16.0\n", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        _handle_generate_perf_report(mock_state)

    assert csv_file.exists()


def test_inject_raw_csv_returns_false_without_html_body(mock_state, tmp_path):
    """A report without a body is not a valid destination for raw telemetry."""
    csv_file = tmp_path / "Profile(20260929_200355).csv"
    csv_file.write_text("FrameTime\n16.0\n", encoding="utf-8")
    html_file = tmp_path / "report.html"
    html_file.write_text("<html><head></head></html>", encoding="utf-8")

    assert _inject_raw_csv_into_report(mock_state, csv_file, html_file) is False
    assert "rawCsvDataHidden" not in html_file.read_text(encoding="utf-8")


def test_metadata_script_marks_report_as_cerebrus_without_metadata():
    """The uploader must recognize reports even when the CSV has no metadata."""
    content = "<html><head></head><body>Report</body></html>"

    rendered = _inject_cerebrus_metadata_script(content, {})

    assert 'meta name="generator" content="Cerebrus Profiling Tool"' in rendered


@pytest.mark.parametrize(
    "dest_subpath,expected_message",
    [
        ("CSV", "No CSV present on device."),
        ("Logs", "No Logs present on device."),
        ("MemReports", "No MemReports present on device."),
    ],
)
def test_move_files_from_device_reports_correct_bucket_when_missing(
    mock_state, dest_subpath, expected_message
):
    """Regression for the 'NO CSV data found' log firing on MemReports/Logs
    failures. The error log must name the actual bucket the caller asked
    to move, not always default to 'CSV Data'."""
    mock_state.package_name = "com.lightfury.titan"
    mock_state.selected_device_serial = "ABCDEF"

    fake_client = MagicMock()
    fake_client.pull.side_effect = AdbError(
        "adb: error: failed to stat remote object '/path/.': No such file or directory"
    )

    with (
        patch(
            "cerebrus.ui.components.file_manager.AdbClient", return_value=fake_client
        ),
        patch(
            "cerebrus.ui.components.file_manager.log_message"
        ) as captured_log,
    ):
        _move_files_from_device(mock_state, "Profiling/Source", dest_subpath)

    levels_and_messages = [call.args[1:3] for call in captured_log.call_args_list]
    assert (
        "ERROR",
        expected_message,
    ) in levels_and_messages, levels_and_messages


def test_handle_generate_mem_report_directory(mock_state, temp_output_dir):
    """Test that generate_mem_report uses the MemReports/ subdirectory."""
    # Setup
    mem_dir = temp_output_dir / "MemReports"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "test.memreport").touch()

    expected_report = temp_output_dir / "MemReports" / "generated.html"
    with patch(
        "cerebrus.ui.components.file_manager.process_memreport",
        return_value=expected_report,
    ) as mock_process:
        _handle_generate_mem_report(mock_state)

        expected_dest_dir = temp_output_dir / "MemReports"
        assert expected_dest_dir.exists()
        mock_process.assert_called_once()
