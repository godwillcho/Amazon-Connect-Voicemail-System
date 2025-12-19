"""
AWS Lambda function for processing Amazon Connect voicemail recordings.
Also serves as Function URL endpoint for generating presigned URLs on-demand.

================================================================================
SETUP INSTRUCTIONS
================================================================================

STEP 1: GENERATE SIGNING SECRET
--------------------------------
Run this command in your terminal:
    openssl rand -base64 32

Copy the output (e.g., "k7vM3nQ9pL2xR8wT5yH1bN6mJ4cV0gF3sA7dE9uI2oP=")


STEP 2: CREATE LAMBDA FUNCTION
--------------------------------
1. Go to AWS Lambda Console
2. Create new function or update existing one
3. Paste this entire code into the code editor
4. Click "Deploy"


STEP 3: CREATE FUNCTION URL
--------------------------------
1. In Lambda Console, go to Configuration → Function URL
2. Click "Create function URL"
3. Auth type: NONE
4. Click "Save"
5. Copy the Function URL (e.g., "https://abc123.lambda-url.us-east-1.on.aws/")


STEP 4: CONFIGURE ENVIRONMENT VARIABLES
--------------------------------
In Lambda Console, go to Configuration → Environment variables → Edit

Add these 6 variables:

    BASE_PATH              = your-bucket-name/recordings
    EMAIL_SENDER           = voicemail@yourdomain.com
    URL_EXPIRATION         = 604800
    RECORDING_WAIT_TIME    = 70
    SIGNING_SECRET         = (paste from Step 1)
    REDIRECT_API_URL       = (paste from Step 3)


STEP 5: UPDATE IAM PERMISSIONS
--------------------------------
Your Lambda execution role needs these permissions:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:HeadObject"],
            "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
        },
        {
            "Effect": "Allow",
            "Action": ["transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "ses:SendEmail",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "*"
        }
    ]
}

To add: IAM Console → Roles → Your Lambda Role → Add permissions → Create inline policy


STEP 6: CONFIGURE LAMBDA SETTINGS
--------------------------------
1. Go to Configuration → General configuration → Edit
2. Set Memory: 512 MB (or higher)
3. Set Timeout: 15 minutes (900 seconds)
4. Click "Save"


STEP 7: VERIFY SES EMAIL
--------------------------------
1. Go to Amazon SES Console
2. Click "Verified identities"
3. Add and verify your EMAIL_SENDER address
4. If in sandbox, also verify recipient addresses


STEP 8: CONFIGURE AMAZON CONNECT
--------------------------------
In your Amazon Connect contact flow:

1. Add "Set recording and analytics behavior" block
   - Set recording behavior: Enable
   - Place BEFORE customer speaks

2. Add "Set contact attributes" block
   - Destination key: emailRecipient
   - Value: support@company.com (or dynamic value)
   
   (Optional)
   - Destination key: RecipientName
   - Value: Support Team

3. Add "Invoke AWS Lambda function" block
   - Select this Lambda function
   - Place AFTER recording completes

4. Publish contact flow


STEP 9: TEST
--------------------------------
1. Call your Amazon Connect number
2. Leave a voicemail
3. Check email for notification
4. Click the link - voicemail should play


TROUBLESHOOTING
--------------------------------
Check CloudWatch Logs for:
    [SUCCESS] Found at s3://...        ← Recording found
    [TRANSCRIBE START]                 ← Transcription started
    [SIGNED URL] Created               ← URL generated
    [EMAIL SENT]                       ← Email sent successfully

Common Issues:
    "Missing emailRecipient"           → Set attribute in contact flow
    "Recording not found"              → Check BASE_PATH and recording enabled
    "403 Forbidden" on link click      → Verify SIGNING_SECRET matches
    "Email send failed"                → Verify SES email and permissions

================================================================================
ENVIRONMENT VARIABLES
================================================================================

Required:
    BASE_PATH: S3 bucket/prefix for recordings (e.g., "my-bucket/recordings")
    EMAIL_SENDER: Sender email address (must be verified in SES)
    SIGNING_SECRET: Secret key for HMAC URL signing (generate with openssl)
    REDIRECT_API_URL: Lambda Function URL (from Configuration → Function URL)

Optional (with defaults):
    URL_EXPIRATION: Link expiration in seconds (default: 604800 = 7 days)
    RECORDING_WAIT_TIME: Wait time for recording upload (default: 70 seconds)

================================================================================
AMAZON CONNECT REQUIREMENTS
================================================================================

Your contact flow must:
    1. Enable call recording (Set recording behavior block)
    2. Set "emailRecipient" attribute (REQUIRED)
    3. Set "RecipientName" attribute (optional, defaults to email)
    4. Invoke this Lambda function after recording

Event structure Lambda receives:
    {
        "Details": {
            "ContactData": {
                "InitialContactId": "abc-123",           ← Used to find recording
                "CustomerEndpoint": {
                    "Address": "+18607866359"            ← Caller number
                },
                "InstanceARN": "arn:aws:connect:...",    ← Determines region
                "Attributes": {
                    "emailRecipient": "user@example.com", ← REQUIRED
                    "RecipientName": "John Smith"         ← Optional
                }
            }
        }
    }

================================================================================
HOW IT WORKS
================================================================================

1. Amazon Connect records voicemail → uploads to S3
2. Contact flow invokes this Lambda
3. Lambda waits for recording to finish uploading
4. Lambda searches S3 for recording file
5. Lambda transcribes audio using AWS Transcribe
6. Lambda generates secure signed URL (valid 7 days)
7. Lambda sends email with transcription and link
8. User clicks link → Lambda validates signature → redirects to S3
9. Voicemail plays in browser

Security:
    - URLs are cryptographically signed (HMAC-SHA256)
    - URLs expire after configured time
    - Signature prevents tampering
    - No API Gateway needed (uses Function URL)

================================================================================
"""

