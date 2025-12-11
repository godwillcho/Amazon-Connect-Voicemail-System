# Quick Start Guide

Get the Amazon Connect Voicemail System up and running in 15 minutes.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS Account
- [ ] Amazon Connect instance created
- [ ] AWS CLI installed and configured
- [ ] Git installed
- [ ] Email address for testing

## 5-Step Setup

### Step 1: Clone Repository (2 minutes)

```bash
git clone https://github.com/godwillcho/amazon-connect-voicemail.git
cd amazon-connect-voicemail
```

### Step 2: Verify SES Email (3 minutes)

```bash
# Verify sender email
aws ses verify-email-identity \
  --email-address noreply@yourdomain.com \
  --region us-west-2

# Check your inbox and click verification link

# Verify recipient email (for testing in sandbox)
aws ses verify-email-identity \
  --email-address your-test-email@example.com \
  --region us-west-2
```

### Step 3: Deploy Lambda (5 minutes)

```bash
# Create IAM role first (one-time setup)
aws iam create-role \
  --role-name voicemail-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name voicemail-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Deploy function
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
    BASE_PATH=your-connect-bucket/connect/recordings,
    EMAIL_SENDER=noreply@yourdomain.com,
    URL_EXPIRATION=604800,
    RECORDING_WAIT_TIME=70
  }"

cd ..
```

**Or use the deployment script:**

```bash
./deploy.sh voicemail-transcribe-email us-west-2
```

### Step 4: Configure Amazon Connect (3 minutes)

#### 4a. Add Lambda to Connect

```bash
# Grant Connect permission to invoke Lambda
aws lambda add-permission \
  --function-name voicemail-transcribe-email \
  --statement-id AllowConnectInvoke \
  --action lambda:InvokeFunction \
  --principal connect.amazonaws.com \
  --source-arn arn:aws:connect:us-west-2:YOUR_ACCOUNT:instance/YOUR_INSTANCE_ID
```

**Via Console:**
1. Go to Amazon Connect Console
2. Select your instance
3. Navigate to **Contact flows** → **AWS Lambda**
4. Find and select `voicemail-transcribe-email`
5. Click **Add Lambda Function**

#### 4b. Import Flow

1. In Amazon Connect Console, go to **Routing** → **Contact flows**
2. Click **Create contact flow**
3. Click dropdown next to **Save** → **Import flow (beta)**
4. Select `connect-flow/VoiceMailModule.json`
5. Click **Import**

#### 4c. Update Flow

1. Click the **"Email-copy-1"** block
2. Select `voicemail-transcribe-email` from Lambda dropdown
3. Click **Save**
4. Update **"NEEDED ATTRIBUTES"** block with your test email
5. Click **Save** → **Publish**

### Step 5: Test (2 minutes)

#### 5a. Create Test Flow

1. Create a new flow named "Voicemail Test"
2. Add these blocks:
   - **Set contact attributes**:
     - emailRecipient: `your-test-email@example.com`
     - RecipientName: `Your Name`
   - **Transfer to flow**: Select `VoiceMailModule`
3. Save and publish

#### 5b. Assign to Number

1. Go to **Phone numbers**
2. Click **Claim a number** (if you don't have one)
3. Edit your test number
4. Set Contact flow to "Voicemail Test"
5. Save

#### 5c. Make Test Call

1. Call your Amazon Connect number
2. Listen to instructions
3. Record a short message after the beep
4. Press `#` to finish
5. Wait 2-3 minutes for email

## Verification Checklist

After testing, verify:

- [ ] CloudWatch logs show successful execution
- [ ] Recording appears in S3 bucket
- [ ] Email received with transcription
- [ ] Audio link in email works
- [ ] Duration shown in email is correct

### Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/voicemail-transcribe-email --follow
```

Look for:
```
VOICEMAIL PROCESSING STARTED
[SUCCESS] Found file at s3://...
[TRANSCRIBE END] Status: COMPLETED
[EMAIL SENT] MessageId: xxx
```

### Check S3

```bash
aws s3 ls s3://your-bucket/connect/recordings/ivr/ --recursive
```

## Common Issues & Quick Fixes

### Issue: Email not received

**Quick fix:**
```bash
# Verify both sender and recipient are verified
aws ses list-verified-email-addresses --region us-west-2
```

### Issue: Recording not found

**Quick fix:**
```bash
# Increase wait time
aws lambda update-function-configuration \
  --function-name voicemail-transcribe-email \
  --environment Variables="{...,RECORDING_WAIT_TIME=90}"
```

### Issue: Lambda not invoked

**Quick fix:**
- Verify Lambda is added to Connect instance
- Check Lambda ARN in Connect flow
- Republish flow after changes

## Next Steps

### For Production Use

1. **Move SES out of sandbox**
   - Go to SES Console → Request production access
   - Fill out form and submit

2. **Adjust recording timeout**
   - Change from 5 seconds to 60 seconds
   - Update `GetParticipantInput` in flow
   - Update `RECORDING_WAIT_TIME=70`

3. **Set up monitoring**
   - Create CloudWatch alarms
   - Configure SNS notifications
   - Set up log retention

4. **Secure your setup**
   - Enable S3 encryption
   - Set up VPC (optional)
   - Review IAM permissions

### Integrate with Main Flow

Add voicemail to your existing flow:

```
1. Check agent availability
2. If unavailable → Transfer to VoiceMailModule
3. Set contact attributes before transfer:
   - emailRecipient: agent's email
   - RecipientName: agent's name
```

## Full Documentation

For detailed information, see:

- [Installation Guide](docs/INSTALLATION.md) - Complete setup
- [Configuration](docs/CONFIGURATION.md) - All settings
- [Architecture](docs/ARCHITECTURE.md) - How it works
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Problem solving

## Support

Need help?

- 📚 [Read the docs](docs/)
- 🐛 [Report issues](https://github.com/godwillcho/amazon-connect-voicemail/issues)
- 💬 [Ask questions](https://github.com/godwillcho/amazon-connect-voicemail/discussions)

---

**Congratulations!** 🎉 Your voicemail system is ready!
