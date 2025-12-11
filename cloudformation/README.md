# CloudFormation Deployment Guide

Deploy the entire Amazon Connect Voicemail System using AWS CloudFormation.

## What Gets Created

### Core Resources
- ✅ Lambda Function (with placeholder code)
- ✅ IAM Execution Role (with required permissions)
- ✅ S3 Bucket (optional - can use existing)
- ✅ S3 Bucket Policy (allows Connect to upload)
- ✅ Lambda Permission (allows Connect to invoke)

### Monitoring (Optional)
- ✅ CloudWatch Log Group
- ✅ CloudWatch Alarms (errors, throttles, duration)
- ✅ CloudWatch Dashboard
- ✅ SNS Topic for alarm notifications

### Configuration
- ✅ Environment variables pre-configured
- ✅ Lifecycle policies for S3
- ✅ Encryption enabled
- ✅ All IAM permissions

## Quick Deploy

### Option 1: AWS Console (Easiest)

1. **Open CloudFormation Console**
   ```
   https://console.aws.amazon.com/cloudformation
   ```

2. **Create Stack**
   - Click "Create stack" → "With new resources"
   - Choose "Upload a template file"
   - Select `cloudformation/voicemail-stack.yaml`
   - Click "Next"

3. **Fill Parameters**
   - Stack name: `voicemail-system`
   - Fill in required parameters (see Parameter Reference below)
   - Click "Next"

4. **Configure Stack Options**
   - Tags (optional): Add project tags
   - Permissions (optional): Use existing IAM role
   - Click "Next"

5. **Review and Create**
   - Check "I acknowledge that AWS CloudFormation might create IAM resources"
   - Click "Create stack"

6. **Wait for Completion**
   - Status will change to `CREATE_COMPLETE` (~3-5 minutes)
   - Check "Outputs" tab for important values

### Option 2: AWS CLI (Automated)

1. **Copy Parameters Template**
   ```bash
   cp cloudformation/parameters.json.example cloudformation/parameters.json
   ```

2. **Edit Parameters**
   ```bash
   nano cloudformation/parameters.json
   # Update with your values
   ```

3. **Deploy Stack**
   ```bash
   aws cloudformation create-stack \
     --stack-name voicemail-system \
     --template-body file://cloudformation/voicemail-stack.yaml \
     --parameters file://cloudformation/parameters.json \
     --capabilities CAPABILITY_NAMED_IAM \
     --region us-west-2
   ```

4. **Monitor Deployment**
   ```bash
   aws cloudformation wait stack-create-complete \
     --stack-name voicemail-system \
     --region us-west-2
   
   aws cloudformation describe-stacks \
     --stack-name voicemail-system \
     --region us-west-2
   ```

## Parameter Reference

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| **EmailSender** | Email to send from (must verify in SES) | `noreply@example.com` |
| **ConnectInstanceId** | Your Connect instance ID | `a8fab42a-...` |
| **ConnectInstanceArn** | Full Connect instance ARN | `arn:aws:connect:...` |

### Important Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| **LambdaFunctionName** | `voicemail-transcribe-email` | Lambda function name |
| **S3BucketName** | (auto-generated) | Leave empty to create new bucket |
| **S3BucketPrefix** | `connect/recordings` | Path within bucket |
| **RecordingWaitTime** | `70` | Seconds to wait before searching |
| **TranscriptionLanguage** | `en-US` | Language for transcription |

### Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| **LambdaTimeout** | `180` | Lambda timeout (seconds) |
| **LambdaMemorySize** | `512` | Lambda memory (MB) |
| **URLExpirationSeconds** | `604800` | URL expiration (7 days) |
| **EnableS3Encryption** | `true` | Encrypt S3 bucket |
| **S3LifecycleDays** | `90` | Days to retain recordings |
| **EnableCloudWatchAlarms** | `true` | Create monitoring alarms |
| **AlarmEmail** | (empty) | Email for alarm notifications |
| **LogRetentionDays** | `30` | CloudWatch log retention |

## Finding Your Connect Instance Details

### Get Instance ID

1. **Via Console**:
   - Go to Amazon Connect Console
   - Select your instance
   - URL will show: `https://[alias].my.connect.aws/connect/home?instance=[ID]`
   - Copy the ID

2. **Via CLI**:
   ```bash
   aws connect list-instances --region us-west-2
   ```

### Get Instance ARN

```bash
aws connect describe-instance \
  --instance-id a8fab42a-42a6-446d-b8fc-31ea25332f07 \
  --region us-west-2 \
  --query 'Instance.Arn' \
  --output text
```

## Post-Deployment Steps

### 1. Upload Lambda Code

The stack creates a Lambda function with placeholder code. Deploy actual code:

```bash
# Package Lambda function
cd lambda
zip function.zip lambda_function.py

# Get function name from stack outputs
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name voicemail-system \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text)

# Update function code
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://function.zip \
  --region us-west-2
```

### 2. Verify SES Email

```bash
# Get sender email from stack
EMAIL_SENDER=$(aws cloudformation describe-stacks \
  --stack-name voicemail-system \
  --query 'Stacks[0].Parameters[?ParameterKey==`EmailSender`].ParameterValue' \
  --output text)

# Verify in SES
aws ses verify-email-identity \
  --email-address $EMAIL_SENDER \
  --region us-west-2

# Check inbox and click verification link
```

### 3. Configure Connect Recording

1. Go to Amazon Connect Console → Your instance
2. Navigate to **Data storage** → **Call recordings**
3. Set S3 bucket (from stack outputs)
4. Set prefix: `connect/recordings`
5. Save

