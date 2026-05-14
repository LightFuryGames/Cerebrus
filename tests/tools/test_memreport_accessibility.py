import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from cerebrus.tools.memreport.tool import HTML_TEMPLATE, generate_html_report


def test_html_accessibility_features():
    """
    Verifies that the generated HTML report contains basic accessibility features.
    """

    # Mock context with minimal data
    context: Dict[str, Any] = {
        "metadata": {"Device Name": "Test Device"},
        "tabs": [],
        "groups": {},
        "group_order": [],
    }

    # Create a temporary file for the report
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        output_path = Path(tmp.name)

    try:
        # Generate the report
        # Note: generate_html_report signature might vary based on local version,
        # but based on usage in tool.py: generate_html_report(report_context, output_file)
        generate_html_report(context, output_path)

        # Read the generated content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Check for Language Attribute
        assert '<html lang="en">' in content, "HTML tag missing lang='en' attribute"

        # 2. Check for Character Set
        assert '<meta charset="UTF-8">' in content, "Meta charset tag is missing"

        # 3. Check for Viewport Meta Tag (for mobile accessibility)
        assert (
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            in content
        )

        # 4. Check for Title
        assert "<title>MemReport - Test Device</title>" in content

        # 5. Check for Accessibility of Interactive Elements
        # Theme toggle should have a title or aria-label
        assert (
            'title="Toggle Light/Dark Mode"' in content
            or 'aria-label="Toggle Light/Dark Mode"' in content
        )

        # 6. Check for meaningful headers
        assert (
            "<h1>MemReport - Test Device</h1>" in content
            or "<h1>Memory Report</h1>" in content
        )

    finally:
        # Cleanup
        if output_path.exists():
            os.unlink(output_path)