import os
import json
import boto3
import logging
import time
import hmac
import hashlib
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError
from botocore.config import Config
from urllib.parse import quote, unquote

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
DEFAULT_LANGUAGE = "en-US"
DEFAULT_PREVIEW_LEN = 700
DEFAULT_MODE = "channel"
TRANSCRIBE_MAX_WAIT_SECS = 600
TRANSCRIBE_POLL_SECS = 3
MAX_TIME_WINDOW_MINUTES = 5


# =============================================================================
# EXCEPTION CLASSES
# =============================================================================

class VoicemailProcessingError(Exception):
    """Base exception for voicemail processing errors."""
    pass


class TranscriptionError(VoicemailProcessingError):
    """Raised when transcription fails."""
    pass


# =============================================================================
# URL SIGNING FUNCTIONS
# =============================================================================

def generate_signed_url(redirect_api_url: str, bucket: str, key: str, secret_key: str, validity_hours: int = 168) -> str:
    """Generate a signed URL that expires after validity_hours."""
    # Calculate expiration timestamp
    expires = int(time.time()) + (validity_hours * 3600)
    
    # Create signature
    message = f"{bucket}:{key}:{expires}"
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # URL-encode the key
    encoded_key = quote(key, safe='')
    
    # Build the signed URL
    url = f"{redirect_api_url}/voicemail/{bucket}/{encoded_key}?expires={expires}&signature={signature}"
    
    return url


def verify_signature(bucket: str, key: str, expires: str, signature: str, secret_key: str) -> bool:
    """Verify the URL signature."""
    message = f"{bucket}:{key}:{expires}"
    expected_signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


# =============================================================================
# FUNCTION URL HANDLER (URL GENERATION)
# =============================================================================