### 4. Import Connect Flow

1. Go to **Routing** → **Contact flows**
2. Create new flow
3. Import `connect-flow/VoiceMailModule.json`
4. Update Lambda function (select from dropdown)
5. Update contact attributes (emailRecipient, RecipientName)
6. Publish flow

### 5. Test the System

```bash
# View logs
aws logs tail /aws/lambda/$FUNCTION_NAME --follow

# Check CloudWatch dashboard (from stack outputs)
# Call your Connect number and leave voicemail
```

## Stack Outputs

After deployment, check the Outputs tab for:

| Output | Description |
|--------|-------------|
| **LambdaFunctionArn** | Lambda ARN for Connect flow |
| **LambdaFunctionName** | Function name for updates |
| **S3BucketName** | Bucket for recordings |
| **S3RecordingPath** | Full path (BASE_PATH value) |
| **IAMRoleArn** | Execution role ARN |
| **DashboardURL** | CloudWatch dashboard link |
| **NextSteps** | Quick reference guide |

## Updating the Stack

### Update Parameters

```bash
aws cloudformation update-stack \
  --stack-name voicemail-system \
  --use-previous-template \
  --parameters file://cloudformation/parameters-updated.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

### Update Template

```bash
aws cloudformation update-stack \
  --stack-name voicemail-system \
  --template-body file://cloudformation/voicemail-stack.yaml \
  --parameters file://cloudformation/parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

## Troubleshooting

### Stack Creation Failed

**View Events**:
```bash
aws cloudformation describe-stack-events \
  --stack-name voicemail-system \
  --region us-west-2 \
  --max-items 20
```

**Common Issues**:

1. **IAM Permissions**: Ensure you have permissions to create IAM roles
   - Solution: Add `--capabilities CAPABILITY_NAMED_IAM`

2. **Bucket Name Conflict**: Bucket name already exists
   - Solution: Leave `S3BucketName` empty for auto-generation

3. **Invalid Parameters**: Check parameter format
   - ConnectInstanceId must be UUID format
   - EmailSender must be valid email format
   - ConnectInstanceArn must be valid ARN format

### Lambda Permission Issues

If Connect can't invoke Lambda:

```bash
# Manually add permission
aws lambda add-permission \
  --function-name voicemail-transcribe-email \
  --statement-id AllowConnectInvoke \
  --action lambda:InvokeFunction \
  --principal connect.amazonaws.com \
  --source-arn arn:aws:connect:region:account:instance/id
```

### Alarm Email Not Received

Check SNS subscription:

```bash
# List subscriptions
aws sns list-subscriptions --region us-west-2

# Resend confirmation if needed
# Check spam folder for confirmation email
```

## Deleting the Stack

**Warning**: This will delete all resources including S3 bucket and recordings!

### Backup First

```bash
# Backup S3 recordings
aws s3 sync s3://your-bucket/connect/recordings ./recordings-backup

# Export Lambda code
aws lambda get-function \
  --function-name voicemail-transcribe-email \
  --query 'Code.Location' \
  --output text | xargs wget -O lambda-backup.zip
```

### Delete Stack

```bash
# If S3 bucket has objects, empty it first
aws s3 rm s3://voicemail-recordings-123456789012/ --recursive

# Delete stack
aws cloudformation delete-stack \
  --stack-name voicemail-system \
  --region us-west-2

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name voicemail-system \
  --region us-west-2
```

## Cost Estimation

Resources created by this stack:

| Resource | Cost |
|----------|------|
| Lambda | $0.20 per 1M requests + compute |
| S3 | $0.023 per GB/month |
| CloudWatch Logs | $0.50 per GB ingested |
| CloudWatch Alarms | $0.10 per alarm/month |
| SNS | $0.50 per 1M requests |
| Transcribe | $0.024 per minute |
| SES | $0.10 per 1,000 emails |

**Estimated monthly cost for 1,000 voicemails**: ~$26

## Advanced Configuration

### Use Existing S3 Bucket

Set `S3BucketName` parameter to your existing bucket:

```json
{
  "ParameterKey": "S3BucketName",
  "ParameterValue": "my-existing-bucket"
}
```

**Note**: You must manually configure bucket policy to allow Connect access.

### Disable Monitoring

Set parameters:

```json
{
  "ParameterKey": "EnableCloudWatchAlarms",
  "ParameterValue": "false"
},
{
  "ParameterKey": "AlarmEmail",
  "ParameterValue": ""
}
```

### Change Retention Policies

```json
{
  "ParameterKey": "S3LifecycleDays",
  "ParameterValue": "180"
},
{
  "ParameterKey": "LogRetentionDays",
  "ParameterValue": "90"
}
```

## Stack Exports

The stack exports these values for use in other stacks:

- `voicemail-system-LambdaArn`
- `voicemail-system-LambdaName`
- `voicemail-system-S3Bucket`
- `voicemail-system-S3Path`
- `voicemail-system-RoleArn`
- `voicemail-system-AlarmTopic`

Reference in other stacks:

```yaml
LambdaFunctionArn:
  Fn::ImportValue: voicemail-system-LambdaArn
```

## Support

For issues with CloudFormation deployment:

- Check **Events** tab in CloudFormation console
- Review **Resources** tab for failed resources
- See [Troubleshooting Guide](../docs/TROUBLESHOOTING.md)
- Open [GitHub issue](https://github.com/godwillcho/amazon-connect-voicemail/issues)

---

**Ready to deploy!** 🚀
