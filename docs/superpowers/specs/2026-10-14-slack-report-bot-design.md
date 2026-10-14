# Slack Report Bot Design

## Summary

Create an AWS-hosted Slack bot for the private **Cerebrus Feedback** channel.
When QA posts one Cerebrus HTML report and optional Thermal CSV files in a
single Slack message, the bot validates the files, extracts the changelist
number from the HTML report, uploads the files to the existing private
Cerebrus S3 bucket, and replies in the same Slack thread with CloudFront
signed links that remain valid for seven days.

This service is separate from the Cerebrus desktop runtime. It will live under
`infrastructure/slack_report_bot/` and be deployed as an AWS SAM application.

## Goals

- Accept reports only from the configured private Slack channel.
- Require exactly one HTML report per Slack message.
- Accept zero or more Thermal CSV files in the same message.
- Extract the CL number from the HTML report's **Build Version** table row.
- Store the HTML and CSV files under the same CL-based S3 prefix.
- Replace existing objects when the same date, CL, and filename are uploaded
  again.
- Keep S3 private and return links that remain usable for seven days.
- Acknowledge Slack quickly and process uploads asynchronously and
  idempotently.
- Use least-privilege AWS roles and keep all non-AWS secrets out of source and
  Lambda configuration.

## Non-goals

- Changing the Cerebrus desktop AWS Secrets plugin.
- Uploading reports directly from the Cerebrus desktop application.
- Accepting files from other Slack channels, direct messages, or public
  channels.
- Supporting report assets other than one HTML file and optional CSV files.
- Automatically deleting stored reports. Objects remain in S3 until a future
  retention policy is approved.
- Making S3 objects public.

## Architecture

```text
Private Slack channel
        |
        v
API Gateway -> Ingress Lambda -> SQS -> Worker Lambda
                                          |-- Slack files.info/download
                                          |-- HTML validation + CL extraction
                                          |-- DynamoDB idempotency state
                                          |-- Existing private S3 bucket
                                          |-- CloudFront signed URLs
                                          `-- Slack threaded reply
```

### Components

1. **Slack app** receives private-channel message events and supplies the bot
   token and signing secret.
2. **API Gateway** exposes a single HTTPS Slack Events API endpoint.
3. **Ingress Lambda** verifies Slack signatures, handles Slack URL
   verification, filters the workspace/channel/event, and sends accepted
   events to SQS.
4. **SQS queue** decouples Slack acknowledgement from file processing. A
   dead-letter queue receives jobs that exhaust retries.
5. **Worker Lambda** downloads and validates the Slack files, extracts the CL,
   uploads objects, creates signed URLs, and posts the result to Slack.
6. **DynamoDB table** stores Slack `event_id` processing state so retries do
   not create duplicate work or duplicate replies.
7. **Existing Cerebrus S3 bucket** stores reports under the reserved
   `reports/` prefix.
8. **CloudFront distribution** uses Origin Access Control (OAC) to read only
   the S3 report prefix and requires signed viewer URLs.
9. **Secrets Manager** stores Slack secrets and the CloudFront signing private
   key.
10. **CloudWatch** stores logs and alarms on Lambda errors, queue age, and
    dead-letter queue messages.

## Slack Configuration

Create a Slack app named **Cerebrus Report Bot** with these bot scopes:

- `groups:history` to receive messages from the private channel.
- `files:read` to inspect and download files shared with the bot.
- `chat:write` to post success and validation messages.

Subscribe the bot to the `message.groups` event. Invite the bot to the private
**Cerebrus Feedback** channel. Configure the deployed API Gateway URL as the
Events API request URL and complete Slack's URL-verification handshake.

The ingress accepts only the configured Slack workspace and channel IDs. It
ignores bot-authored messages, message edits/deletions, messages without files,
and events from any other conversation. The bot token and signing secret are
never logged.

## AWS Authentication

Deployment commands use the AWS SDK default credential chain. The developer or
CI environment provides:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN       # optional for temporary credentials
AWS_REGION
```

The deployment must not copy these values into SAM parameters, CloudFormation
outputs, Lambda configuration, files, or logs.

At runtime, Lambda uses temporary credentials supplied automatically through
its execution role. Application code constructs AWS SDK clients without
explicit credentials. The CloudFront signing key is not an AWS access key; its
private half is stored separately in Secrets Manager.

## Event Ingress

The ingress Lambda performs these steps:

1. Preserve the raw HTTP request body.
2. Reject timestamps more than five minutes from the current time.
3. Recalculate and constant-time compare the `X-Slack-Signature` using the
   signing secret.
