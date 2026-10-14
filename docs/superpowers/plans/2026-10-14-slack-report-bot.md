# Slack Report Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AWS-hosted Slack bot that accepts one Cerebrus HTML report plus optional Thermal CSV files from the private Cerebrus Feedback channel, stores them under a CL-based prefix in the existing S3 bucket, and replies with seven-day CloudFront signed links.

**Architecture:** API Gateway and an ingress Lambda authenticate and enqueue Slack private-channel message events. An SQS-triggered worker Lambda validates and downloads Slack files, extracts the CL from the HTML, uploads deterministic S3 objects, signs private CloudFront URLs, and posts an idempotent threaded reply; DynamoDB provides processing leases and terminal-state deduplication.

**Tech Stack:** Python 3.12, AWS SAM/CloudFormation, API Gateway HTTP API, Lambda, SQS/DLQ, DynamoDB, S3, CloudFront OAC and signed URLs, Secrets Manager, CloudWatch, `boto3`, `beautifulsoup4`, `cryptography`, and `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-14-slack-report-bot-design.md`

## Global Constraints

- Treat `docs/superpowers/specs/2026-10-14-slack-report-bot-design.md` as authoritative.
- Target Python 3.12+ and follow `CODE_STANDARDS.md`: typed public APIs, frozen dataclasses, pure parsing logic, explicit dependency injection, and no swallowed exceptions.
- Use the AWS SDK default credential chain. Never pass, persist, log, or template `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_SESSION_TOKEN`.
- At runtime, use the Lambda execution role; never construct an AWS client with explicit credentials.
- Accept events only for the configured Slack workspace and private channel.
- Require exactly one `.html` file; allow zero or more `.csv` files; reject all other attached file types.
- Extract the CL only from the `Build Version` table row using `-CL-(?P<cl>\d+)\b`.
- Use `Asia/Kolkata` for `reports/YYYY/MM/DD/<CL>/<filename>`.
- Overwrite deterministic S3 keys on repeated uploads.
- Keep S3 private and use CloudFront signed URLs expiring after exactly 604800 seconds.
- Retain S3 objects indefinitely; do not add an S3 lifecycle rule.
- Never log secret values, Authorization headers, uploaded contents, or signed URL query strings.
- Run focused tests with `python -m pytest tests/slack_report_bot` and remove `.pytest_run_tmp` after test runs.
- Preserve all unrelated working-tree changes and stage only files named in each task.

---

## File Structure

Create the service outside the desktop runtime while keeping it importable by the root test suite:

```text
infrastructure/
  __init__.py                         # Infrastructure Python namespace
  slack_report_bot/
    __init__.py                       # Slack report bot package marker
    README.md                         # Operator entry point and deployment summary
    requirements.txt                  # Lambda/runtime dependencies
    template.yaml                     # SAM resources and least-privilege policies
    app/
      __init__.py
      config.py                       # Typed environment configuration
      errors.py                       # Permanent vs retryable service errors
      models.py                       # Immutable Slack/report/upload models
      secrets.py                      # Cached Secrets Manager reads
      slack_auth.py                   # Pure Slack signature verification
      ingress.py                      # API Gateway Lambda handler
      report_parser.py                # File-set validation and Build Version parsing
      slack_client.py                 # Slack files.info/download/chat.postMessage boundary
      storage.py                      # India-time keys and S3 uploads
      link_signer.py                  # Seven-day CloudFront signed URLs
      idempotency.py                  # DynamoDB lease/state transitions
      metrics.py                      # Secret-safe CloudWatch EMF metrics
      worker.py                       # SQS orchestration
    scripts/
      provision_signing_key.py        # Generate RSA key in memory and provision AWS resources
      provision_slack_secrets.py      # Put Slack secrets from non-echoed environment values
      configure_bucket_policy.py      # Idempotently merge/remove one scoped OAC statement
      deploy.ps1                      # Validate environment and deploy SAM stack
tests/
  slack_report_bot/
    test_config.py
    test_slack_auth.py
    test_ingress.py
    test_report_parser.py
    test_slack_client.py
    test_storage.py
    test_link_signer.py
    test_idempotency.py
    test_metrics.py
    test_worker.py
    test_infrastructure.py
    test_provisioning_scripts.py
docs/
  developer/SLACK_REPORT_BOT.md       # AWS/Slack runbook and incident handling
  user/SLACK_REPORT_BOT.md            # QA upload instructions and error meanings
```

Do not place this service under `cerebrus/plugins`; it is deployed infrastructure, not a desktop `TabPlugin` or `MenuPlugin`.

---

### Task 1: Establish the Service Package and Typed Contracts

**Files:**
- Create: `infrastructure/__init__.py`
- Create: `infrastructure/slack_report_bot/__init__.py`
- Create: `infrastructure/slack_report_bot/app/__init__.py`
- Create: `infrastructure/slack_report_bot/app/config.py`
- Create: `infrastructure/slack_report_bot/app/errors.py`
- Create: `infrastructure/slack_report_bot/app/models.py`
- Create: `infrastructure/slack_report_bot/requirements.txt`
- Create: `tests/slack_report_bot/test_config.py`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Produces: `IngressSettings.from_env(mapping)`, `WorkerSettings.from_env(mapping)`, `SlackFile`, `ReportFiles`, `UploadedObject`, `ValidationError`, and `RetryableServiceError`.
- Consumes: no prior task interfaces.

- [ ] **Step 1: Write failing configuration tests**

