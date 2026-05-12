from unittest.mock import MagicMock

from cerebrus.plugins.s3_uploader import (
    _derive_s3_dir_from_metadata,
    _extract_report_metadata,
    _upload_file_to_s3,
)


def test_extract_report_metadata_from_json_script():
    html = """
    <html>
      <script type="application/json" id="cerebrus-metadata">
        {"Build Configuration": "Development", "Device Make": "Samsung"}
      </script>
    </html>
    """

    metadata = _extract_report_metadata(html)

    assert metadata["Build Configuration"] == "Development"
    assert metadata["Device Make"] == "Samsung"


def test_extract_report_metadata_from_legacy_stat_cards():
    html = """
    <div class="stat-label">Build Configuration</div><div class="stat-value">Dev Test</div>
    <div class="stat-label">Device Make</div><div class="stat-value">Sony Mobile</div>
    <div class="stat-label">Device Model</div><div class="stat-value">XQ/123</div>
    <div class="stat-label">Changelist</div><div class="stat-value">12345</div>
    <div class="stat-label">Date</div><div class="stat-value">2026.05.11-09.30.00</div>
    """

    metadata = _extract_report_metadata(html)

    assert metadata == {
        "Build Configuration": "Dev Test",
        "Device Make": "Sony Mobile",
        "Device Model": "XQ/123",
        "Changelist": "12345",
        "Date": "2026.05.11-09.30.00",
    }


def test_extract_report_metadata_from_perf_report_table():
    html = """
    <html>
      <head><title>60FPS Performance Report : Profile(20260511_082831)</title></head>
      <body>
        <table>
          <tr><td bgcolor='#F0F0F0'>Build Version</td><td><b>++titan-game+development-CL-33425</b></td></tr>
          <tr><td>Configuration</td><td><b>Test</b></td></tr>
          <tr><td>CPU/Device</td><td><b>OnePlus|ONEPLUS A3003|Qualcomm Technologies&#44; Inc MSM8996</b></td></tr>
        </table>
      </body>
    </html>
    """

    metadata = _extract_report_metadata(html)

    assert metadata == {
        "Build Configuration": "Test",
        "Changelist": "CL-33425",
        "Device Make": "OnePlus",
        "Device Model": "A3003",
        "Date": "11-05-2026",
        "Time": "082831",
    }


def test_extract_report_metadata_from_perf_report_footer_fallback():
    html = """
    <title>60FPS Performance Report : Profile(20260511_162618)</title>
    <pre>
    [HasHeaderRowAtEnd],1,[platform],Android,[config],Test,[buildversion],++titan-game+development-CL-32831,[cpu],samsung|SM-S948U1|Adreno (TM) 840,[commandline],""
    </pre>
    """

    metadata = _extract_report_metadata(html)

    assert metadata == {
        "Build Configuration": "Test",
        "Changelist": "CL-32831",
        "Device Make": "samsung",
        "Device Model": "SM-S948U1",
        "Date": "11-05-2026",
        "Time": "162618",
    }


def test_derive_s3_dir_from_metadata_sanitizes_segments():
    metadata = {
        "Build Configuration": "Dev Test",
        "Device Make": "Sony Mobile",
        "Device Model": "XQ/123",
        "Changelist": "CL 123",
        "Date": "2026.05.11-09.30.00",
    }

    assert (
        _derive_s3_dir_from_metadata(metadata)
        == "Dev_Test/Sony_Mobile/XQ_123/CL_123/2026.05.11/09.30.00"
    )


def test_derive_s3_dir_from_current_perf_report_metadata():
    metadata = {
        "Build Configuration": "Test",
        "Device Make": "OnePlus",
        "Device Model": "A3003",
        "Changelist": "CL-33425",
        "Date": "11-05-2026",
        "Time": "082831",
    }

    assert (
        _derive_s3_dir_from_metadata(metadata)
        == "Test/OnePlus/A3003/CL-33425/11-05-2026/082831"
    )


def test_upload_file_to_s3_includes_content_type_extra_args():
    s3_client = MagicMock()

    _upload_file_to_s3(
        s3_client,
        "report.html",
        "perf-reports",
        "Development/report.html",
        content_type="text/html",
    )

    s3_client.upload_file.assert_called_once_with(
        "report.html",
        "perf-reports",
        "Development/report.html",
        ExtraArgs={"ContentType": "text/html"},
    )


def test_upload_file_to_s3_omits_extra_args_when_empty():
    s3_client = MagicMock()

    _upload_file_to_s3(
        s3_client,
        "report.html",
        "perf-reports",
        "Development/report.html",
    )

    s3_client.upload_file.assert_called_once_with(
        "report.html",
        "perf-reports",
        "Development/report.html",
    )
