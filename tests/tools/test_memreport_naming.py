import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from cerebrus.tools.memreport.tool import process_memreport

@pytest.fixture
def mock_report_context():
    return {
        "metadata": {
            "Build Configuration": "Development",
            "Device Make": "Samsung",
            "Device Model": "SM-G991B",
            "Changelist": "123456",
            "Date": "2026.05.07-12.00.00"
        },
        "sections": []
    }

def test_process_memreport_filename_metadata_driven(mock_report_context, tmp_path):
    """Test that the output filename is correctly generated from metadata."""
    input_file = tmp_path / "test_report.memreport"
    input_file.write_text("dummy content")
    
    output_dir = tmp_path / "output"
    
    with patch("cerebrus.tools.memreport.tool.HTML_TEMPLATE", "{metadata_json} {title} {report_title} {tab_buttons} {tab_contents}"):
        process_memreport(
            input_file=input_file,
            output_dir=output_dir,
            report_context=mock_report_context,
            use_as_prefix_only=False
        )
    
    expected_name = "Development_Samsung_SM-G991B_123456_2026.05.07-12.00.00.html"
    output_file = output_dir / expected_name
    assert output_file.exists()

def test_process_memreport_filename_sanitization(mock_report_context, tmp_path):
    """Test that filename components are sanitized (spaces and slashes removed)."""
    mock_report_context["metadata"]["Build Configuration"] = "Dev/Test Config"
    mock_report_context["metadata"]["Device Make"] = "Sony Mobile"
    
    input_file = tmp_path / "test_report.memreport"
    input_file.write_text("dummy content")
    output_dir = tmp_path / "output"
    
    with patch("cerebrus.tools.memreport.tool.HTML_TEMPLATE", "{metadata_json} {title} {report_title} {tab_buttons} {tab_contents}"):
        process_memreport(
            input_file=input_file,
            output_dir=output_dir,
            report_context=mock_report_context,
            use_as_prefix_only=False
        )
    
    # Dev/Test Config -> Dev_TestConfig (spaces removed, / replaced by _)
    # Sony Mobile -> SonyMobile (spaces removed)
    expected_name = "Dev_TestConfig_SonyMobile_SM-G991B_123456_2026.05.07-12.00.00.html"
    output_file = output_dir / expected_name
    assert output_file.exists()

def test_process_memreport_embeds_metadata(mock_report_context, tmp_path):
    """Test that metadata is embedded as JSON in the HTML output."""
    input_file = tmp_path / "test_report.memreport"
    input_file.write_text("dummy content")
    output_dir = tmp_path / "output"
    
    with patch("cerebrus.tools.memreport.tool.HTML_TEMPLATE", "METADATA: {metadata_json}"):
        process_memreport(
            input_file=input_file,
            output_dir=output_dir,
            report_context=mock_report_context,
            use_as_prefix_only=False
        )
    
    output_file = list(output_dir.glob("*.html"))[0]
    content = output_file.read_text()
    assert '"Build Configuration": "Development"' in content
    assert '"Changelist": "123456"' in content

def test_process_memreport_prefixes_input_name(mock_report_context, tmp_path):
    """Test UI-style prefix naming for memreport generation."""
    input_file = tmp_path / "test_report.memreport"
    input_file.write_text("dummy content")
    output_dir = tmp_path / "output"

    with patch("cerebrus.tools.memreport.tool.HTML_TEMPLATE", "{metadata_json} {title} {report_title} {tab_buttons} {tab_contents}"):
        process_memreport(
            input_file=input_file,
            output_dir=output_dir,
            report_context=mock_report_context,
            use_as_prefix_only=True,
            output_name_prefix="Nightly Build",
        )

    output_file = output_dir / "NightlyBuild_test_report.html"
    assert output_file.exists()
