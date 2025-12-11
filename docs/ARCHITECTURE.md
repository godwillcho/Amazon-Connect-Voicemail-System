# Architecture

System design and technical details of the Amazon Connect Voicemail System.

## System Overview

```
┌─────────────┐
│   Caller    │
└──────┬──────┘
       │
       │ Calls
       ▼
┌─────────────────────────────────────────┐
│        Amazon Connect                   │
│  ┌───────────────────────────────────┐  │
│  │  Contact Flow                     │  │
│  │  1. Play instructions             │  │
│  │  2. Play beep                     │  │
│  │  3. Invoke Lambda (async) ────────┼──┼──┐
│  │  4. Start recording               │  │  │
│  │  5. Wait for # or timeout         │  │  │
│  │  6. Stop recording                │  │  │
│  │  7. Upload to S3                  │  │  │
│  │  8. Disconnect                    │  │  │
│  └───────────────────────────────────┘  │  │
└──────────┬──────────────────────────────┘  │
           │                                  │
           │ Recording saved                  │
           ▼                                  │
    ┌────────────┐                           │
    │     S3     │◄──────────────────────────┼──┐
    │  Bucket    │                            │  │
    └────────────┘                            │  │
                                              │  │
                                              ▼  │
                                      ┌────────────────┐
                                      │  AWS Lambda    │
                                      │  (Async)       │
                                      │                │
                                      │  1. Wait 70s   │
                                      │  2. Find file  │◄─┐
                                      │  3. Transcribe │  │
                                      │  4. Send email │  │
                                      └────┬───────────┘  │
                                           │              │
                     ┌─────────────────────┼──────────────┘
                     │                     │
                     │                     │
          ┌──────────▼─────────┐   ┌──────▼──────────┐
          │  AWS Transcribe    │   │   Amazon SES    │
          │  (Speech-to-text)  │   │  (Email)        │
          └────────────────────┘   └─────────┬───────┘
                                             │
                                             │
                                             ▼
                                      ┌────────────┐
                                      │ Recipient  │
                                      │   Email    │
                                      └────────────┘
```

## Component Details

### 1. Amazon Connect Contact Flow

**Purpose**: Manages caller interaction and recording

**Key Blocks**:

| Block | Type | Function |
|-------|------|----------|
| Enable Logging | UpdateFlowLoggingBehavior | Enables CloudWatch logging |
| Set Attributes | UpdateContactAttributes | Sets emailRecipient and RecipientName |
| Play Instructions | MessageParticipant | "Record a voice message..." |
| Play Beep | MessageParticipant | Audio cue to start |
| Invoke Lambda | InvokeLambdaFunction | Triggers processing (ASYNC) |
| Start Recording | UpdateContactRecordingBehavior | Enables IVR recording |
| Get Input | GetParticipantInput | Waits for # or timeout |
| Stop Recording | UpdateContactRecordingBehavior | Disables IVR recording |
| Thank You | MessageParticipant | "We will get back to you" |
| Disconnect | DisconnectParticipant | Ends call |

**Flow Sequence**:

```
1. EnableLogging
2. SetAttributes (emailRecipient, RecipientName)
3. PlayInstructions
4. PlayBeep
5. InvokeLambda (ASYNCHRONOUS) ──┐
6. StartRecording                 │ Lambda starts waiting
7. GetInput (# or 5s timeout)     │
8. StopRecording                  │
9. ThankYou                       │
10. Disconnect                     │
                                   │ 70 seconds later...
                                   └─> Lambda searches for file
```

**Critical Configuration**:
- Lambda invocation: **ASYNCHRONOUS** (non-blocking)
- Timeout: 5 seconds (adjustable to 60s for production)
- DTMF: "#" key stops recording

### 2. AWS Lambda Function

**Runtime**: Python 3.9  
**Memory**: 512 MB  
**Timeout**: 180 seconds  
**Invocation**: Asynchronous from Connect

**Execution Flow**:

```python
1. Validate environment variables
   ├─ BASE_PATH (required)
   ├─ EMAIL_SENDER (required)
   ├─ URL_EXPIRATION (default: 604800)
   └─ RECORDING_WAIT_TIME (default: 70)

2. Extract contact data
   ├─ Initial contact ID
   ├─ Caller number
   ├─ Email recipient
   └─ Recipient name

3. Wait for recording completion
   └─ sleep(RECORDING_WAIT_TIME)

4. Search for recording in S3
   ├─ Generate potential S3 URIs
   │  └─ Time windows: ±5, ±4, ±3, ±2, ±1 minutes
   ├─ Check each location
   └─ Retry after 30s if not found

5. Transcribe audio
   ├─ Start Transcribe job
   ├─ Wait for completion (max 600s)
   ├─ Fetch results
   └─ Build transcription preview

6. Calculate duration
   └─ Extract last speech timestamp

7. Generate presigned URL
   └─ 7-day expiration (configurable)

8. Send email
   ├─ HTML format (with button)
   ├─ Plain text fallback
   └─ Via SES

9. Return success/error
```