```python
from infrastructure.slack_report_bot.app.config import IngressSettings, WorkerSettings


def test_ingress_settings_require_non_secret_identifiers():
    settings = IngressSettings.from_env(
        {
            "SLACK_WORKSPACE_ID": "T123",
            "SLACK_CHANNEL_ID": "G456",
            "SLACK_SIGNING_SECRET_ARN": "arn:aws:secretsmanager:ap-south-1:1:secret:signing",
            "REPORT_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/1/reports",
        }
    )
    assert settings.channel_id == "G456"


def test_worker_settings_use_seven_day_links_and_kolkata_time():
    settings = WorkerSettings.from_env(
        {
            "SLACK_BOT_TOKEN_ARN": "arn:aws:secretsmanager:ap-south-1:1:secret:bot",
            "CLOUDFRONT_PRIVATE_KEY_ARN": "arn:aws:secretsmanager:ap-south-1:1:secret:key",
            "CLOUDFRONT_KEY_PAIR_ID": "K123",
            "CLOUDFRONT_DOMAIN": "reports.example.cloudfront.net",
            "REPORT_BUCKET": "cerebrus-existing",
            "IDEMPOTENCY_TABLE": "cerebrus-report-events",
        }
    )
    assert settings.link_ttl_seconds == 604800
    assert settings.timezone_name == "Asia/Kolkata"
```

- [ ] **Step 2: Run the tests and confirm the missing-package failure**

Run: `python -m pytest tests/slack_report_bot/test_config.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'infrastructure'` or the config types are missing.

- [ ] **Step 3: Implement immutable models, explicit errors, and environment parsing**

Use frozen dataclasses and reject blank required values:

```python
@dataclass(frozen=True)
class SlackFile:
    file_id: str
    name: str
    size: int
    download_url: str


@dataclass(frozen=True)
class ReportFiles:
    html: SlackFile
    csvs: tuple[SlackFile, ...]


@dataclass(frozen=True)
class UploadedObject:
    name: str
    key: str
    signed_url: str
    media_type: str


class ValidationError(ValueError):
    """A user-correctable report error that must not be retried."""


class RetryableServiceError(RuntimeError):
    """An external-service error for which SQS should retry the event."""
```

`IngressSettings` must contain `workspace_id`, `channel_id`, `signing_secret_arn`, and `queue_url`. `WorkerSettings` must contain `bot_token_arn`, `cloudfront_private_key_arn`, `cloudfront_key_pair_id`, `cloudfront_domain`, `report_bucket`, `idempotency_table`, plus constants `timezone_name="Asia/Kolkata"`, `link_ttl_seconds=604800`, `max_file_bytes=536870912`, and `max_message_bytes=1073741824`.

- [ ] **Step 4: Add isolated runtime dependencies and CI installation**

Write `infrastructure/slack_report_bot/requirements.txt`:

```text
boto3>=1.35,<2
beautifulsoup4>=4.12,<5
cryptography>=43,<47
```

In `.github/workflows/tests.yml`, add this immediately after the root requirements installation:

```powershell
pip install -r infrastructure/slack_report_bot/requirements.txt
```

Extend the coverage command with `--cov=infrastructure.slack_report_bot.app`.

- [ ] **Step 5: Run focused tests and formatting**

Run:

```powershell
python -m pytest tests/slack_report_bot/test_config.py -v
python -m black --check infrastructure/slack_report_bot/app tests/slack_report_bot
python -m isort --check-only infrastructure/slack_report_bot/app tests/slack_report_bot
```

Expected: all commands pass.

- [ ] **Step 6: Commit the package contracts**

```powershell
git add infrastructure/__init__.py infrastructure/slack_report_bot/__init__.py infrastructure/slack_report_bot/app infrastructure/slack_report_bot/requirements.txt tests/slack_report_bot/test_config.py .github/workflows/tests.yml
git commit -m "feat: establish Slack report bot contracts"
```

---

### Task 2: Verify Slack Requests and Load Secrets Safely

**Files:**
- Create: `infrastructure/slack_report_bot/app/secrets.py`
- Create: `infrastructure/slack_report_bot/app/slack_auth.py`
- Create: `tests/slack_report_bot/test_slack_auth.py`

**Interfaces:**
- Produces: `SecretProvider.get_text(secret_arn: str) -> str` and `verify_slack_request(signing_secret, timestamp, raw_body, signature, now) -> None`.
- Consumes: `ValidationError` is not used here; authentication failures use `SlackAuthenticationError` defined in `slack_auth.py`.

- [ ] **Step 1: Write signature and replay-window tests**

```python
def test_verify_slack_request_accepts_valid_signature():
    now = 1_700_000_000
    body = b'{"type":"event_callback"}'
    signature = sign_for_test("secret", str(now), body)
    verify_slack_request("secret", str(now), body, signature, now)


def test_verify_slack_request_rejects_request_older_than_five_minutes():
    with pytest.raises(SlackAuthenticationError, match="timestamp"):
        verify_slack_request("secret", "1699999699", b"{}", "v0=bad", 1_700_000_000)
```

Also assert rejection of missing headers, non-integer timestamps, wrong signatures, and future timestamps outside the same 300-second window.

- [ ] **Step 2: Run the signature tests and confirm they fail**

Run: `python -m pytest tests/slack_report_bot/test_slack_auth.py -v`

Expected: import fails because `slack_auth.py` does not exist.

- [ ] **Step 3: Implement HMAC verification and cached secret retrieval**

```python
def verify_slack_request(
    signing_secret: str,
    timestamp: str,
    raw_body: bytes,
    signature: str,
    now: int,
) -> None:
    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise SlackAuthenticationError("Invalid Slack timestamp") from exc
    if abs(now - request_time) > 300:
        raise SlackAuthenticationError("Slack timestamp is outside the replay window")
    base = b"v0:" + timestamp.encode("ascii") + b":" + raw_body
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"), base, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SlackAuthenticationError("Invalid Slack signature")
```

