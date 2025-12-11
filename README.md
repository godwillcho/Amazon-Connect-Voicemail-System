# Amazon Connect Voicemail System

Professional voicemail system for Amazon Connect with automated transcription and email notifications.

[![AWS](https://img.shields.io/badge/AWS-Lambda-orange)](https://aws.amazon.com/lambda/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Features

- **Automatic Recording** - Records voicemails when callers can't reach you
- **AI Transcription** - Uses AWS Transcribe for accurate speech-to-text
- **Email Notifications** - Sends HTML emails with transcription and audio link
- **Duration Detection** - Shows actual message length (excludes silence)
- **Flexible Recording** - Handles # press, timeout, or caller hangup
- **Professional Design** - Clean, mobile-friendly email layout

## 🚀 Quick Start

### Option 1: CloudFormation (Recommended)

Deploy entire infrastructure with one command:

```bash
# Clone repository
git clone https://github.com/godwillcho/amazon-connect-voicemail.git
cd amazon-connect-voicemail

# Configure and deploy
cp cloudformation/parameters.json.example cloudformation/parameters.json
# Edit parameters.json with your values
./deploy-cfn.sh
```

See [CloudFormation Guide](cloudformation/README.md) for details.

### Option 2: Manual Deployment

```bash
# Deploy Lambda function only
./deploy.sh voicemail-transcribe-email us-west-2

# Then configure S3, IAM, and Connect manually
```

**Full instructions**: [Installation Guide](docs/INSTALLATION.md)

## 📖 Documentation

- 📘 [Installation Guide](docs/INSTALLATION.md) - Complete setup instructions
- 🔧 [Configuration](docs/CONFIGURATION.md) - Environment variables and settings
- 🐛 [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## 🏗️ Architecture

```
Caller → Amazon Connect → Lambda (Async) → AWS Transcribe → SES Email
                    ↓
              S3 Recording
```

**How it works:**
1. Caller leaves voicemail after beep
2. Amazon Connect invokes Lambda asynchronously
3. Lambda waits for recording to complete (configurable)
4. Recording automatically uploaded to S3
5. Lambda transcribes audio and sends email notification

## 📁 Repository Structure

```
├── lambda/                  # Lambda function code
│   ├── lambda_function.py  # Main handler
│   └── requirements.txt    # Python dependencies
├── connect-flow/           # Amazon Connect flow
│   └── VoiceMailModule.json
├── cloudformation/         # Infrastructure as Code
│   ├── voicemail-stack.yaml
│   ├── parameters.json.example
│   └── README.md
├── docs/                   # Documentation
│   ├── INSTALLATION.md
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
├── deploy.sh              # Lambda deployment script
├── deploy-cfn.sh          # CloudFormation deployment
├── README.md
├── LICENSE
└── CHANGELOG.md
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BASE_PATH` | ✅ | - | S3 bucket/prefix (e.g., `my-bucket/recordings`) |
| `EMAIL_SENDER` | ✅ | - | Sender email (must be verified in SES) |
| `URL_EXPIRATION` | ❌ | 604800 | Presigned URL expiration (seconds) |
| `RECORDING_WAIT_TIME` | ❌ | 70 | Wait before searching for recording |

### Example Lambda Configuration

```bash
BASE_PATH=voicemail-recordings/connect
EMAIL_SENDER=noreply@example.com
URL_EXPIRATION=604800
RECORDING_WAIT_TIME=70
```

## 💰 Cost Estimation

**Per 60-second voicemail:**
- Lambda: ~$0.000014
- AWS Transcribe: ~$0.024
- S3 Storage: ~$0.000001
- SES Email: ~$0.0001
- **Total: ~$0.024**

**For 1,000 voicemails/month: ~$24**

## 📧 Email Format

Recipients receive an HTML email like this:

```
Voicemail for: John Doe
There is a voicemail from +1234567890.

[Listen to the voicemail]
Duration: 15s

Voicemail transcription
This is the transcribed message text...
```

## 🔐 Security & Permissions

### Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject",
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob",
        "ses:SendEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

See [Installation Guide](docs/INSTALLATION.md) for complete IAM policy.

## 🧪 Testing

### Test Scenarios

1. **# Press**: Caller records message and presses #
2. **Timeout**: Caller records until timeout (default 60s)
3. **Hangup**: Caller hangs up mid-recording

All scenarios should successfully send email notifications.

### View Logs

```bash
aws logs tail /aws/lambda/voicemail-transcribe-email --follow
```

## 🛠️ Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Recording not found | Increase `RECORDING_WAIT_TIME` to 90-100 |
| Email not received | Verify sender email in SES, check sandbox mode |
| Lambda timeout | Increase timeout to 180 seconds |
| Empty transcription | Check audio quality (minimum 8kHz) |

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for details.

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📚 [Documentation](docs/)
- 🐛 [Report Issues](https://github.com/godwillcho/amazon-connect-voicemail/issues)
- 💬 [Discussions](https://github.com/godwillcho/amazon-connect-voicemail/discussions)

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 🌟 Acknowledgments

Built with:
- [AWS Lambda](https://aws.amazon.com/lambda/)
- [AWS Transcribe](https://aws.amazon.com/transcribe/)
- [Amazon Connect](https://aws.amazon.com/connect/)
- [Amazon SES](https://aws.amazon.com/ses/)

---

**Made with ❤️ for Amazon Connect users**

⭐ **Star this repo if you find it useful!**