4. Return the `challenge` value for Slack URL-verification requests.
5. For event callbacks, verify the configured workspace ID and private-channel
   ID.
6. Accept only human-authored private-channel message events containing files.
7. Send the complete event envelope to SQS with Slack `event_id` as a message
   attribute.
8. Return HTTP 200 immediately after SQS accepts the event.

Signature failures return HTTP 401. Valid but irrelevant Slack events return
HTTP 200 without queuing so Slack does not retry them.

## File Processing

For each accepted Slack message, the worker:

1. Atomically claims a DynamoDB record keyed by Slack `event_id`. Completed or
   permanently failed events are ignored. An active processing lease blocks a
   concurrent duplicate, while an expired lease or retryable failure can be
   reclaimed by an SQS retry.
2. Resolves each Slack file through `files.info` and downloads it from
   `url_private_download` with the bot token in the Authorization header.
3. Requires exactly one filename ending in `.html`, case-insensitively.
4. Accepts zero or more filenames ending in `.csv`, case-insensitively.
5. Rejects the entire message if it contains any other uploaded file type.
6. Rejects filenames containing path separators, control characters, or an
   empty basename.
7. Streams downloads to Lambda temporary storage. The maximum is 512 MiB per
   file and 1 GiB for the complete Slack message; exceeding either limit is a
   permanent validation error.
8. Parses the HTML with an HTML parser rather than regular expressions over
   raw markup.
9. Finds the table row whose normalized first cell is exactly `Build Version`.
10. Extracts the CL digits from the second cell using `-CL-(\d+)\b`.
11. Rejects missing, ambiguous, or non-numeric CL values.
12. Completes all downloads and validation before beginning S3 uploads.

Given this HTML value:

```text
++titan-game+development-CL-51333
```

the extracted CL is `51333`.

## S3 Object Layout

The date uses the `Asia/Kolkata` timezone at the time the Slack event is
accepted:

```text
reports/YYYY/MM/DD/<CL-number>/<original-filename>
```

Example:

```text
reports/2026/10/14/51333/report.html
reports/2026/10/14/51333/thermal.csv
```

The worker uses deterministic keys, so a later upload with the same date, CL,
and filename replaces the existing object. HTML objects use content type
`text/html; charset=utf-8` and inline content disposition. CSV objects use
content type `text/csv; charset=utf-8` and attachment content disposition.
Server-side encryption remains enabled according to the existing bucket's
policy.

No lifecycle expiration is added. The seven-day limit applies only to links,
not stored objects.

## Private Download Links

The existing S3 bucket keeps Block Public Access enabled. A CloudFront OAC and
bucket policy grant the CloudFront distribution `s3:GetObject` only for
`reports/*`. The distribution behavior trusts one CloudFront public-key group
and rejects unsigned viewer requests.

The worker reads the matching private signing key from Secrets Manager and
creates one CloudFront signed URL per uploaded object. Each URL expires exactly
604800 seconds (seven days) after successful processing. This avoids the
shorter effective lifetime of S3 presigned URLs made with Lambda's temporary
execution-role credentials.

The CloudFront hostname is dedicated to these reports and carries no
authentication cookies. HTML reports open inline; CSV files download.

## Slack Replies

On success, the worker calls `chat.postMessage` with the original message's
timestamp as `thread_ts`:

```text
✅ Cerebrus report uploaded
CL: 51333

• HTML Report: <signed URL>
• Thermal CSV: <signed URL>     # one line per CSV, when present

Links expire in 7 days. Files remain stored in S3.
```

Permanent validation failures produce one threaded error describing the exact
problem and upload nothing. Examples include missing HTML, multiple HTML files,
unsupported files, unsafe filenames, size-limit violations, and missing or
ambiguous CL values.

Transient Slack, S3, Secrets Manager, CloudFront-signing, and DynamoDB failures
raise an error so SQS retries the job. Processing is deterministic, so a retry
can safely replace any partially uploaded object. A success reply is posted
only after every object is uploaded and every signed URL is generated.

When retries are exhausted, SQS moves the event to the dead-letter queue and a
CloudWatch alarm notifies operators. Redrive reuses the same Slack `event_id`
and processing record rather than creating a second report.

## Idempotency State

The DynamoDB record contains:

- Slack `event_id` as the partition key.
- State: `processing`, `completed`, `validation_failed`, or `retryable_failed`.
- Processing-lease expiration and attempt count.
- Slack channel ID and parent message timestamp.
- Extracted CL number when available.
- Final S3 keys when completed.
- Creation and update timestamps.
- A TTL fourteen days after creation for automatic idempotency-record cleanup.