`SecretProvider` accepts an injected Secrets Manager client, reads `SecretString`, rejects binary/empty values, and caches by ARN only in process memory. It must never log a secret or AWS response.

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest tests/slack_report_bot/test_slack_auth.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit Slack authentication**

```powershell
git add infrastructure/slack_report_bot/app/secrets.py infrastructure/slack_report_bot/app/slack_auth.py tests/slack_report_bot/test_slack_auth.py
git commit -m "feat: verify Slack event signatures"
```

---

### Task 3: Build the Fast Ingress Lambda

**Files:**
- Create: `infrastructure/slack_report_bot/app/ingress.py`
- Create: `tests/slack_report_bot/test_ingress.py`

**Interfaces:**
- Consumes: `IngressSettings`, `SecretProvider.get_text`, and `verify_slack_request`.
- Produces: `build_handler(settings, secret_provider, sqs_client, clock) -> Callable` and Lambda entry point `handler(event, context) -> dict[str, object]`.

- [ ] **Step 1: Write failing ingress tests**

Cover URL verification, accepted file messages, irrelevant events, wrong workspace/channel, bot messages, absent files, invalid JSON, bad signature, and SQS failures. The accepted-event assertion must be:

```python
response = handler(api_gateway_event(slack_payload), None)

assert response["statusCode"] == 200
sqs.send_message.assert_called_once_with(
    QueueUrl=settings.queue_url,
    MessageBody=json.dumps(slack_payload, separators=(",", ":")),
    MessageAttributes={
        "SlackEventId": {"DataType": "String", "StringValue": "Ev123"},
        "AcceptedAtEpoch": {"DataType": "Number", "StringValue": "1791921600"},
    },
)
```

- [ ] **Step 2: Run ingress tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_ingress.py -v`

Expected: import fails because `ingress.py` does not exist.

- [ ] **Step 3: Implement filtering and enqueueing**

The handler must decode API Gateway base64 bodies, verify the raw bytes before JSON parsing, return `{"statusCode": 200, "body": challenge}` for `url_verification`, and accept only this event shape. Capture `AcceptedAtEpoch` once from the injected UTC clock and include it as an SQS number message attribute so retries always use the original India-time folder date:

```python
def is_report_message(payload: Mapping[str, object], settings: IngressSettings) -> bool:
    event = payload.get("event")
    return bool(
        payload.get("team_id") == settings.workspace_id
        and isinstance(event, dict)
        and event.get("type") == "message"
        and event.get("channel_type") == "group"
        and event.get("channel") == settings.channel_id
        and event.get("user")
        and not event.get("bot_id")
        and event.get("subtype") not in {"bot_message", "message_changed", "message_deleted"}
        and isinstance(event.get("files"), list)
        and event["files"]
    )
```

Return 401 for authentication errors, 400 for malformed JSON, 502 if SQS rejects the event, and 200 for valid but irrelevant Slack events.

- [ ] **Step 4: Run ingress tests and static checks**

Run:

```powershell
python -m pytest tests/slack_report_bot/test_ingress.py -v
python -m mypy infrastructure/slack_report_bot/app/ingress.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit the ingress Lambda**

```powershell
git add infrastructure/slack_report_bot/app/ingress.py tests/slack_report_bot/test_ingress.py
git commit -m "feat: enqueue authenticated Slack events"
```

---

### Task 4: Validate File Sets and Extract the CL

**Files:**
- Create: `infrastructure/slack_report_bot/app/report_parser.py`
- Create: `tests/slack_report_bot/test_report_parser.py`

**Interfaces:**
- Consumes: `SlackFile`, `ReportFiles`, and `ValidationError`.
- Produces: `select_report_files(files: Sequence[SlackFile], max_file_bytes: int, max_message_bytes: int) -> ReportFiles`, `safe_filename(name: str) -> str`, and `extract_cl_number(html_text: str) -> str`.

- [ ] **Step 1: Write failing report-validation tests**

Use synthetic HTML strings, not committed `.html` fixtures:

```python
VALID_HTML = """
<table><tr><td>Build Version</td>
<td><strong>++titan-game+development-CL-51333</strong></td></tr></table>
"""


def test_extracts_cl_from_build_version_row():
    assert extract_cl_number(VALID_HTML) == "51333"


def test_accepts_one_html_and_optional_csvs():
    selected = select_report_files(
        [file("report.HTML"), file("thermal-1.csv"), file("thermal-2.CSV")],
        max_file_bytes=536870912,
        max_message_bytes=1073741824,
    )
    assert selected.html.name == "report.HTML"
    assert [item.name for item in selected.csvs] == ["thermal-1.csv", "thermal-2.CSV"]
```

Add tests for no HTML, multiple HTML, unsupported extensions, separators, control characters, empty basename, per-file size, total size, no Build Version row, multiple Build Version rows, no CL, and multiple CL matches.

- [ ] **Step 2: Run parser tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_report_parser.py -v`

Expected: import fails because `report_parser.py` does not exist.

- [ ] **Step 3: Implement pure selection and parsing**

```python
CL_PATTERN = re.compile(r"-CL-(?P<cl>\d+)\b")


