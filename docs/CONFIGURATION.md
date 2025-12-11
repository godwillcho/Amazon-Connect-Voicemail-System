# Configuration Guide

Complete configuration reference for the Amazon Connect Voicemail System.

## Environment Variables

### Lambda Function Configuration

#### Required Variables

| Variable | Description | Example | Notes |
|----------|-------------|---------|-------|
| `BASE_PATH` | S3 bucket and prefix for recordings | `my-voicemail-bucket/recordings` | Must match Connect recording path |
| `EMAIL_SENDER` | Email address to send from | `noreply@example.com` | Must be verified in SES |

#### Optional Variables

| Variable | Description | Default | Example | Notes |
|----------|-------------|---------|---------|-------|
| `URL_EXPIRATION` | Presigned URL expiration (seconds) | `604800` (7 days) | `259200` (3 days) | Max: 604800 (7 days) |
| `RECORDING_WAIT_TIME` | Wait before searching for recording | `70` | `100` | Adjust based on recording length |

### Setting Environment Variables

#### Via AWS Console

1. Go to Lambda Console
2. Select `voicemail-transcribe-email` function
3. Navigate to **Configuration** → **Environment variables**
4. Click **Edit**
5. Add/modify variables:

```
BASE_PATH: my-voicemail-bucket/connect/recordings
EMAIL_SENDER: noreply@example.com
URL_EXPIRATION: 604800
RECORDING_WAIT_TIME: 70
```

6. Click **Save**

#### Via AWS CLI

```bash
aws lambda update-function-configuration \
  --function-name voicemail-transcribe-email \
  --environment Variables="{
    BASE_PATH=my-voicemail-bucket/connect/recordings,
    EMAIL_SENDER=noreply@example.com,
    URL_EXPIRATION=604800,
    RECORDING_WAIT_TIME=70
  }" \
  --region us-west-2
```

#### Via CloudFormation

```yaml
Environment:
  Variables:
    BASE_PATH: my-voicemail-bucket/connect/recordings
    EMAIL_SENDER: noreply@example.com
    URL_EXPIRATION: 604800
    RECORDING_WAIT_TIME: 70
```

## Amazon Connect Flow Configuration

### Contact Attributes

The flow requires these contact attributes to be set before calling the voicemail module:

| Attribute | Required | Description | Example |
|-----------|----------|-------------|---------|
| `emailRecipient` | ✅ Yes | Email address to receive voicemail | `user@example.com` |
| `RecipientName` | ❌ No | Display name in email | `John Doe` |

### Setting Contact Attributes

#### In Connect Flow (Before Transfer)

```json
{
  "Type": "UpdateContactAttributes",
  "Parameters": {
    "Attributes": {
      "emailRecipient": "$.Attributes.UserEmail",
      "RecipientName": "$.Attributes.UserName"
    }
  }
}
```

#### Dynamic from Lambda

```python
# In your routing Lambda
return {
    'emailRecipient': get_user_email(agent_id),
    'RecipientName': get_user_name(agent_id)
}
```

### Recording Timeout

Adjust recording duration in the flow:

**Current setting**: 5 seconds (for testing)

**For production**: Update `GetParticipantInput` block:

```json
{
  "InputTimeLimitSeconds": "60"  // Change from 5 to 60
}
```

Then update Lambda:
```bash
RECORDING_WAIT_TIME=70  // 60 + 10 buffer
```

### Lambda Function ARN

**Current ARN in flow**: 
```
arn:aws:lambda:us-west-2:551642657889:function:voicemail-transcribe-email
```

**Update for your account**:

1. Open flow in Connect
2. Click "Email-copy-1" block
3. Update Lambda function dropdown
4. Click **Save**
5. Publish flow

## S3 Configuration

### Bucket Structure

Amazon Connect creates this structure:

```
your-bucket/
└── connect/
    └── recordings/
        └── ivr/
            └── YYYY/
                └── MM/
                    └── DD/
                        └── contactId_YYYYMMDDThh:mm_UTC.wav
```

### Required Configuration

#### Recording Path in Connect

1. Go to Amazon Connect Console
2. Select your instance
3. Navigate to **Data storage** → **Call recordings**
4. Set:
   - Bucket: `your-bucket`
   - Prefix: `connect/recordings` (optional)
5. Save

#### Lambda BASE_PATH

Must match Connect configuration:

```bash
# If Connect uses: bucket/prefix
BASE_PATH=your-bucket/connect/recordings

# If Connect uses: bucket only
BASE_PATH=your-bucket
```

### Bucket Permissions

