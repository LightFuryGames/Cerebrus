"""Analytics pipeline smoke test.

End-to-end sanity check over TestData/Profiling. Invoked by
run_pipeline.ps1 and .github/workflows/tests.yml so local and CI
exercise the exact same code path.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cerebrus.plugins.analytics.core.csv_report_parser import (  # noqa: E402
    PerformanceCSVReportParser,
)
from cerebrus.plugins.analytics.core.html_report_parser import (  # noqa: E402
    PerformanceHTMLReportParser,
)
from cerebrus.plugins.analytics.core.normalizer import (  # noqa: E402
    build_analytics_document,
)


def main(test_data_root: Path = Path("TestData/Profiling")) -> int:
    ini = test_data_root / "BaseDeviceProfiles.ini"
    htmls = {p.stem: p for p in test_data_root.rglob("HTML/*.html")}
    failures: list[str] = []
    checked = 0

    for csv_file in test_data_root.rglob("CSV/*.csv"):
        stem = csv_file.stem
        html_path = htmls.get(stem)
        if html_path is None:
            raw = PerformanceCSVReportParser(csv_file).parse()
            doc = build_analytics_document(
                source_path=csv_file,
                source_type="profiling_csv",
                raw_values=raw,
                device_profile_config_path=ini,
            )
        else:
            parser = PerformanceHTMLReportParser(html_path)
            raw_csv = parser.extract_embedded_raw_csv()
            embedded = parser.embedded_profile_name()
            logical = html_path.with_name(f"{embedded}.csv") if embedded else html_path
            raw = PerformanceCSVReportParser(logical, csv_text=raw_csv).parse()
            doc = build_analytics_document(
                source_path=html_path,
                source_type="profiling_html_raw_csv",
                raw_values=raw,
                device_profile_config_path=ini,
            )

        schema_version = doc["schema_version"]
        report_value = doc["report_value"]
        corruption = doc["data_quality_has_corruption"]

        if schema_version != 2:
            failures.append(f"{stem}: schema_version={schema_version}")
        if not (1 <= report_value <= 100):
            failures.append(f"{stem}: report_value out of range = {report_value}")
        if not doc["report_fingerprint"]:
            failures.append(f"{stem}: empty fingerprint")
        if corruption not in (0, 1):
            failures.append(f"{stem}: bad corruption flag = {corruption}")
        checked += 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    print(f"Analytics smoke OK ({checked} samples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