def extract_cl_number(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    values: list[str] = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2 and cells[0].get_text(" ", strip=True) == "Build Version":
            values.append(cells[1].get_text(" ", strip=True))
    if len(values) != 1:
        raise ValidationError("Expected exactly one Build Version row")
    matches = list(CL_PATTERN.finditer(values[0]))
    if len(matches) != 1:
        raise ValidationError("Build Version must contain exactly one CL number")
    return matches[0].group("cl")
```

`safe_filename` must require `Path(name).name == name`, reject `/`, `\`, control characters, `.` and `..`, and return the original basename so S3 overwrite keys remain deterministic.

- [ ] **Step 4: Run parser tests**

Run: `python -m pytest tests/slack_report_bot/test_report_parser.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit report validation**

```powershell
git add infrastructure/slack_report_bot/app/report_parser.py tests/slack_report_bot/test_report_parser.py
git commit -m "feat: validate Slack report files and extract CL"
```

---

### Task 5: Implement the Slack API Boundary

**Files:**
- Create: `infrastructure/slack_report_bot/app/slack_client.py`
- Create: `tests/slack_report_bot/test_slack_client.py`

**Interfaces:**
- Produces: `SlackClient.get_file(file_id: str) -> SlackFile`, `SlackClient.download(file: SlackFile, destination: Path, max_bytes: int) -> int`, and `SlackClient.post_reply(channel: str, thread_ts: str, text: str, client_message_id: str) -> str`.
- Consumes: `SlackFile` and `RetryableServiceError`.

- [ ] **Step 1: Write failing HTTP-boundary tests**

Inject an `open_url(request, timeout)` callable. Assert that `files.info`, file downloads, and `chat.postMessage` always use `Authorization: Bearer <token>`, but no exception string includes the token. Assert that `post_reply` sends `thread_ts` and a stable `client_msg_id`.

```python
reply_ts = client.post_reply("G456", "1710000000.000100", "uploaded", "uuid-value")
assert reply_ts == "1710000001.000200"
assert json.loads(recorded_request.data)["thread_ts"] == "1710000000.000100"
```

- [ ] **Step 2: Run Slack client tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_slack_client.py -v`

Expected: import fails because `slack_client.py` does not exist.

- [ ] **Step 3: Implement strict Slack response handling and streaming downloads**

Use `urllib.request` from the standard library. `get_file` must call `https://slack.com/api/files.info?file=<urlencoded-id>`, require `ok is True`, and map `id`, `name`, `size`, and `url_private_download`. `download` must read fixed-size chunks into a previously validated local path. `post_reply` must POST JSON to `https://slack.com/api/chat.postMessage` and return the response `ts`.

Count downloaded bytes while streaming and return the count. Abort if actual bytes exceed the declared file size or `max_bytes`, and reject a truncated response whose byte count differs from Slack's declared size. Convert HTTP, timeout, malformed JSON, `ok: false`, and truncated-download failures to `RetryableServiceError` with sanitized messages containing only the Slack method and status/error code.

- [ ] **Step 4: Run Slack client tests**

Run: `python -m pytest tests/slack_report_bot/test_slack_client.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the Slack client**

```powershell
git add infrastructure/slack_report_bot/app/slack_client.py tests/slack_report_bot/test_slack_client.py
git commit -m "feat: add Slack file and reply client"
```

---

### Task 6: Upload Deterministic S3 Objects and Sign CloudFront Links

**Files:**
- Create: `infrastructure/slack_report_bot/app/storage.py`
- Create: `infrastructure/slack_report_bot/app/link_signer.py`
- Create: `tests/slack_report_bot/test_storage.py`
- Create: `tests/slack_report_bot/test_link_signer.py`

**Interfaces:**
- Produces: `build_object_key(accepted_at: datetime, cl_number: str, filename: str) -> str`, `object_metadata(filename: str) -> dict[str, str]`, `S3Store.upload(local_path: Path, key: str, metadata: Mapping[str, str]) -> None`, and `CloudFrontLinkSigner.sign(key: str, expires_at: datetime) -> str`.
- Consumes: `RetryableServiceError` and a validated filename from Task 4.

- [ ] **Step 1: Write failing storage and signing tests**

```python
def test_build_object_key_uses_kolkata_date():
    instant = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)
    assert build_object_key(instant, "51333", "report.html") == (
        "reports/2026/10/14/51333/report.html"
    )


def test_signed_url_expires_in_exactly_seven_days():
    expires_at = datetime(2026, 10, 21, tzinfo=timezone.utc)
    url = signer.sign("reports/2026/10/14/51333/report.html", expires_at)
    assert url.startswith("https://reports.example.cloudfront.net/")
    assert "Expires=1792540800" in url
```

Also verify HTML inline metadata, CSV attachment metadata, URL quoting, deterministic overwrite keys, `ExtraArgs` passed to `upload_file`, and exception sanitization.

- [ ] **Step 2: Run storage tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_storage.py tests/slack_report_bot/test_link_signer.py -v`

Expected: imports fail because the modules do not exist.

- [ ] **Step 3: Implement S3 metadata and uploads**

```python
def build_object_key(accepted_at: datetime, cl_number: str, filename: str) -> str:
    local_date = accepted_at.astimezone(ZoneInfo("Asia/Kolkata"))
    return f"reports/{local_date:%Y/%m/%d}/{cl_number}/{filename}"


def object_metadata(filename: str) -> dict[str, str]:
    if filename.lower().endswith(".html"):
        return {
            "ContentType": "text/html; charset=utf-8",
            "ContentDisposition": f'inline; filename="{filename}"',
        }
    return {
        "ContentType": "text/csv; charset=utf-8",
        "ContentDisposition": f'attachment; filename="{filename}"',
    }
```

`S3Store.upload` calls `upload_file(str(local_path), bucket, key, ExtraArgs=dict(metadata))`. It relies on the existing bucket encryption policy and must not set ACLs.

- [ ] **Step 4: Implement RSA CloudFront signing**