**Key Functions**:

| Function | Purpose |
|----------|---------|
| `validate_environment()` | Checks required env vars |
| `find_recording_in_s3()` | Locates recording file |
| `start_transcription_job()` | Initiates Transcribe |
| `wait_for_transcription()` | Polls for completion |
| `build_transcription_preview()` | Formats transcript |
| `get_actual_recording_duration()` | Calculates speech time |
| `create_html_email()` | Generates HTML body |
| `send_email_with_recording()` | Sends via SES |

**Error Handling**:

```python
try:
    # Main logic
except ValueError:
    return {"statusCode": 500, "message": "Configuration error"}
except ClientError:
    return {"statusCode": 500, "message": "AWS service error"}
except TimeoutError:
    return {"statusCode": 504, "message": "Transcription timeout"}
except Exception:
    return {"statusCode": 500, "message": "Unexpected error"}
```

### 3. Amazon S3

**Purpose**: Stores voicemail recordings

**Bucket Structure**:
```
your-bucket/
└── connect/
    └── recordings/
        └── ivr/
            └── 2024/
                └── 12/
                    └── 11/
                        └── contactId_20241211T15:30_UTC.wav
```

**File Naming Convention**:
```
{contactId}_{timestamp}_UTC.wav
```

**Example**:
```
abc123def456_20241211T15:30_UTC.wav
```

**Access Pattern**:
1. Connect uploads: `PutObject` (managed automatically)
2. Lambda reads: `HeadObject` (check existence), `GetObject` (download for presigning)

**Security**:
- Server-side encryption (AES256 or KMS)
- Bucket policy restricts access
- Presigned URLs expire after 7 days

### 4. AWS Transcribe

**Purpose**: Converts speech to text

**Job Configuration**:
```python
{
    "TranscriptionJobName": "voicemail-transcribe-{timestamp}",
    "Media": {"MediaFileUri": "s3://bucket/key.wav"},
    "LanguageCode": "en-US",
    "MediaFormat": "wav",
    "Settings": {
        "ChannelIdentification": True  # Separate channels
    }
}
```

**Processing Time**:
- ~1-2 minutes for 60-second audio
- Faster for shorter recordings

**Output Format**:
```json
{
  "results": {
    "transcripts": [
      {"transcript": "Full text here"}
    ],
    "items": [
      {
        "start_time": "0.0",
        "end_time": "0.5",
        "alternatives": [{"content": "Hello"}],
        "type": "pronunciation"
      }
    ]
  }
}
```

**Duration Calculation**:
- Find last item with `end_time`
- Excludes trailing silence
- Displays actual speech duration

### 5. Amazon SES

**Purpose**: Sends email notifications

**Email Structure**:

```
From: noreply@example.com
To: user@example.com
Subject: Voicemail message from: +1234567890

HTML Body:
  ┌────────────────────────────────┐
  │ Voicemail for: John Doe        │
  │ From: +1234567890              │
  │ ┌──────────────────────────┐   │
  │ │  Listen to voicemail     │   │
  │ └──────────────────────────┘   │
  │ Duration: 15s                  │
  │                                │
  │ Transcription:                 │
  │ ┃ Message text here...         │
  └────────────────────────────────┘

Plain Text Fallback:
  Voicemail for: John Doe
  From: +1234567890
  Duration: 15s
  
  Transcription:
  Message text here...
  
  Link: https://s3.amazonaws.com/...
```

**Delivery**:
- Typical delivery: <1 minute
- Retry logic: Handled by SES
- Bounce handling: Not implemented (optional)

## Data Flow

### Timeline

```
T+0s:    Caller hears beep
T+0s:    Lambda invoked (async, returns immediately)
T+0s:    Connect starts recording
T+0s:    Lambda begins waiting (70s)

T+15s:   Caller presses # (or T+60s timeout)
T+15s:   Connect stops recording
T+15s:   File uploads to S3 (~5-10s)
T+15s:   Caller hears "Thank you"
T+15s:   Call disconnects

T+70s:   Lambda wakes up
T+70s:   Lambda searches for file
T+71s:   File found in S3
T+71s:   Transcribe job started
T+72s:   Transcribe processing...
T+120s:  Transcribe complete
T+121s:  Email sent
T+122s:  Lambda returns success
```

### Wait Strategy

**Why wait 70 seconds?**

1. Max recording: 60 seconds (configurable)
2. Upload time: ~5-10 seconds
3. Buffer: Extra safety margin
4. Total: 70 seconds

**Adjustable for different recording lengths**:
- 30s recording → 40s wait
- 60s recording → 70s wait
- 90s recording → 100s wait

### Search Strategy

**Expanding Time Windows**:

```
Attempt 1: ±5 minutes from now
├─ Check: now-5m, now-4m, ..., now, ..., now+5m
└─ Priority: Closest to now first

Not found? Try:

Attempt 2: ±4 minutes from now
├─ Check: now-4m, ..., now, ..., now+4m
└─ Priority: Closest to now

Continue narrowing: ±3m, ±2m, ±1m

Still not found after 30s?
└─ Wait additional 30s and retry entire sequence
```

## Scaling Considerations

### Concurrency

**Lambda**:
- Default: 1000 concurrent executions
- Async invocation: Queued if limit reached
- Auto-scales: No configuration needed

**Transcribe**:
- Default: 100 concurrent jobs
- Can request increase
- Jobs queue if limit reached

**SES**:
- Sandbox: 1 email/second
- Production: 14 emails/second (can increase)

### Cost at Scale

| Volume | Lambda | Transcribe | S3 | SES | Total/month |
|--------|--------|------------|----|----|-------------|
| 100 voicemails | $0.001 | $2.40 | $0.01 | $0.01 | **$2.42** |
| 1,000 voicemails | $0.014 | $24.00 | $0.10 | $0.10 | **$24.24** |
| 10,000 voicemails | $0.140 | $240.00 | $1.00 | $1.00 | **$242.14** |

### Performance

**Average execution time**: ~120 seconds
- Wait: 70s
- Search: 2s
- Transcribe: 45s
- Email: 1s
- Overhead: 2s

**Optimization opportunities**:
1. Reduce wait time if recordings are shorter
2. Use reserved concurrency for consistent performance
3. Enable X-Ray for detailed tracing

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────┐
│            IAM Role: Lambda                 │
├─────────────────────────────────────────────┤
│ Trust Policy:                               │
│   Principal: lambda.amazonaws.com           │
│                                             │
│ Permissions:                                │
│   ✓ S3: GetObject, HeadObject              │
│   ✓ Transcribe: Start/Get Job              │
│   ✓ SES: SendEmail                          │
│   ✓ CloudWatch: Logs                        │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│       S3 Bucket Policy                      │
├─────────────────────────────────────────────┤
│ Allow:                                      │
│   Principal: connect.amazonaws.com          │
│   Action: PutObject                         │
│   Resource: bucket/recordings/*             │
│                                             │
│ Allow:                                      │
│   Principal: Lambda Role                    │
│   Action: GetObject, HeadObject             │
│   Resource: bucket/recordings/*             │
└─────────────────────────────────────────────┘
```

### Data Protection

**In Transit**:
- HTTPS for all API calls
- TLS 1.2+ enforced

**At Rest**:
- S3: Server-side encryption (AES-256 or KMS)
- CloudWatch Logs: Encrypted by default

**Access Control**:
- Presigned URLs: Time-limited (7 days)
- No public S3 bucket access
- IAM roles follow least privilege

## Monitoring Architecture

### CloudWatch Integration

```
┌─────────────────────────────────────────────┐
│              CloudWatch                     │
├─────────────────────────────────────────────┤
│                                             │
│  Logs:                                      │
│    /aws/lambda/voicemail-transcribe-email   │
│    /aws/connect/instance-id                 │
│                                             │
│  Metrics:                                   │
│    Lambda: Invocations, Errors, Duration    │
│    Transcribe: JobsStarted, JobsFailed      │
│    SES: Sent, Bounced, Complaints           │
│                                             │
│  Alarms:                                    │
│    Lambda Errors > 5                        │
│    Lambda Duration > 150s                   │
│                                             │
└─────────────────────────────────────────────┘
```

### Logging Levels

**Lambda**:
- INFO: Normal execution flow
- WARNING: Recoverable issues
- ERROR: Failures requiring attention

**Key Log Messages**:
```
[INFO] VOICEMAIL PROCESSING STARTED
[INFO] Contact ID: xxx
[INFO] Waiting 70 seconds...
[INFO] [SUCCESS] Found file at s3://...
[INFO] [TRANSCRIBE END] Status: COMPLETED
[INFO] [EMAIL SENT] MessageId: xxx
```

## Reliability & Fault Tolerance

### Retry Logic

**Lambda Async Invocation**:
- Automatic retry: 2 times
- Exponential backoff
- Dead letter queue (optional)

**S3 File Search**:
- 2 search attempts
- 30-second wait between attempts
- Expanding time windows

**Transcribe**:
- Polls every 3 seconds
- Max wait: 600 seconds
- Fails gracefully if timeout

### Error Recovery

| Error Type | Recovery Strategy |
|------------|------------------|
| S3 not found | Retry with longer wait |
| Transcribe failed | Return partial result |
| SES bounce | Log error, continue |
| Lambda timeout | Increase timeout setting |

---

**Next**: [Configuration Guide](CONFIGURATION.md) | [Troubleshooting](TROUBLESHOOTING.md)
