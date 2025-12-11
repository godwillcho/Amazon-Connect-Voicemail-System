# Installation Guide

Complete step-by-step guide to deploy the Amazon Connect Voicemail System.

## Prerequisites

Before you begin, ensure you have:

- [ ] AWS Account with appropriate permissions
- [ ] Amazon Connect instance set up
- [ ] AWS CLI installed and configured
- [ ] S3 bucket for storing recordings
- [ ] SES configured (sender email verified)
- [ ] Basic familiarity with AWS services

## Step 1: Prepare AWS Services

### 1.1 Create S3 Bucket

```bash
aws s3 mb s3://your-voicemail-recordings --region us-west-2
```

### 1.2 Configure Amazon Connect Recording

1. Go to Amazon Connect Console
2. Select your instance
3. Navigate to **Data storage** → **Call recordings**
4. Set S3 bucket: `your-voicemail-recordings`
5. Set path prefix: `recordings` (optional)
6. Save

### 1.3 Verify SES Email

```bash
aws ses verify-email-identity --email-address noreply@yourdomain.com --region us-west-2
```

Check your inbox and click verification link.

### 1.4 Create IAM Role for Lambda

Create role with this trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach these policies:
- `AWSLambdaBasicExecutionRole` (AWS managed)
- Custom policy (see README for details)

## Step 2: Deploy Lambda Function

### 2.1 Clone Repository

```bash
git clone https://github.com/godwillcho/amazon-connect-voicemail.git
cd amazon-connect-voicemail
```

### 2.2 Create Lambda Function

```bash
cd lambda
zip function.zip lambda_function.py

aws lambda create-function \
  --function-name voicemail-transcribe-email \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/voicemail-lambda-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --timeout 180 \
  --memory-size 512 \
  --region us-west-2 \
  --environment Variables="{
    BASE_PATH=your-voicemail-recordings/recordings,
    EMAIL_SENDER=noreply@yourdomain.com,
    URL_EXPIRATION=604800,
    RECORDING_WAIT_TIME=70
  }"
```

**OR use the deployment script:**

```bash
./deploy.sh voicemail-transcribe-email us-west-2
```

### 2.3 Verify Deployment

```bash
aws lambda get-function --function-name voicemail-transcribe-email --region us-west-2
```

## Step 3: Configure Amazon Connect

### 3.1 Add Lambda to Amazon Connect

1. Go to Amazon Connect Console
2. Select your instance
3. Navigate to **Contact flows** → **AWS Lambda**
4. Add your Lambda function ARN
5. Click **Add Lambda Function**

### 3.2 Import Voicemail Flow

1. In Amazon Connect, go to **Routing** → **Contact flows**
2. Click **Create contact flow** → **Import flow (beta)**
3. Select `connect-flow/VoiceMailModule.json`
4. Click **Import**

### 3.3 Update Flow Configuration

In the imported flow:

1. **Update Lambda ARN**:
   - Click the "Email-copy-1" block
   - Select your Lambda function from dropdown
   - Click **Save**

2. **Update Contact Attributes** (NEEDED ATTRIBUTES block):
   - Change `emailRecipient` to your test email
   - Change `RecipientName` to your name
   - Click **Save**

3. **Publish Flow**:
   - Click **Save** → **Publish**

### 3.4 Create Test Flow (Optional)

Create a simple flow for testing:

```
1. Play prompt → "Welcome to voicemail test"
2. Set contact attributes:
   - emailRecipient: your-email@example.com
   - RecipientName: Your Name
3. Transfer to flow → VoiceMailModule
```

## Step 4: Test the System

### 4.1 Call Your Test Number

1. Dial your Amazon Connect test phone number
2. When prompted, leave a voicemail
3. Press # or wait for timeout
4. Hang up

### 4.2 Check Email

Within 2-3 minutes, you should receive:
- Email with voicemail transcription
- Duration information
- Link to listen to recording

### 4.3 Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/voicemail-transcribe-email --follow --region us-west-2
```

Look for:
```
VOICEMAIL PROCESSING STARTED
Contact ID: xxxxx
Caller: +1234567890
Recording found in X.Xs
[TRANSCRIBE END] COMPLETED
[EMAIL SENT] MessageId: xxxxx
```

## Step 5: Production Configuration

### 5.1 Move SES Out of Sandbox

By default, SES is in sandbox mode (can only send to verified addresses).

To send to any email:
1. Go to SES Console
2. Click **Account Dashboard**
3. Click **Request production access**
4. Fill out the form
5. Wait for approval (usually 24 hours)

### 5.2 Enable Encryption

Encrypt recordings at rest:

```bash
aws s3api put-bucket-encryption \
  --bucket your-voicemail-recordings \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 5.3 Set Up Monitoring

Create CloudWatch alarms:

```bash
# Alarm for Lambda errors
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
  --dimensions Name=FunctionName,Value=voicemail-transcribe-email
```

### 5.4 Configure Lifecycle Policies

Delete old recordings after 90 days:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-voicemail-recordings \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "DeleteOldRecordings",
      "Status": "Enabled",
      "Prefix": "recordings/",
      "Expiration": {
        "Days": 90
      }
    }]
  }'
```

## Troubleshooting

### Lambda Function Not Found

**Error**: "Function not found"

**Solution**:
- Verify function exists: `aws lambda list-functions --region us-west-2`
- Check region matches your Connect instance
- Ensure function name is correct

### Recording Not Found

**Error**: "Recording file not found"

**Solution**:
- Increase `RECORDING_WAIT_TIME` to 90-100
- Verify S3 bucket path in `BASE_PATH`
- Check Connect recording configuration

### Email Not Sent

**Error**: "Email send failed"

**Solution**:
- Verify sender email in SES
- Check SES sending limits
- Confirm recipient email in attributes
- Review CloudWatch logs

### Transcription Failed

**Error**: "Transcription failed"

**Solution**:
- Check audio format (must be .wav, 8kHz+)
- Verify Transcribe service availability
- Check Lambda IAM permissions

## Next Steps

1. ✅ Integrate with your main Connect flow
2. ✅ Set up production monitoring
3. ✅ Configure email customization
4. ✅ Test all scenarios (# press, timeout, hangup)
5. ✅ Review CloudWatch logs
6. ✅ Set up cost alerts

## Support

Need help? Check:
- [README.md](../README.md) - Main documentation
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [GitHub Issues](https://github.com/godwillcho/amazon-connect-voicemail/issues)

---

**Installation complete!** 🎉