Load the PEM with `serialization.load_pem_private_key`, require an RSA private key, and inject this callback into `botocore.signers.CloudFrontSigner`:

```python
def rsa_signer(message: bytes) -> bytes:
    return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())
```

Construct the resource URL as `https://<domain>/<quoted-key>` and call `generate_presigned_url(resource_url, date_less_than=expires_at)`. Never log the returned URL query string.

- [ ] **Step 5: Run storage and signer tests**

Run: `python -m pytest tests/slack_report_bot/test_storage.py tests/slack_report_bot/test_link_signer.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit storage and private links**

```powershell
git add infrastructure/slack_report_bot/app/storage.py infrastructure/slack_report_bot/app/link_signer.py tests/slack_report_bot/test_storage.py tests/slack_report_bot/test_link_signer.py
git commit -m "feat: store reports and sign CloudFront links"
```

---

### Task 7: Implement DynamoDB Processing Leases

**Files:**
- Create: `infrastructure/slack_report_bot/app/idempotency.py`
- Create: `tests/slack_report_bot/test_idempotency.py`

**Interfaces:**
- Produces: `IdempotencyStore.acquire(event_id, channel_id, thread_ts, now) -> bool`, `mark_completed(event_id, cl_number, keys, reply_ts, now)`, `mark_validation_failed(event_id, message, reply_ts, now)`, and `mark_retryable_failed(event_id, error_code, now)`.
- Consumes: an injected DynamoDB table resource and UTC-aware datetimes.

- [ ] **Step 1: Write failing lease-transition tests**

Assert that acquire uses a conditional update allowing a missing record, `retryable_failed`, or an expired `processing` lease; it must reject active `processing`, `completed`, and `validation_failed` records. Assert a 15-minute lease, incremented attempt count, and TTL at creation plus fourteen days.

```python
assert store.acquire("Ev123", "G456", "171.001", now) is True
request = table.update_item.call_args.kwargs
assert "lease_expires_at < :now" in request["ConditionExpression"]
assert request["ExpressionAttributeValues"][":lease"] == int(now.timestamp()) + 900
```

- [ ] **Step 2: Run idempotency tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_idempotency.py -v`

Expected: import fails because `idempotency.py` does not exist.

- [ ] **Step 3: Implement conditional state transitions**

Use `UpdateItem`, not read-then-write. Map `ConditionalCheckFailedException` to `False` only in `acquire`; propagate other SDK failures as `RetryableServiceError`. Terminal transition methods must require current state `processing`. `mark_retryable_failed` must preserve the attempt count and make the record reclaimable.

Store only sanitized error codes such as `slack_timeout`, `s3_upload_failed`, or `signing_failed`; never store exception text that may contain a URL or header.

- [ ] **Step 4: Run idempotency tests**

Run: `python -m pytest tests/slack_report_bot/test_idempotency.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit idempotency handling**

```powershell
git add infrastructure/slack_report_bot/app/idempotency.py tests/slack_report_bot/test_idempotency.py
git commit -m "feat: add report event processing leases"
```

---

### Task 8: Orchestrate the SQS Worker

**Files:**
- Modify: `infrastructure/slack_report_bot/app/ingress.py`
- Create: `infrastructure/slack_report_bot/app/metrics.py`
- Create: `infrastructure/slack_report_bot/app/worker.py`
- Modify: `tests/slack_report_bot/test_ingress.py`
- Create: `tests/slack_report_bot/test_metrics.py`
- Create: `tests/slack_report_bot/test_worker.py`

**Interfaces:**
- Consumes: every interface from Tasks 1, 4, 5, 6, and 7.
- Produces: `MetricsSink.emit(name: str, value: int, unit: str) -> None`, `ReportWorker.process(payload: Mapping[str, object], accepted_at: datetime) -> None`, `build_handler(dependencies) -> Callable`, and Lambda entry point `handler(event, context) -> dict[str, list[dict[str, str]]]` using SQS partial-batch responses.

- [ ] **Step 1: Write failing end-to-end orchestration tests**

Cover HTML-only success, HTML plus multiple CSVs, validation failure with no uploads, duplicate event suppression, deterministic overwrite, Slack failure, S3 failure, signer failure, and one SQS batch containing one success and one retryable failure.

The success assertion must verify operation order:

```python
worker.process(payload, accepted_at)

assert calls == [
    "acquire",
    "get_file:html",
    "get_file:csv",
    "download:html",
    "download:csv",
    "upload:html",
    "upload:csv",
    "sign:html",
    "sign:csv",
    "post_reply",
    "mark_completed",
]
```

- [ ] **Step 2: Run worker tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_worker.py -v`

Expected: import fails because `worker.py` does not exist.

- [ ] **Step 3: Implement the worker transaction boundary**

The worker must:

1. Parse `event_id`, `event.channel`, `event.ts`, and file IDs.
2. In the SQS handler, parse the required `AcceptedAtEpoch` message attribute into a UTC-aware `datetime`; a missing or invalid value is retryable and must never fall back to the current time.
3. Acquire the DynamoDB lease.
4. Resolve all files and validate declared sizes before downloading.
5. Download to a `TemporaryDirectory` under `/tmp`.
6. Decode HTML as UTF-8 with BOM support (`utf-8-sig`) and reject invalid UTF-8.
7. Extract the CL and calculate all S3 keys from the captured acceptance time.
8. Upload every file, then sign every link.
9. Create the Slack success text without logging its signed URLs.
10. Derive a stable Slack client message ID with `str(uuid.uuid5(uuid.NAMESPACE_URL, event_id))`.
11. Post once and mark completed with the returned reply timestamp.