The TTL applies only to DynamoDB state; it does not delete S3 objects.
Workers acquire and extend a short processing lease with conditional writes.
They set `completed` only after posting the success reply, set
`validation_failed` after posting a permanent error, and set
`retryable_failed` before raising a transient error. This lets SQS retries
resume abandoned work without allowing concurrent workers to post twice.

## IAM Boundaries

The ingress role can:

- Read only the Slack signing-secret secret.
- Send messages only to the report-processing SQS queue.
- Write its CloudWatch logs.

The worker role can:

- Consume only the report-processing queue.
- Read only the Slack bot-token and CloudFront private-key secrets.
- Put objects only under the existing bucket's `reports/*` prefix.
- Read and update only the bot's DynamoDB idempotency table.
- Write its CloudWatch logs.

The CloudFront OAC can read only the existing bucket's `reports/*` prefix and
only when the request originates from the configured distribution. Neither
Lambda role receives permission to administer IAM, CloudFront, or the S3
bucket at runtime.

## Infrastructure Parameters

The SAM/CloudFormation deployment requires non-secret parameters for:

- Existing S3 bucket name and region.
- Slack workspace ID.
- Cerebrus Feedback channel ID.
- Secrets Manager ARNs for the Slack signing secret, Slack bot token, and
  CloudFront private key.
- CloudFront public-key ID and distribution settings.
- Optional CloudWatch alarm destination.

AWS access keys are intentionally not stack parameters.

## Observability

Logs use Slack event IDs, file IDs, CL numbers, and S3 keys as correlation
fields. Logs never contain Slack tokens, signing secrets, AWS credentials,
CloudFront private keys, file contents, Authorization headers, or signed URL
query strings.

Metrics and alarms cover:

- Invalid Slack signatures.
- Permanent validation failures.
- Worker errors and throttling.
- SQS oldest-message age.
- Dead-letter queue depth.
- Successful reports and uploaded bytes.

## Testing

### Unit tests

- Valid and invalid Slack signatures, including replay-window rejection.
- Workspace/channel filtering and bot-message suppression.
- Exactly-one-HTML validation and optional multiple CSV files.
- Unsupported extensions, unsafe filenames, and size limits.
- Build Version parsing for the approved HTML table shape.
- Missing, duplicate, ambiguous, and malformed CL values.
- `Asia/Kolkata` S3 date paths.
- Deterministic overwrite keys and content metadata.
- Seven-day CloudFront policy expiration.
- DynamoDB conditional idempotency transitions.
- Redaction of secrets and signed query strings from logs.

### Integration tests

- Slack API calls are mocked while exercising the complete ingress-to-worker
  event shape.
- S3, SQS, DynamoDB, Secrets Manager, and CloudFront signer boundaries are
  tested through SDK fakes or an isolated test stack.
- Retry tests prove duplicate Slack events do not generate duplicate replies.
- Partial-upload retry tests prove deterministic overwrites reach the final
  complete state.

### Staging acceptance test

In a separate private Slack test channel, upload:

1. A valid HTML-only report.
2. A valid HTML report plus Thermal CSV.
3. A report missing the CL entry.
4. A message containing multiple HTML reports.
5. The same valid report twice.

Verify threaded responses, India-time S3 keys, overwrite behavior, private S3
access, seven-day CloudFront expiration, idempotency, and alarms without using
production report data.

## Rollout

1. Create the Slack app and requested scopes without enabling events.
2. Deploy the AWS stack using environment-provided deployment credentials.
3. Add the Slack and CloudFront signing secrets to Secrets Manager.
4. Configure the CloudFront public key, key group, OAC, and bucket policy.
5. Enable the Slack Events API endpoint and `message.groups` subscription.
6. Install or reinstall the Slack app and invite it to the private channel.
7. Run the staging acceptance test.
8. Configure the production channel ID and perform one controlled QA upload.
9. Monitor the queue, Lambda errors, and Slack reply before announcing the bot.

## Primary References

- Slack private-channel events:
  <https://docs.slack.dev/reference/events/message.groups>
- Slack request verification:
  <https://docs.slack.dev/authentication/verifying-requests-from-slack/>
- Slack private file access:
  <https://docs.slack.dev/reference/objects/file-object/>
- Slack threaded replies:
  <https://docs.slack.dev/reference/methods/chat.postMessage/>
- AWS Lambda authentication:
  <https://docs.aws.amazon.com/sdkref/latest/guide/access.html>
- S3 presigned URL credential lifetime:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>
- CloudFront signed URLs:
  <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html>
- CloudFront private S3 origins:
  <https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-overview.html>
- SQS and Lambda retry semantics:
  <https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html>