Lambda needs these S3 permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket/connect/recordings/*"
    }
  ]
}
```

### Lifecycle Policy (Optional)

Auto-delete old recordings:

```json
{
  "Rules": [{
    "Id": "DeleteOldVoicemails",
    "Status": "Enabled",
    "Prefix": "connect/recordings/",
    "Expiration": {
      "Days": 90
    }
  }]
}
```

## SES Configuration

### Email Verification

#### Verify Sender Email

```bash
aws ses verify-email-identity \
  --email-address noreply@example.com \
  --region us-west-2
```

Check inbox and click verification link.

#### Verify Domain (Recommended for Production)

```bash
aws ses verify-domain-identity \
  --domain example.com \
  --region us-west-2
```

Add DNS records provided by AWS.

### Sandbox Mode

**Default**: SES is in sandbox mode (can only send to verified emails)

**For Production**: Request production access

1. Go to SES Console
2. Click **Account Dashboard**
3. Click **Request production access**
4. Fill form:
   - Use case: Transactional emails
   - Website: Your company website
   - Description: "Voicemail notification system for Amazon Connect"
5. Submit

Approval typically takes 24 hours.

### Email Limits

| Environment | Limit |
|-------------|-------|
| Sandbox | 200 emails/day, 1 email/second |
| Production | 50,000 emails/day (can be increased) |

## Transcription Configuration

### Language

Default language is US English (`en-US`).

To change language, modify Lambda code:

```python
# In lambda_function.py
DEFAULT_LANGUAGE = "es-US"  # Spanish
```

Supported languages:
- `en-US` - English (US)
- `en-GB` - English (UK)
- `en-AU` - English (Australian)
- `es-US` - Spanish (US)
- `es-ES` - Spanish (Spain)
- `fr-FR` - French
- `fr-CA` - French (Canadian)
- `de-DE` - German
- `it-IT` - Italian
- `pt-BR` - Portuguese (Brazilian)
- `ja-JP` - Japanese
- `ko-KR` - Korean
- `zh-CN` - Chinese (Simplified)
- And many more...

### Transcription Mode

Current mode: **Channel identification**

Alternative modes:

```python
# Speaker diarization (identifies speakers as Speaker 1, Speaker 2)
DEFAULT_MODE = "diarization"

# Simple transcript (no speaker identification)
DEFAULT_MODE = "simple"
```

## Advanced Configuration

### Custom Email Template

Modify email design in `lambda_function.py`:

```python
def create_html_email(...):
    # Change colors
    background-color: #0066cc;  # Blue
    background-color: #ff6600;  # Orange
    
    # Change font
    font-family: 'Helvetica', Arial, sans-serif;
    
    # Change button text
    Listen to the voicemail → Play Recording
```

### Recording Wait Time Calculation

Formula:
```
RECORDING_WAIT_TIME = Max Recording Duration + Upload Buffer
```

Examples:
- 30s recording → `RECORDING_WAIT_TIME=40`
- 60s recording → `RECORDING_WAIT_TIME=70`
- 90s recording → `RECORDING_WAIT_TIME=100`
- 120s recording → `RECORDING_WAIT_TIME=130`

### Presigned URL Expiration

Security recommendations:

| Sensitivity | Recommended Expiration |
|-------------|----------------------|
| Low | 7 days (604800) |
| Medium | 3 days (259200) |
| High | 1 day (86400) |
| Very High | 1 hour (3600) |

### CloudWatch Logs

Configure log retention:

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/voicemail-transcribe-email \
  --retention-in-days 30 \
  --region us-west-2
```

Options: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653 days

## Monitoring Configuration

### CloudWatch Alarms

#### Lambda Errors

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name voicemail-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=voicemail-transcribe-email \
  --alarm-actions arn:aws:sns:us-west-2:ACCOUNT:alert-topic
```

#### Lambda Duration

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name voicemail-lambda-duration \
  --alarm-description "Alert on slow Lambda execution" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 150000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=voicemail-transcribe-email
```

### X-Ray Tracing

Enable AWS X-Ray for detailed tracing:

```bash
aws lambda update-function-configuration \
  --function-name voicemail-transcribe-email \
  --tracing-config Mode=Active
```

## Security Configuration

### Encryption at Rest

#### S3 Bucket Encryption

```bash
aws s3api put-bucket-encryption \
  --bucket your-voicemail-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

Or use KMS:

```bash
aws s3api put-bucket-encryption \
  --bucket your-voicemail-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "arn:aws:kms:us-west-2:ACCOUNT:key/KEY-ID"
      }
    }]
  }'
```

### VPC Configuration (Optional)

For enhanced security, run Lambda in VPC:

```bash
aws lambda update-function-configuration \
  --function-name voicemail-transcribe-email \
  --vpc-config SubnetIds=subnet-xxx,subnet-yyy,SecurityGroupIds=sg-xxx
```

**Note**: Requires NAT Gateway for internet access.

## Configuration Validation

### Test Configuration

```bash
# Test Lambda invocation
aws lambda invoke \
  --function-name voicemail-transcribe-email \
  --payload file://test-event.json \
  --region us-west-2 \
  response.json

# View response
cat response.json
```

### Verify Environment Variables

```bash
aws lambda get-function-configuration \
  --function-name voicemail-transcribe-email \
  --region us-west-2 \
  --query 'Environment.Variables'
```

### Check S3 Access

```bash
aws s3 ls s3://your-bucket/connect/recordings/ivr/
```

### Verify SES

```bash
aws ses get-send-quota --region us-west-2
aws ses list-verified-email-addresses --region us-west-2
```

## Troubleshooting Configuration Issues

### BASE_PATH Mismatch

**Symptom**: "Recording not found"

**Check**:
1. Connect recording path: Console → Data storage
2. Lambda BASE_PATH: Must match exactly
3. Test: Check S3 bucket for actual file location

### SES Not Sending

**Symptom**: "Email send failed"

**Check**:
1. Sender verification: `aws ses list-verified-email-addresses`
2. Sandbox mode: Check Account Dashboard
3. Limits: `aws ses get-send-quota`

### Lambda Timeout

**Symptom**: Lambda times out

**Fix**:
1. Increase timeout: Configuration → General → Timeout → 180 seconds
2. Check RECORDING_WAIT_TIME is appropriate
3. Verify network connectivity to AWS services

## Configuration Checklist

- [ ] Lambda environment variables set
- [ ] S3 bucket configured in Connect
- [ ] BASE_PATH matches Connect configuration
- [ ] SES sender email verified
- [ ] Contact attributes set in flow
- [ ] Lambda ARN updated in Connect flow
- [ ] Recording timeout adjusted for production
- [ ] IAM permissions configured
- [ ] CloudWatch alarms created
- [ ] Bucket encryption enabled
- [ ] Lifecycle policy configured (optional)
- [ ] Tested all scenarios

---

**Need help?** See [INSTALLATION.md](INSTALLATION.md) or [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