def handle_url_generation(event: dict) -> dict:
    """
    Handle Function URL request to generate presigned URL.
    Expected path: /voicemail/{bucket}/{key}?expires={timestamp}&signature={hmac}
    """
    try:
        # Extract path and query parameters from Function URL event
        raw_path = event.get('rawPath', '')
        query_parameters = event.get('queryStringParameters') or {}
        
        # Parse path: /voicemail/{bucket}/{remaining_key_path}
        if not raw_path.startswith('/voicemail/'):
            logger.warning(f"Invalid path: {raw_path}")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>404 Not Found</h1><p>Invalid path</p>'
            }
        
        # Remove '/voicemail/' prefix and split into bucket and key
        path_after_voicemail = raw_path[11:]  # Remove '/voicemail/'
        
        if not path_after_voicemail or '/' not in path_after_voicemail:
            logger.warning("Missing bucket or key in path")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>400 Bad Request</h1><p>Missing bucket or key</p>'
            }
        
        # Split at first '/' to get bucket and key
        bucket, key_encoded = path_after_voicemail.split('/', 1)
        
        # Get query parameters
        expires = query_parameters.get('expires')
        signature = query_parameters.get('signature')
        
        if not expires or not signature:
            logger.warning("Missing expires or signature parameter")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>400 Bad Request</h1><p>Missing required parameters</p>'
            }
        
        # Decode the key (it's URL-encoded)
        key = unquote(key_encoded)
        
        # Check expiration
        try:
            expires_timestamp = int(expires)
            current_timestamp = int(time.time())
            
            if current_timestamp > expires_timestamp:
                expires_date = datetime.fromtimestamp(expires_timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
                logger.warning(f"Link expired: {expires_date}")
                return {
                    'statusCode': 403,
                    'headers': {'Content-Type': 'text/html'},
                    'body': f'<h1>403 Forbidden</h1><p>This link expired on {expires_date}.</p><p>Please contact support for a new link.</p>'
                }
        except ValueError:
            logger.warning("Invalid expiration timestamp")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>400 Bad Request</h1><p>Invalid expiration timestamp</p>'
            }
        
        # Get signing secret
        signing_secret = os.environ.get('SIGNING_SECRET', '')
        if not signing_secret:
            logger.error("SIGNING_SECRET not configured")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>500 Internal Server Error</h1><p>Server configuration error</p>'
            }
        
        # Verify signature
        if not verify_signature(bucket, key, expires, signature, signing_secret):
            logger.warning(f"Invalid signature for {bucket}/{key}")
            return {
                'statusCode': 403,
                'headers': {'Content-Type': 'text/html'},
                'body': '<h1>403 Forbidden</h1><p>Invalid signature. This link may have been tampered with.</p>'
            }
        
        # Generate presigned URL
        region = os.environ.get('AWS_REGION', 'us-east-1')
        boto_config = Config(region_name=region, signature_version='s3v4')
        s3_client = boto3.client('s3', config=boto_config)
        
        # Verify the object exists before generating URL
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == '404':
                logger.error(f"Recording not found: s3://{bucket}/{key}")
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'text/html'},
                    'body': '<h1>404 Not Found</h1><p>Recording not found. It may have been deleted.</p>'
                }
            raise
        
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentType': 'audio/wav',
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=3600  # 1 hour to listen
        )
        
        logger.info(f"[URL GENERATED] s3://{bucket}/{key}")
        
        # Redirect to the presigned URL
        return {
            'statusCode': 302,
            'headers': {
                'Location': presigned_url,
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating URL: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html'},
            'body': '<h1>500 Internal Server Error</h1><p>Failed to generate URL</p>'
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def parse_s3_uri(uri: str) -> Tuple[str, str]:
    """Parse S3 URI into bucket and key."""
    rest = uri[5:]
    bucket, key = rest.split("/", 1)
    return bucket, key


def fetch_json(uri: str, region: str) -> dict:
    """Fetch and parse JSON from S3 URI or HTTP URL."""
    if uri.startswith("s3://"):
        bucket, key = parse_s3_uri(uri)
        s3_client = boto3.client("s3", region_name=region)
        body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
    else:
        body = urllib.request.urlopen(uri).read()
    return json.loads(body)


def extract_region_from_arn(arn: str) -> Optional[str]:
    """Extract AWS region from ARN."""
    try:
        return arn.split(":")[3]
    except Exception:
        return None


def resolve_region(instance_arn: str) -> str:
    """Resolve AWS region from instance ARN or session."""
    region = extract_region_from_arn(instance_arn)
    if region:
        return region
    
    try:
        region = boto3.client("sts").meta.region_name
    except Exception:
        region = None
    
    if not region:
        region = boto3.session.Session().region_name
    
    if not region:
        raise RuntimeError("Unable to determine AWS region")
    
    return region


def validate_environment() -> Tuple[str, int, str, int]:
    """Validate and retrieve environment variables."""
    base_path = os.environ.get("BASE_PATH", "").strip("/")
    if not base_path:
        raise ValueError("BASE_PATH environment variable is required")
    
    email_sender = os.environ.get("EMAIL_SENDER", "")
    if not email_sender:
        raise ValueError("EMAIL_SENDER environment variable is required")
    
    url_expiration = int(os.environ.get("URL_EXPIRATION", "604800"))
    recording_wait_time = int(os.environ.get("RECORDING_WAIT_TIME", "70"))
    
    return base_path, url_expiration, email_sender, recording_wait_time


# =============================================================================
# TRANSCRIPTION PROCESSING
# =============================================================================

def build_transcription_preview(results: dict, mode: str, limit: int) -> str:
    """Build transcription preview from AWS Transcribe results."""
    if mode == "channel" and results.get("channel_labels"):
        return _build_preview_channel(results, limit)
    elif mode == "diarization" and results.get("speaker_labels"):
        return _build_preview_diarization(results, limit)
    else:
        transcript = results.get("transcripts", [{}])[0].get("transcript", "")
        return transcript[:limit].strip()


def _build_preview_channel(results: dict, limit: int) -> str:
    """Build preview from channel-separated results."""
    channels = results.get("channel_labels", {}).get("channels", [])
    all_words = []
    
    for channel in channels:
        words = []
        for item in channel.get("items", []):
            item_type = item.get("type")
            content = item["alternatives"][0].get("content", "")
            
            if item_type == "pronunciation":
                words.append(content)
            elif item_type == "punctuation" and words:
                words[-1] += content
            elif item_type == "punctuation":
                words.append(content)
        
        text = " ".join(words).replace(" ,", ",").replace(" .", ".").strip()
        if text:
            all_words.append(text)
    
    return " ".join(all_words).strip()[:limit]


def _build_preview_diarization(results: dict, limit: int) -> str:
    """Build preview from speaker-diarized results."""
    speaker_map = {}
    for segment in results.get("speaker_labels", {}).get("segments", []):
        speaker = segment.get("speaker_label", "spk_?")
        for item in segment.get("items", []):
            start_time = item.get("start_time")
            if start_time:
                speaker_map[start_time] = speaker
    
    per_speaker = {}
    current_speaker = None
    
    for item in results.get("items", []):
        item_type = item.get("type")
        
        if item_type == "pronunciation":
            start_time = item.get("start_time")
            current_speaker = speaker_map.get(start_time, current_speaker)
            content = item["alternatives"][0].get("content", "")
            per_speaker.setdefault(current_speaker or "spk_?", []).append(content)
        elif item_type == "punctuation" and current_speaker in per_speaker:
            if per_speaker[current_speaker]:
                content = item["alternatives"][0].get("content", "")
                per_speaker[current_speaker][-1] += content
    
    all_text = []
    for speaker, words in per_speaker.items():
        text = " ".join(words).replace(" ,", ",").replace(" .", ".").strip()
        if text:
            all_text.append(text)
    
    return " ".join(all_text).strip()[:limit]


def get_actual_recording_duration(results: dict) -> float:
    """Calculate actual recording duration excluding trailing silence."""
    try:
        items = results.get("items", [])
        if not items:
            return 0.0
        
        for item in reversed(items):
            if item.get("end_time"):
                return float(item.get("end_time"))
        
        return 0.0
    except Exception as e:
        logger.warning(f"Could not calculate duration: {e}")
        return 0.0


def start_transcription_job(media_s3_uri: str, region: str, mode: str, language: str) -> str:
    """Start AWS Transcribe job for audio file."""
    transcribe_client = boto3.client("transcribe", region_name=region)
    job_name = f"voicemail-transcribe-{int(time.time())}"
    
    request = {
        "TranscriptionJobName": job_name,
        "Media": {"MediaFileUri": media_s3_uri},
        "LanguageCode": language
    }
    
    extension = media_s3_uri.rsplit(".", 1)[-1].lower()
    supported_formats = {"mp3", "mp4", "wav", "flac", "ogg", "amr", "webm", "opus"}
    if extension in supported_formats:
        request["MediaFormat"] = extension
    
    settings = {}
    if mode == "channel":
        settings["ChannelIdentification"] = True
    else:
        settings["ShowSpeakerLabels"] = True
        settings["MaxSpeakerLabels"] = 2
    request["Settings"] = settings
    
    try:
        transcribe_client.start_transcription_job(**request)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConflictException":
            job_name = f"{job_name}-{int(time.time())}"
            request["TranscriptionJobName"] = job_name
            transcribe_client.start_transcription_job(**request)
        else:
            raise TranscriptionError(f"Failed to start transcription: {e}")
    
    return job_name


def wait_for_transcription(job_name: str, region: str) -> dict:
    """Wait for transcription job to complete."""
    transcribe_client = boto3.client("transcribe", region_name=region)
    waited = 0
    
    while True:
        job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]
        
        if status in ("COMPLETED", "FAILED"):
            return job
        
        time.sleep(TRANSCRIBE_POLL_SECS)
        waited += TRANSCRIBE_POLL_SECS
        
        if waited >= TRANSCRIBE_MAX_WAIT_SECS:
            raise TimeoutError(f"Transcription job '{job_name}' timed out")


# =============================================================================
# S3 RECORDING SEARCH
# =============================================================================

def generate_s3_uris_with_time_window(
    bucket: str, prefix: str, initial_contact_id: str, now: datetime, minutes_offset: int
) -> List[Dict[str, str]]:
    """Generate S3 URIs for potential recording locations within time window."""
    fmt_day = "%Y/%m/%d"
    fmt_time = "%Y%m%dT%H:%M"
    s3_uris = []
    
    for offset in range(-minutes_offset, minutes_offset + 1):
        dt = now + timedelta(minutes=offset)
        date_path = dt.strftime(fmt_day)
        timestamp = dt.strftime(fmt_time)
        filename = f"{initial_contact_id}_{timestamp}_UTC.wav"
        
        key = f"{prefix}/ivr/{date_path}/{filename}" if prefix else f"ivr/{date_path}/{filename}"
        uri = f"s3://{bucket}/{key}"
        
        s3_uris.append({
            "key": key,
            "uri": uri,
            "timestamp": timestamp,
            "offset_minutes": offset
        })
    
    return s3_uris


def find_recording_in_s3(
    s3_client, bucket: str, prefix: str, initial_contact_id: str
) -> Optional[Dict[str, str]]:
    """Search for recording file in S3 with decreasing time windows."""
    now = datetime.utcnow()
    
    for window_minutes in range(MAX_TIME_WINDOW_MINUTES, 0, -1):
        logger.info(f"Searching with time window: ±{window_minutes} minutes")
        
        s3_uris = generate_s3_uris_with_time_window(bucket, prefix, initial_contact_id, now, window_minutes)
        s3_uris.sort(key=lambda x: abs(x['offset_minutes']))
        
        for location in s3_uris:
            try:
                s3_client.head_object(Bucket=bucket, Key=location["key"])
                logger.info(f"[SUCCESS] Found at {location['uri']} (offset: {location['offset_minutes']}m)")
                return location
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") != "404":
                    logger.error(f"Error checking S3 object: {e}")
                    raise
        
        if window_minutes > 1:
            logger.info(f"Not found in ±{window_minutes}m window, trying ±{window_minutes - 1}m...")
            time.sleep(0.5)
    
    return None


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def create_html_email(
    caller_number: str, preview: str, redirect_url: str, 
    recipient_name: str, recording_duration: float = 0.0
) -> str:
    """Create HTML email body with voicemail details."""
    duration_text = ""
    if recording_duration > 0:
        minutes = int(recording_duration // 60)
        seconds = int(recording_duration % 60)
        duration_text = f"<p style='color: #666; font-size: 14px; margin: 10px 0 0 0; text-align: left;'>Duration: {minutes}m {seconds}s</p>" if minutes > 0 else f"<p style='color: #666; font-size: 14px; margin: 10px 0 0 0; text-align: left;'>Duration: {seconds}s</p>"
    
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: transparent; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: transparent; text-align: left; }}
            .header {{ background-color: transparent; padding: 0; margin-bottom: 30px; text-align: left; }}
            .header h2 {{ font-size: 28px; margin: 0 0 15px 0; color: #333; font-weight: bold; text-align: left; }}
            .header p {{ font-size: 18px; margin: 0 0 30px 0; color: #333; text-align: left; }}
            .preview {{ background-color: transparent; padding: 0 0 0 15px; border-left: 4px solid #0066cc; margin: 20px 0; white-space: pre-wrap; font-family: Arial, sans-serif; font-size: 16px; line-height: 1.6; text-align: left; }}
            h3 {{ font-size: 20px; margin: 30px 0 20px 0; color: #333; text-align: left; }}
            a {{ color: #0066cc; text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Voicemail for: {recipient_name}</h2>
                <p>There is a voicemail from <strong>{caller_number}</strong>.</p>
            </div>
            <p><a href="{redirect_url}">Listen to the voicemail.</a></p>
            {duration_text}
            <h3>Voicemail transcription</h3>
            <div class="preview">{preview}</div>
        </div>
    </body>
    </html>
    """


def create_text_email(
    caller_number: str, preview: str, redirect_url: str,
    recipient_name: str, recording_duration: float = 0.0
) -> str:
    """Create plain text email body as fallback."""
    duration_text = ""
    if recording_duration > 0:
        minutes = int(recording_duration // 60)
        seconds = int(recording_duration % 60)
        duration_text = f"\nDuration: {minutes}m {seconds}s" if minutes > 0 else f"\nDuration: {seconds}s"
    
    return f"""Voicemail for: {recipient_name}

There is a voicemail from {caller_number}{duration_text}

Voicemail transcription:
{preview}

Listen to the full recording here:
{redirect_url}
""".strip()


def send_email_with_recording(
    ses_client, email_sender: str, email_recipient: str, caller_number: str,
    preview: str, redirect_url: str, recipient_name: str, recording_duration: float = 0.0
) -> dict:
    """Send email notification with voicemail details."""
    subject = f"Voicemail message from: {caller_number}"
    html_body = create_html_email(caller_number, preview, redirect_url, recipient_name, recording_duration)
    text_body = create_text_email(caller_number, preview, redirect_url, recipient_name, recording_duration)
    
    return ses_client.send_email(
        FromEmailAddress=email_sender,
        Destination={"ToAddresses": [email_recipient]},
        Content={
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"}
                }
            }
        }
    )


# =============================================================================
# VOICEMAIL PROCESSING HANDLER
# =============================================================================

def handle_voicemail_processing(event: dict, context) -> dict:
    """Handle Amazon Connect voicemail processing."""
    logger.info("=" * 80)
    logger.info("VOICEMAIL PROCESSING STARTED")
    logger.info("=" * 80)
    
    try:
        # Validate environment and extract contact data
        base_path, url_expiration, email_sender, recording_wait_time = validate_environment()
        
        contact_data = event["Details"]["ContactData"]
        initial_contact_id = contact_data["InitialContactId"]
        contact_id = contact_data["ContactId"]
        instance_arn = contact_data["InstanceARN"]
        attributes = contact_data.get("Attributes", {})
        
        caller_number = contact_data.get("CustomerEndpoint", {}).get("Address", "Unknown")
        email_recipient = attributes.get("emailRecipient")
        recipient_name = attributes.get("RecipientName", email_recipient)
        
        # Log configuration
        logger.info(f"Contact ID: {initial_contact_id}")
        logger.info(f"Caller: {caller_number}")
        logger.info(f"Email: {email_sender} -> {email_recipient or 'MISSING'}")
        logger.info(f"Recipient: {recipient_name}")
        logger.info(f"Wait time: {recording_wait_time}s")
        
        if not email_recipient:
            logger.error("Missing emailRecipient attribute")
            return {"statusCode": 400, "message": "Missing emailRecipient attribute"}
        
    except KeyError as e:
        logger.error(f"Missing contact data: {e}")
        return {"statusCode": 400, "message": f"Missing contact data: {str(e)}"}
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return {"statusCode": 500, "message": str(e)}
    
    # Initialize AWS clients
    try:
        region = resolve_region(instance_arn)
        boto_config = Config(region_name=region, signature_version="s3v4")
        
        s3_client = boto3.client("s3", config=boto_config)
        ses_client = boto3.client("sesv2", config=boto_config)
        
        logger.info(f"AWS clients initialized in {region}")
    except Exception as e:
        logger.error(f"Failed to initialize AWS clients: {e}")
        return {"statusCode": 500, "message": "Failed to initialize AWS clients"}
    
    # Parse S3 path
    parts = base_path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    
    # Wait for recording to complete and upload
    logger.info(f"Waiting {recording_wait_time}s for recording to complete...")
    time.sleep(recording_wait_time)
    
    # Find recording with retry
    try:
        location = None
        for attempt in range(1, 3):
            logger.info(f"Search attempt {attempt}/2")
            start_time = time.time()
            
            location = find_recording_in_s3(s3_client, bucket, prefix, initial_contact_id)
            
            if location:
                logger.info(f"Recording found in {time.time() - start_time:.1f}s")
                break
            
            if attempt < 2:
                logger.warning(f"Not found after {time.time() - start_time:.1f}s, waiting 30s...")
                time.sleep(30)
        
        if not location:
            logger.error("Recording not found after all attempts")
            return {"statusCode": 404, "message": "Recording not found"}
        
        key = location["key"]
        uri = location["uri"]
        timestamp = location["timestamp"]
        
    except Exception as e:
        logger.error(f"Error searching for recording: {e}")
        return {"statusCode": 500, "message": "Error searching for recording"}
    
    # Transcribe recording
    try:
        media_s3_uri = f"s3://{bucket}/{key}"
        logger.info(f"[TRANSCRIBE START] {media_s3_uri}")
        
        start_time = time.time()
        job_name = start_transcription_job(media_s3_uri, region, DEFAULT_MODE, DEFAULT_LANGUAGE)
        
        job = wait_for_transcription(job_name, region)
        status = job["TranscriptionJobStatus"]
        elapsed = int(time.time() - start_time)
        
        logger.info(f"[TRANSCRIBE END] {job_name}: {status} ({elapsed}s)")
        
        if status != "COMPLETED":
            raise TranscriptionError(f"Transcription failed: {status}")
        
        # Parse results
        data = fetch_json(job["Transcript"]["TranscriptFileUri"], region)
        results = data.get("results", {})
        
        preview = build_transcription_preview(results, DEFAULT_MODE, DEFAULT_PREVIEW_LEN)
        duration = get_actual_recording_duration(results)
        
        if not preview:
            logger.warning("Empty transcription")
            preview = "No transcription available"
        
        logger.info(f"Actual duration (excluding silence): {duration:.1f}s")
        
    except TranscriptionError as e:
        logger.error(f"Transcription error: {e}")
        return {"statusCode": 502, "message": str(e)}
    except Exception as e:
        logger.error(f"Transcription processing error: {e}")
        return {"statusCode": 500, "message": "Transcription processing error"}
    
    # Generate signed redirect URL
    try:
        redirect_api_url = os.environ.get("REDIRECT_API_URL", "").rstrip("/")
        signing_secret = os.environ.get("SIGNING_SECRET", "")
        
        if not redirect_api_url:
            raise ValueError("REDIRECT_API_URL environment variable not set")
        if not signing_secret:
            raise ValueError("SIGNING_SECRET environment variable not set")
        
        # Calculate validity in hours from URL_EXPIRATION (in seconds)
        validity_hours = url_expiration // 3600
        
        # Generate signed URL
        redirect_url = generate_signed_url(
            redirect_api_url,
            bucket,
            key,
            signing_secret,
            validity_hours
        )
        
        logger.info(f"[SIGNED URL] Created (valid for {validity_hours} hours)")
        
    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return {"statusCode": 500, "message": "Error generating signed URL"}
    
    # Send email
    try:
        logger.info("Sending email...")
        response = send_email_with_recording(
            ses_client, email_sender, email_recipient, caller_number,
            preview, redirect_url, recipient_name, duration
        )
        
        message_id = response.get("MessageId")
        logger.info(f"[EMAIL SENT] {message_id}")
        
        return {
            "statusCode": 200,
            "message": "Voicemail processed successfully",
            "data": {
                "timestamp": timestamp,
                "s3_uri": uri,
                "duration": duration,
                "message_id": message_id
            }
        }
        
    except ClientError as e:
        logger.error(f"Email send failed: {e}")
        return {"statusCode": 500, "message": "Email send failed"}
    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"statusCode": 500, "message": "Email error"}


# =============================================================================
# MAIN HANDLER (ROUTER)
# =============================================================================

def lambda_handler(event: dict, context) -> dict:
    """
    Main Lambda handler that routes between:
    1. Function URL requests (URL generation/validation)
    2. Amazon Connect events (voicemail processing)
    """
    
    # Log the incoming event for debugging
    logger.info(f"Event type check - Keys: {list(event.keys())}")
    
    # Check if this is a Function URL request (HTTP request)
    if 'requestContext' in event and 'http' in event.get('requestContext', {}):
        logger.info("Handling Function URL request (URL generation)")
        return handle_url_generation(event)
    
    # Check if this is an Amazon Connect event
    elif 'Details' in event and 'ContactData' in event.get('Details', {}):
        logger.info("Handling Amazon Connect event (voicemail processing)")
        return handle_voicemail_processing(event, context)
    
    # Unknown event type
    else:
        logger.error(f"Unknown event type. Event keys: {list(event.keys())}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unknown event type'})
        }
