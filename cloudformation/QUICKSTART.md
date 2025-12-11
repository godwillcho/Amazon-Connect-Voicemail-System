# CloudFormation Quick Reference

## One-Command Deployment

```bash
./deploy-cfn.sh voicemail-system us-west-2
```

## What Gets Created

| Resource | Description |
|----------|-------------|
| **Lambda Function** | Voicemail processing |
| **IAM Role** | With S3, Transcribe, SES permissions |
| **S3 Bucket** | For voicemail recordings (optional) |
| **CloudWatch Logs** | Function logging |
| **CloudWatch Alarms** | Error monitoring (optional) |
| **SNS Topic** | Alarm notifications (optional) |
| **Dashboard** | Performance metrics (optional) |

## Required Parameters

```json
{
  "EmailSender": "noreply@example.com",
  "ConnectInstanceId": "a8fab42a-...",
  "ConnectInstanceArn": "arn:aws:connect:..."
}
```

## Common Commands

### Deploy
```bash
aws cloudformation create-stack \
  --stack-name voicemail-system \
  --template-body file://cloudformation/voicemail-stack.yaml \
  --parameters file://cloudformation/parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

### Update
```bash
aws cloudformation update-stack \
  --stack-name voicemail-system \
  --use-previous-template \
  --parameters file://cloudformation/parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

### Status
```bash
aws cloudformation describe-stacks \
  --stack-name voicemail-system \
  --region us-west-2
```

### Outputs
```bash
aws cloudformation describe-stacks \
  --stack-name voicemail-system \
  --query 'Stacks[0].Outputs' \
  --output table
```

### Delete
```bash
# Empty S3 bucket first
aws s3 rm s3://bucket-name/ --recursive

# Delete stack
aws cloudformation delete-stack \
  --stack-name voicemail-system \
  --region us-west-2
```

## Post-Deployment

1. **Upload Lambda code**
   ```bash
   cd lambda && zip function.zip lambda_function.py
   aws lambda update-function-code \
     --function-name [name] --zip-file fileb://function.zip
   ```

2. **Verify SES email**
   ```bash
   aws ses verify-email-identity --email-address [sender]
   ```

3. **Configure Connect**
   - Set S3 bucket in Data storage
   - Import flow JSON
   - Update Lambda ARN

4. **Test**
   - Call Connect number
   - Leave voicemail
   - Check email

## Troubleshooting

### Stack Failed
```bash
# View events
aws cloudformation describe-stack-events \
  --stack-name voicemail-system --max-items 10
```

### Missing Permissions
```bash
# Add capability flag
--capabilities CAPABILITY_NAMED_IAM
```

### Bucket Exists
```bash
# Use existing bucket
"S3BucketName": "my-existing-bucket"

# Or leave empty for auto-generated name
"S3BucketName": ""
```

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| Lambda (1000 calls) | ~$0.50 |
| S3 (10 GB) | ~$0.23 |
| CloudWatch | ~$1.00 |
| Transcribe | ~$24.00 |
| **Total** | **~$26/month** |

## Support

- 📘 [Full Guide](cloudformation/README.md)
- 🐛 [Issues](https://github.com/godwillcho/amazon-connect-voicemail/issues)
- 📚 [Documentation](../docs/)