For `ValidationError`, post one sanitized threaded error and mark `validation_failed`. For `RetryableServiceError`, mark `retryable_failed` and return the SQS record identifier in `batchItemFailures`.

- [ ] **Step 4: Add structured, redacted logging tests**

Capture logs with `caplog` and assert they contain event ID, CL, and S3 key but do not contain `xoxb-`, `X-Amz-Signature`, `Authorization`, a private-key header, or uploaded HTML text.

Create `MetricsSink` to emit CloudWatch Embedded Metric Format JSON in namespace `Cerebrus/SlackReportBot`, with only a `Function` dimension. Test and emit `InvalidSlackSignatures` from ingress, and `ValidationFailures`, `SuccessfulReports`, and `UploadedBytes` from the worker. Metric records may contain counts, function names, event IDs, and CL numbers, but never Slack/AWS secrets, filenames, file contents, or signed URLs.

- [ ] **Step 5: Run worker and full service tests**

Run:

```powershell
python -m pytest tests/slack_report_bot/test_worker.py -v
python -m pytest tests/slack_report_bot -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit worker orchestration**

```powershell
git add infrastructure/slack_report_bot/app/ingress.py infrastructure/slack_report_bot/app/metrics.py infrastructure/slack_report_bot/app/worker.py tests/slack_report_bot/test_ingress.py tests/slack_report_bot/test_metrics.py tests/slack_report_bot/test_worker.py
git commit -m "feat: process Slack report upload jobs"
```

---

### Task 9: Define SAM Infrastructure and Existing-Bucket Policy Integration

**Files:**
- Create: `infrastructure/slack_report_bot/template.yaml`
- Create: `infrastructure/slack_report_bot/scripts/configure_bucket_policy.py`
- Create: `tests/slack_report_bot/test_infrastructure.py`
- Create: `tests/slack_report_bot/test_provisioning_scripts.py`

**Interfaces:**
- Consumes: handlers `app.ingress.handler` and `app.worker.handler`.
- Produces: CloudFormation outputs `SlackEventsUrl`, `ReportDistributionDomain`, `ReportDistributionArn`, `SlackSigningSecretArn`, `SlackBotTokenArn`, and `CloudFrontPrivateKeySecretArn`; CLI `configure_bucket_policy.py --bucket NAME --distribution-arn ARN [--remove]`.

- [ ] **Step 1: Write failing infrastructure contract tests**

Parse `template.yaml` as YAML and assert it contains:

- HTTP API route `POST /slack/events`.
- Ingress and worker functions using Python 3.12.
- SQS queue with DLQ and `maxReceiveCount: 3`.
- Worker event source with `FunctionResponseTypes: [ReportBatchItemFailures]`.
- DynamoDB PAY_PER_REQUEST table with TTL attribute `expires_at`.
- Parameters referencing the three pre-provisioned Secrets Manager secret ARNs; the stack must not create, replace, or populate secret values.
- CloudFront OAC, key group using the supplied public-key ID, distribution, and signed-viewer restriction.
- CloudWatch alarms for ingress/worker errors, worker throttles, SQS oldest-message age, and DLQ visible-message count; attach `AlarmTopicArn` only when it is non-empty.
- No S3 bucket resource and no lifecycle rule.
- IAM resources scoped to the exact queue, table, secret ARNs, and `${ExistingReportBucketArn}/reports/*`.

- [ ] **Step 2: Run infrastructure tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_infrastructure.py tests/slack_report_bot/test_provisioning_scripts.py -v`

Expected: tests fail because the template and helper do not exist.

- [ ] **Step 3: Write the SAM template with explicit parameters**

Define these required parameters:

```yaml
Parameters:
  ExistingReportBucketName: {Type: String, MinLength: 3}
  ExistingReportBucketArn: {Type: String, AllowedPattern: '^arn:aws:s3:::.+'}
  SlackWorkspaceId: {Type: String, AllowedPattern: '^T[A-Z0-9]+$'}
  SlackChannelId: {Type: String, AllowedPattern: '^[GC][A-Z0-9]+$'}
  SlackSigningSecretArn: {Type: String, AllowedPattern: '^arn:aws:secretsmanager:.+'}
  SlackBotTokenArn: {Type: String, AllowedPattern: '^arn:aws:secretsmanager:.+'}
  CloudFrontPrivateKeySecretArn: {Type: String, AllowedPattern: '^arn:aws:secretsmanager:.+'}
  CloudFrontPublicKeyId: {Type: String, MinLength: 1}
  AlarmTopicArn: {Type: String, Default: ''}
```

Set function environment variables only to non-secret identifiers and secret ARNs. Use `Policies` statements scoped to specific resource ARNs. Configure worker ephemeral storage to 2048 MiB, timeout to 900 seconds, memory to 1024 MiB, and reserved concurrency to a conservative value of 5. Configure the ingress timeout to 10 seconds.

Create a CloudFront default cache behavior with `TrustedKeyGroups`, HTTPS redirect, OAC, and the S3 REST origin. Do not set `OriginPath`; signed URLs already begin with `/reports/`, and the separately merged bucket statement restricts CloudFront reads to `reports/*`. Do not create or replace an `AWS::S3::BucketPolicy` for the existing bucket.

- [ ] **Step 4: Implement an idempotent bucket-policy merger**

`configure_bucket_policy.py` must use the default boto3 credential chain, retrieve the current policy when present, and upsert only this statement by `Sid`:

```python
{
    "Sid": "AllowCerebrusReportCloudFrontRead",
    "Effect": "Allow",
    "Principal": {"Service": "cloudfront.amazonaws.com"},
    "Action": "s3:GetObject",
    "Resource": f"arn:aws:s3:::{bucket}/reports/*",
    "Condition": {"StringEquals": {"AWS:SourceArn": distribution_arn}},
}
```

Preserve every unrelated statement byte-for-byte at the parsed JSON-data level. `--remove` removes only this `Sid`; if no statements remain, delete the bucket policy, otherwise write the remaining policy. Print bucket name and action only, never credentials or full policies.

Before adding the statement, call `get_public_access_block` and require all four flags (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, and `RestrictPublicBuckets`) to be true. Refuse to modify the policy if the configuration is absent or weaker; the helper must never silently change the existing bucket's public-access settings.

- [ ] **Step 5: Validate SAM and run infrastructure tests**

Run:

```powershell
sam validate --lint --template-file infrastructure/slack_report_bot/template.yaml
python -m pytest tests/slack_report_bot/test_infrastructure.py tests/slack_report_bot/test_provisioning_scripts.py -v
```

Expected: SAM validation and all tests pass.

- [ ] **Step 6: Commit infrastructure**

```powershell
git add infrastructure/slack_report_bot/template.yaml infrastructure/slack_report_bot/scripts/configure_bucket_policy.py tests/slack_report_bot/test_infrastructure.py tests/slack_report_bot/test_provisioning_scripts.py
git commit -m "feat: define Slack report bot infrastructure"
```

---

### Task 10: Add Safe Key Provisioning and Deployment Automation

**Files:**
- Create: `infrastructure/slack_report_bot/scripts/provision_signing_key.py`
- Create: `infrastructure/slack_report_bot/scripts/provision_slack_secrets.py`
- Create: `infrastructure/slack_report_bot/scripts/deploy.ps1`
- Modify: `tests/slack_report_bot/test_provisioning_scripts.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: CLI `provision_signing_key.py --secret-name /cerebrus/cloudfront/private-key --comment "Cerebrus report links"` that outputs only JSON containing `public_key_id` and `private_key_secret_arn`; CLI `provision_slack_secrets.py --bot-token-secret-name /cerebrus/slack/bot-token --signing-secret-name /cerebrus/slack/signing-secret` that outputs only the two secret ARNs; `deploy.ps1` consumes environment variables and SAM parameters.
- Consumes: the default AWS credential chain and Task 9's template outputs.

- [ ] **Step 1: Write failing key-provisioning tests**

Inject CloudFront and Secrets Manager clients. Assert that the script:

- Generates RSA-2048 in memory.
- Sends only the private PEM to Secrets Manager.
- Sends only the public PEM to CloudFront.
- Prints no PEM, AWS key, or secret value.
- Returns an existing public-key ID when a key with the configured caller reference already exists.
- Reads Slack values only from `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`, creates or updates the named secrets, outputs only their ARNs, and never prints their values.

- [ ] **Step 2: Run provisioning tests and confirm failure**

Run: `python -m pytest tests/slack_report_bot/test_provisioning_scripts.py -v`

Expected: key-provisioning tests fail because the script does not exist.

- [ ] **Step 3: Implement in-memory RSA provisioning**

Generate with:

```python
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
private_pem = private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
public_pem = private_key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)
```

Immediately put `private_pem` into the configured Secrets Manager secret and create the CloudFront public key from `public_pem`. Do not write either key to disk. Sanitize all exceptions before printing.

Implement `provision_slack_secrets.py` with an injected Secrets Manager client. Require both environment variables, call `create_secret` or `put_secret_value` as appropriate, and emit JSON containing only `slack_bot_token_arn` and `slack_signing_secret_arn`. Redact all exception text to the operation name and AWS error code.

- [ ] **Step 4: Implement deployment preflight and SAM deployment**

`deploy.ps1` must fail before calling AWS if any of these are absent: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `CEREBRUS_REPORT_BUCKET`, `SLACK_WORKSPACE_ID`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET_ARN`, `SLACK_BOT_TOKEN_ARN`, `CLOUDFRONT_PRIVATE_KEY_SECRET_ARN`, and `CLOUDFRONT_PUBLIC_KEY_ID`. It must never echo their values.

Then run:

```powershell
sam validate --lint --template-file infrastructure/slack_report_bot/template.yaml
sam build --template-file infrastructure/slack_report_bot/template.yaml
sam deploy --stack-name cerebrus-slack-report-bot `
  --region $env:AWS_REGION `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --no-confirm-changeset `
  --no-fail-on-empty-changeset `
  --parameter-overrides `
  "ExistingReportBucketName=$env:CEREBRUS_REPORT_BUCKET" `
  "ExistingReportBucketArn=arn:aws:s3:::$env:CEREBRUS_REPORT_BUCKET" `
  "SlackWorkspaceId=$env:SLACK_WORKSPACE_ID" `
  "SlackChannelId=$env:SLACK_CHANNEL_ID" `
  "SlackSigningSecretArn=$env:SLACK_SIGNING_SECRET_ARN" `
  "SlackBotTokenArn=$env:SLACK_BOT_TOKEN_ARN" `
  "CloudFrontPrivateKeySecretArn=$env:CLOUDFRONT_PRIVATE_KEY_SECRET_ARN" `
  "CloudFrontPublicKeyId=$env:CLOUDFRONT_PUBLIC_KEY_ID"
```

After deployment, the script reads stack outputs and invokes `configure_bucket_policy.py` with the exact bucket and distribution ARN.

Add `.aws-sam/` to `.gitignore` so SAM build artifacts cannot be staged.

- [ ] **Step 5: Run tests and PowerShell syntax validation**

Run:

```powershell
python -m pytest tests/slack_report_bot/test_provisioning_scripts.py -v
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
  'infrastructure/slack_report_bot/scripts/deploy.ps1',
  [ref]$null,
  [ref]$errors
) | Out-Null
if ($errors.Count) { throw ($errors | Out-String) }
```

Expected: tests pass and PowerShell reports no syntax errors.

- [ ] **Step 6: Commit deployment automation**

```powershell
git add infrastructure/slack_report_bot/scripts/provision_signing_key.py infrastructure/slack_report_bot/scripts/provision_slack_secrets.py infrastructure/slack_report_bot/scripts/deploy.ps1 tests/slack_report_bot/test_provisioning_scripts.py .gitignore
git commit -m "feat: automate report bot provisioning"
```

---

### Task 11: Write Operator and QA Documentation

**Files:**
- Create: `infrastructure/slack_report_bot/README.md`
- Create: `docs/developer/SLACK_REPORT_BOT.md`
- Create: `docs/user/SLACK_REPORT_BOT.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: CloudFormation outputs and scripts from Tasks 9-10.
- Produces: exact human setup, staging acceptance, rollback, and QA usage instructions.

- [ ] **Step 1: Write the operator runbook**

Document the exact sequence:

1. Create the Slack app **Cerebrus Report Bot**.
2. Add bot scopes `groups:history`, `files:read`, and `chat:write`.
3. Install it, invite it to Cerebrus Feedback, and record workspace/channel IDs.
4. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in the current process, run `provision_slack_secrets.py`, and record only the two ARNs from its sanitized JSON output.
5. Run `provision_signing_key.py`; record the public-key ID and private-key secret ARN from its non-secret JSON output.
6. Set deployment environment variables, including all three secret ARNs, without printing their values.
7. Run `deploy.ps1`.
8. Configure Slack Event Subscriptions with the `SlackEventsUrl` output and subscribe to `message.groups`.
9. Run the five staging acceptance cases from the spec.
10. Monitor Lambda errors, SQS age, and DLQ depth.

Include rollback commands that disable Slack event subscriptions first, remove only the scoped bucket-policy statement via `--remove`, and then delete the stack. State explicitly that rollback does not delete S3 report objects.

- [ ] **Step 2: Write the QA guide**

Explain that QA posts exactly one self-contained Cerebrus `.html` file and optional Thermal `.csv` files in one message. Include the accepted Build Version example, expected threaded success reply, seven-day link behavior, overwrite behavior, and exact remedies for each validation message.

- [ ] **Step 3: Add discoverability links**

Add a concise **Slack Report Bot** link under the cloud/reporting area of root `README.md`, pointing to both the QA and developer guides. Do not add the service to the desktop plugin table.

- [ ] **Step 4: Verify documentation and references**

Run:

```powershell
rg -n "AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|groups:history|files:read|chat:write|message.groups|604800|Asia/Kolkata" infrastructure/slack_report_bot docs/developer/SLACK_REPORT_BOT.md docs/user/SLACK_REPORT_BOT.md
git diff --check
```

Expected: required names are present, no actual credentials appear, and `git diff --check` reports no errors.

- [ ] **Step 5: Commit documentation**

```powershell
git add infrastructure/slack_report_bot/README.md docs/developer/SLACK_REPORT_BOT.md docs/user/SLACK_REPORT_BOT.md README.md
git commit -m "docs: add Slack report bot runbook"
```

---

### Task 12: Perform Final Verification

**Files:**
- Modify only files required to correct failures found by the commands below.

**Interfaces:**
- Consumes: the complete service and infrastructure from Tasks 1-11.
- Produces: a verified implementation ready for staging deployment.

- [ ] **Step 1: Run the focused service suite**

Run: `python -m pytest tests/slack_report_bot -v`

Expected: every Slack report bot test passes.

- [ ] **Step 2: Run formatting, imports, and type checks**

Run:

```powershell
python -m black --check infrastructure/slack_report_bot tests/slack_report_bot
python -m isort --check-only infrastructure/slack_report_bot tests/slack_report_bot
python -m mypy infrastructure/slack_report_bot/app infrastructure/slack_report_bot/scripts
```

Expected: all commands pass.

- [ ] **Step 3: Validate and build the SAM application**

Run:

```powershell
sam validate --lint --template-file infrastructure/slack_report_bot/template.yaml
sam build --template-file infrastructure/slack_report_bot/template.yaml
```

Expected: SAM validation and build succeed without downloading or embedding credentials.

- [ ] **Step 4: Run the repository suite**

Run: `python -m pytest tests`

Expected: the full suite passes. Do not claim full-suite success if it does not complete.

- [ ] **Step 5: Confirm secret and artifact hygiene**

Run:

```powershell
rg -n "AKIA[0-9A-Z]{16}|xox[baprs]-|BEGIN (RSA )?PRIVATE KEY|AWS_SECRET_ACCESS_KEY\s*=" infrastructure/slack_report_bot tests/slack_report_bot docs
git status --short
```

Expected: the scan finds only explanatory variable names or synthetic test markers, no real credentials or private keys. Confirm `.aws-sam/`, `.pytest_run_tmp/`, downloaded Slack files, and generated keys are not staged.

- [ ] **Step 6: Commit verification-only corrections if needed**

If verification required code or documentation corrections, stage only those named files and commit:

```powershell
git add --update infrastructure/slack_report_bot tests/slack_report_bot docs/developer/SLACK_REPORT_BOT.md docs/user/SLACK_REPORT_BOT.md README.md .github/workflows/tests.yml
git commit -m "fix: satisfy Slack report bot verification"
```

If no corrections were required, do not create an empty commit.
