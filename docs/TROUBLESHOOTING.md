# Troubleshooting Guide

Solutions to common issues with the Amazon Connect Voicemail System.

## Table of Contents

- [Recording Issues](#recording-issues)
- [Email Issues](#email-issues)
- [Lambda Issues](#lambda-issues)
- [Transcription Issues](#transcription-issues)
- [Connect Flow Issues](#connect-flow-issues)
- [Debugging Tips](#debugging-tips)

---

## Recording Issues

### Recording Not Found

**Symptom**: Lambda logs show "Recording file not found in S3"

**Possible Causes**:

1. **Wait time too short**
   ```
   Solution: Increase RECORDING_WAIT_TIME
   ```
   ```bash
   # Current: 70 seconds
   # Try: 90-100 seconds
   aws lambda update-function-configuration \
     --function-name voicemail-transcribe-email \
     --environment Variables="{...,RECORDING_WAIT_TIME=90}"
   ```

2. **BASE_PATH mismatch**
   ```
   Solution: Verify S3 path matches Connect configuration
   ```
   - Check Connect: Console → Data storage → Call recordings
   - Check Lambda: Environment variables → BASE_PATH
   - Must match exactly: `bucket/prefix`

3. **Recording not uploaded**
   ```
   Solution: Check S3 bucket manually
   ```
   ```bash
   aws s3 ls s3://your-bucket/connect/recordings/ivr/ --recursive
   ```

**CloudWatch Logs to Check**:
```
Searching for recording with time window: ±5 minutes
[NOT FOUND] s3://bucket/...
Recording not found after all attempts
```

**Fix**:
1. Check actual file location in S3
2. Update BASE_PATH to match
3. Increase RECORDING_WAIT_TIME if needed

### No Recording Created

**Symptom**: No file appears in S3 at all

**Possible Causes**:

1. **Recording not enabled in flow**
   ```
   Solution: Verify UpdateContactRecordingBehavior block
   ```
   - Check block "8b4a69ed-1915-4c3f-9c6f-ba8cfda3fc80"
   - Ensure: `IVRRecordingBehavior: Enabled`

2. **S3 bucket not configured**
   ```
   Solution: Configure recording destination
   ```
   - Go to Connect Console → Data storage
   - Set Call recordings bucket and prefix
   - Save changes

3. **IAM permissions missing**
   ```
   Solution: Grant Connect access to S3
   ```
   - Check bucket policy allows Connect service
   - See AWS documentation for required permissions

---

## Email Issues

### Email Not Received

**Symptom**: No email arrives after voicemail

**Possible Causes**:

1. **SES not verified**
   ```
   Solution: Verify sender email
   ```
   ```bash
   aws ses verify-email-identity \
     --email-address noreply@example.com \
     --region us-west-2
   ```
   Check inbox for verification email

2. **SES in sandbox mode**
   ```
   Solution: Verify recipient OR request production access
   ```
   - Sandbox: Can only send to verified emails
   - Verify recipient:
   ```bash
   aws ses verify-email-identity \
     --email-address recipient@example.com
   ```
   - OR request production access in SES Console

3. **EMAIL_SENDER not set**
   ```
   Solution: Set environment variable
   ```
   ```bash
   aws lambda update-function-configuration \
     --function-name voicemail-transcribe-email \
     --environment Variables="{...,EMAIL_SENDER=noreply@example.com}"
   ```

4. **emailRecipient attribute missing**
   ```
   Solution: Set attribute in Connect flow
   ```
   - Update "NEEDED ATTRIBUTES" block
   - Or pass from routing logic

**CloudWatch Logs to Check**:
```
Email recipient: MISSING  ← Problem!
[EMAIL SENT] MessageId: xxx  ← Success
Failed to send email: ...  ← Error details
```

**Fix**:
1. Check CloudWatch logs for specific error
2. Verify SES configuration
3. Confirm contact attributes are set

### Email in Spam

**Symptom**: Email goes to spam folder

**Solutions**:

1. **Set up SPF record**
   ```
   Add to DNS:
   TXT record: "v=spf1 include:amazonses.com ~all"
   ```

2. **Set up DKIM**
   ```
   - Go to SES Console → Verified identities
   - Enable DKIM
   - Add DNS records provided
   ```

3. **Use verified domain**
   ```
   Instead of: noreply@example.com
   Use verified domain: noreply@yourdomain.com
   ```

### Email Formatting Issues

**Symptom**: Email doesn't look right

**Possible Causes**:

1. **Email client doesn't support HTML**
   ```
   Solution: Improve plain text fallback
   ```
   - Edit `create_text_email()` function

2. **Missing CSS inline styles**
   ```
   Solution: Use inline styles (already done)
   ```
   - All styles are inline in HTML

---

## Lambda Issues

### Lambda Timeout

**Symptom**: "Task timed out after X seconds"

**Possible Causes**:

1. **Timeout too short**
   ```
   Solution: Increase to 180 seconds
   ```
   ```bash
   aws lambda update-function-configuration \
     --function-name voicemail-transcribe-email \
     --timeout 180
   ```

2. **Transcription taking too long**
   ```
   Solution: Check audio file size
   ```
   - Large files (>10MB) take longer
   - Consider shorter recording limits

3. **Network issues**
   ```
   Solution: Check VPC configuration
   ```
   - If in VPC, ensure NAT Gateway exists
   - Check security group allows outbound HTTPS

**CloudWatch Logs to Check**:
```
[TRANSCRIBE START] Starting transcription...
Task timed out after 60.00 seconds  ← Problem!
```

**Fix**:
1. Increase Lambda timeout to 180s
2. Verify network connectivity
3. Check transcription service status

### Lambda Not Invoked

**Symptom**: No Lambda logs appear in CloudWatch

**Possible Causes**:

1. **Lambda not added to Connect**
   ```
   Solution: Add Lambda to Connect instance
   ```
   - Go to Connect Console
   - Contact flows → AWS Lambda
   - Add function ARN

2. **Wrong Lambda ARN in flow**
   ```
   Solution: Update flow
   ```
   - Open flow in Connect
   - Click "Email-copy-1" block
   - Update Lambda function
   - Publish flow

3. **Invoke permission missing**
   ```
   Solution: Grant Connect permission
   ```
   ```bash
   aws lambda add-permission \
     --function-name voicemail-transcribe-email \
     --statement-id AllowConnectInvoke \
     --action lambda:InvokeFunction \
     --principal connect.amazonaws.com \
     --source-arn arn:aws:connect:region:account:instance/instance-id
   ```

**CloudWatch Logs to Check**:
```
# Should see:
VOICEMAIL PROCESSING STARTED
```

**Fix**:
1. Verify Lambda permissions
2. Check flow configuration
3. Test Lambda manually

### Memory Issues

**Symptom**: "Runtime exited with error: signal: killed"

**Solution**: Increase memory

```bash
aws lambda update-function-configuration \
  --function-name voicemail-transcribe-email \
  --memory-size 512  # or 1024
```

---

## Transcription Issues

### Empty Transcription

**Symptom**: "No transcription available"

**Possible Causes**:

1. **No speech in recording**
   ```
   Solution: Verify recording has actual speech
   ```
   - Download recording from S3
   - Listen to confirm audio

2. **Audio quality too low**
   ```
   Solution: Check audio format
   ```
   - Minimum: 8kHz sample rate
   - Connect default: 8kHz mono WAV
   - Should work fine

3. **Wrong language set**
   ```
   Solution: Update language code
   ```
   ```python
   # In lambda_function.py
   DEFAULT_LANGUAGE = "en-US"  # Match caller's language
   ```

**CloudWatch Logs to Check**:
```
[TRANSCRIBE END] Job: xxx, Status: COMPLETED
Transcription preview is empty  ← Problem!
```

**Fix**:
1. Test with known good audio
2. Check Transcribe job details in console
3. Verify language setting

### Transcription Failed

**Symptom**: "[TRANSCRIBE END] Status: FAILED"

**Possible Causes**:

1. **Unsupported audio format**
   ```
   Solution: Verify .wav format
   ```
   - Connect uses .wav (supported)
   - Check file extension in S3

2. **IAM permissions missing**
   ```
   Solution: Add Transcribe permissions
   ```
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "transcribe:StartTranscriptionJob",
       "transcribe:GetTranscriptionJob"
     ],
     "Resource": "*"
   }
   ```

3. **Service limit exceeded**
   ```
   Solution: Request limit increase
   ```
   - Default: 100 concurrent jobs
   - Request increase in AWS Support

**CloudWatch Logs to Check**:
```
[TRANSCRIBE END] Job: xxx, Status: FAILED
Transcription error: ...  ← Error details
```

**Fix**:
1. Check Transcribe service status
2. Verify IAM permissions
3. Review Transcribe console for job details

---

## Connect Flow Issues

### Flow Not Working

**Symptom**: Caller doesn't reach voicemail

**Possible Causes**:

1. **Flow not published**
   ```
   Solution: Publish the flow
   ```
   - Open flow in Connect
   - Click "Save" → "Publish"

2. **Flow not attached to number**
   ```
   Solution: Link flow to phone number
   ```
   - Go to Phone numbers
   - Edit number
   - Set Contact flow

3. **Transfer not configured**
   ```
   Solution: Add transfer block in main flow
   ```
   - Use "Transfer to flow" block
   - Select VoiceMailModule

### Recording Not Stopping

**Symptom**: Recording continues after # press

**Possible Causes**:

1. **Disable recording block missing**
   ```
   Solution: Verify flow structure
   ```
   - Check block "8ea28fe0-ae5d-481e-96c3-8e08a5754c9c"
   - Must disable recording after input

2. **GetParticipantInput not configured**
   ```
   Solution: Check DTMF settings
   ```
   - Ensure "#" is configured as stop key

### Caller Can't Hear Prompts

**Symptom**: Silence instead of prompts

**Possible Causes**:

1. **Prompt not uploaded**
   ```
   Solution: Upload beep.wav
   ```
   - Go to Connect → Prompts
   - Upload beep sound file

2. **Prompt ARN incorrect**
   ```
   Solution: Update prompt in flow
   ```
   - Edit block "c8b94ae7-7fe0-490a-92d2-4f4b7868cad4"
   - Select correct prompt

---

## Debugging Tips

### Enable Detailed Logging

**In Lambda**:
```python
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Change from INFO
```

**In Connect**:
- Flow block "6cee06e7-3d99-493a-a5c6-3c16ae13f8ad" enables logging
- Logs appear in CloudWatch: `/aws/connect/your-instance`

### View CloudWatch Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/voicemail-transcribe-email --follow

# Last 1 hour
aws logs tail /aws/lambda/voicemail-transcribe-email --since 1h

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/voicemail-transcribe-email \
  --filter-pattern "ERROR"
```

### Test Lambda Manually

Create `test-event.json`:
```json
{
  "Details": {
    "ContactData": {
      "InitialContactId": "test-contact-123",
      "ContactId": "test-contact-123",
      "InstanceARN": "arn:aws:connect:us-west-2:account:instance/id",
      "CustomerEndpoint": {
        "Address": "+12345678900"
      },
      "Attributes": {
        "emailRecipient": "test@example.com",
        "RecipientName": "Test User"
      }
    }
  }
}
```

Invoke:
```bash
aws lambda invoke \
  --function-name voicemail-transcribe-email \
  --payload file://test-event.json \
  response.json

cat response.json
```

### Check S3 File Exists

```bash
# List recent files
aws s3 ls s3://your-bucket/connect/recordings/ivr/$(date +%Y/%m/%d)/ \
  --recursive --human-readable

# Download and listen
aws s3 cp s3://your-bucket/path/to/file.wav test.wav
# Open in audio player
```

### Verify All Configurations

```bash
# Lambda config
aws lambda get-function-configuration \
  --function-name voicemail-transcribe-email

# SES status
aws ses get-send-quota
aws ses list-verified-email-addresses

# S3 bucket
aws s3 ls s3://your-bucket/

# IAM role
aws iam get-role \
  --role-name voicemail-lambda-role
```

### Common Log Messages

**Success**:
```
VOICEMAIL PROCESSING STARTED
Contact ID: abc-123
Waiting 70 seconds for recording...
[SUCCESS] Found file at s3://...
[TRANSCRIBE END] Status: COMPLETED
[EMAIL SENT] MessageId: xxx
```

**Failure**:
```
Missing required attribute: emailRecipient  ← Set contact attribute
Recording not found after all attempts  ← Increase wait time
Email send failed: ...  ← Check SES
Transcription error: ...  ← Check Transcribe
```

## Getting Help

If you're still stuck:

1. **Check CloudWatch logs first**
   - Lambda logs: `/aws/lambda/voicemail-transcribe-email`
   - Connect logs: `/aws/connect/your-instance`

2. **Review configuration**
   - Environment variables
   - S3 path
   - SES setup
   - IAM permissions

3. **Test components individually**
   - Lambda manually
   - S3 access
   - SES sending
   - Transcribe service

4. **Open GitHub issue**
   - Include CloudWatch logs
   - Describe steps to reproduce
   - Share configuration (redact sensitive info)

---

**Still having issues?** [Open an issue](https://github.com/godwillcho/amazon-connect-voicemail/issues) with your CloudWatch logs.
