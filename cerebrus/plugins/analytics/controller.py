"""UI-agnostic orchestration for the analytics plugin.

All non-DPG behaviour lives here so the same pipeline can be exercised from
tests, scripts, or CI without spinning up the Dear PyGui runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cerebrus.plugins.analytics.core.converter import (
    ElasticsearchClient,
    convert_file_to_document,
    convert_file_to_json,
    summarize_folder,
)
from cerebrus.plugins.analytics.core.settings import (
    AnalyticsSettings,
    load_analytics_settings,
    save_analytics_settings,
)

Logger = Callable[[str, str], None]


@dataclass
class UploadOutcome:
    successes: list[Path] = field(default_factory=list)
    failures: list[tuple[Path, str]] = field(default_factory=list)
    last_status: int | None = None
    last_timestamp: str = "not found"
    summary_lines: list[str] = field(default_factory=list)


@dataclass
class BulkOutcome:
    documents_sent: int = 0
    targets_total: int = 0
    status: int = 0
    response_text: str = ""
    counts: dict[str, int] = field(default_factory=lambda: {"created": 0, "updated": 0, "errors": 0})
    convert_failures: list[tuple[Path, str]] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        if self.status not in {200, 201}:
            return False
        if self.counts.get("errors", 0) != 0:
            return False
        if self.convert_failures:
            return False
        # Strict accounting: every document we sent must be acknowledged as
        # either created or updated. Anything else (under-reported items,
        # silently-dropped docs) blocks delete-after-success.
        accounted = self.counts.get("created", 0) + self.counts.get("updated", 0)
        return accounted == self.documents_sent and self.documents_sent > 0


class AnalyticsController:
    """Headless analytics pipeline.

    Inject ``logger`` to receive ``(level, message)`` events. Inject
    ``settings_path`` for tests that need an isolated settings file. Inject
    ``client`` to mock Elasticsearch transport.
    """

    def __init__(
        self,
        *,
        logger: Logger | None = None,
        client: ElasticsearchClient | None = None,
        settings_path: Path | None = None,
    ) -> None:
        self._log: Logger = logger if logger is not None else (lambda level, message: None)
        self._client = client if client is not None else ElasticsearchClient()
        self._settings_path = settings_path

    @property
    def client(self) -> ElasticsearchClient:
        return self._client

    def load_settings(self) -> AnalyticsSettings:
        return load_analytics_settings(self._settings_path)

    def save_upload_url(self, url: str) -> str:
        clean_url = (url or "").strip()
        current = self.load_settings()
        save_analytics_settings(
            AnalyticsSettings(
                elasticsearch_url=clean_url,
                device_profile_config_path=current.device_profile_config_path,
            ),
            self._settings_path,
        )
        self._log("SUCCESS", "Analytics upload endpoint saved.")
        return clean_url

    def device_profile_config_path(self) -> str:
        return self.load_settings().device_profile_config_path

    def resolve_targets(
        self, source: Path | None, folder: Path | None
    ) -> list[Path]:
        if source and source.is_file():
            return [source]
        if folder and folder.is_dir():
            return sorted(folder.glob("*.analytics.json"))
        return []

    def convert_to_document(self, source: Path) -> dict[str, Any]:
        return convert_file_to_document(source, self.device_profile_config_path())

    def convert_to_json_file(
        self, source: Path, output_dir: Path | None = None
    ) -> Path:
        """Convert ``source`` to ``.analytics.json``.

        When ``output_dir`` is omitted the JSON is written next to the source
        report; this is what the UI does when the "Output File Path" field
        is left empty. When supplied, the JSON is placed inside that
        directory while keeping the source's basename (with the
        ``.analytics.json`` suffix).
        """
        target: Path | None = None
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            target = output_dir / f"{Path(source).stem}.analytics.json"
        return convert_file_to_json(
            source,
            output_path=target,
            device_profile_config_path=self.device_profile_config_path(),
        )

    def build_trend_summary(self, folder: Path) -> Path:
        return summarize_folder(
            folder, device_profile_config_path=self.device_profile_config_path()
        )

    def upload_individual(
        self,
        targets: list[Path],
        url: str,
        *,
        delete_after_success: bool = False,
    ) -> UploadOutcome:
        outcome = UploadOutcome()
        for target in targets:
            try:
                document = self.convert_to_document(target)
                status, response_text = self._client.push_document(document, url)
                outcome.last_status = status
                if status in {200, 201}:
                    outcome.successes.append(target)
                    outcome.last_timestamp = document.get("@timestamp", "not found")
                    self._log("SUCCESS", f"Uploaded analytics document: {target.name}")
                    if delete_after_success:
                        self._delete_uploaded(target)
                else:
                    outcome.failures.append((target, f"{status} {response_text}"))
                    self._log(
                        "ERROR",
                        f"Upload failed for {target.name}: {status} {response_text}",
                    )
            except Exception as exc:
                outcome.failures.append((target, str(exc)))
                self._log("ERROR", f"Upload failed for {target.name}: {exc}")

        outcome.summary_lines = self._format_individual_summary(
            url, outcome, len(targets)
        )
        return outcome

    def upload_bulk(
        self,
        targets: list[Path],
        url: str,
        *,
        delete_after_success: bool = False,
    ) -> BulkOutcome:
        outcome = BulkOutcome(targets_total=len(targets))
        documents: list[dict[str, Any]] = []
        converted_targets: list[Path] = []
        for target in targets:
            try:
                documents.append(self.convert_to_document(target))
                converted_targets.append(target)
            except Exception as exc:
                outcome.convert_failures.append((target, str(exc)))
                self._log(
                    "ERROR",
                    f"Skipping {target.name}: conversion failed: {exc}",
                )

        outcome.documents_sent = len(documents)
        if not documents:
            self._log("ERROR", "No documents to upload after conversion.")
            outcome.summary_lines = ["Bulk upload aborted: nothing to send."]
            return outcome

        try:
            status, response_text, counts = self._client.push_bulk(documents, url)
        except Exception as exc:
            self._log("ERROR", f"Bulk upload failed: {exc}")
            outcome.summary_lines = [f"Bulk upload error: {exc}"]
            return outcome

        outcome.status = status
        outcome.response_text = response_text
        outcome.counts = counts.as_dict()

        if outcome.is_success:
            self._log(
                "SUCCESS",
                f"Bulk uploaded {len(documents)} document(s) "
                f"(created={counts.created}, updated={counts.updated}).",
            )
            if delete_after_success:
                for target in converted_targets:
                    self._delete_uploaded(target)
        else:
            self._log(
                "ERROR",
                f"Bulk upload returned status {status} "
                f"with {counts.errors} item error(s). "
                f"Response: {response_text[:300]}",
            )

        outcome.summary_lines = self._format_bulk_summary(url, outcome)
        return outcome

    def _delete_uploaded(self, path: Path) -> None:
        if not path.name.endswith(".analytics.json"):
            return
        try:
            path.unlink()
            self._log("INFO", f"Deleted uploaded JSON: {path.name}")
        except OSError as exc:
            self._log("ERROR", f"Could not delete {path.name}: {exc}")

    @staticmethod
    def _format_individual_summary(
        url: str, outcome: UploadOutcome, total: int
    ) -> list[str]:
        lines = [
            f"Endpoint: {url}",
            f"Uploaded: {len(outcome.successes)} / {total}",
        ]
        if outcome.last_status is not None:
            lines.append(f"Last status: {outcome.last_status}")
        if outcome.successes:
            lines.append(f"Last timestamp: {outcome.last_timestamp}")
        if outcome.failures:
            lines.append(f"Failures: {len(outcome.failures)}")
            for path, reason in outcome.failures[:3]:
                lines.append(f"  - {path.name}: {reason}")
        return lines

    @staticmethod
    def _format_bulk_summary(url: str, outcome: BulkOutcome) -> list[str]:
        counts = outcome.counts
        lines = [
            f"Endpoint (bulk): {url}",
            f"Documents sent: {outcome.documents_sent} / {outcome.targets_total}",
            f"HTTP status: {outcome.status}",
            f"Created: {counts.get('created', 0)}  "
            f"Updated: {counts.get('updated', 0)}  "
            f"Errors: {counts.get('errors', 0)}",
        ]
        if outcome.convert_failures:
            lines.append(f"Conversion failures: {len(outcome.convert_failures)}")
            for path, reason in outcome.convert_failures[:3]:
                lines.append(f"  - {path.name}: {reason}")
        return lines
