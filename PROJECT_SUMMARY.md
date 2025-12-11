# Amazon Connect Voicemail System - Project Summary

## Repository Information

**GitHub Repository**: https://github.com/godwillcho/amazon-connect-voicemail  
**Author**: Godwill Cho  
**License**: MIT  
**Version**: 1.0.0

## What's Included

### Core Files
- `lambda/lambda_function.py` - Production-ready Lambda function (591 lines)
- `connect-flow/VoiceMailModule.json` - Amazon Connect flow configuration
- `deploy.sh` - Automated deployment script

### Documentation
- `README.md` - Main project documentation
- `docs/QUICKSTART.md` - 15-minute setup guide
- `docs/INSTALLATION.md` - Complete installation guide
- `docs/CONFIGURATION.md` - Configuration reference
- `docs/ARCHITECTURE.md` - System architecture
- `docs/TROUBLESHOOTING.md` - Troubleshooting guide

### Project Files
- `LICENSE` - MIT License
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guidelines
- `.gitignore` - Git ignore rules

## Features

✅ Automatic voicemail recording  
✅ AI-powered transcription (AWS Transcribe)  
✅ Email notifications with HTML formatting  
✅ Duration detection (excludes silence)  
✅ Handles # press, timeout, or hangup  
✅ Professional email design  
✅ Production-ready code  
✅ Comprehensive documentation  

## Quick Start

```bash
# Clone repository
git clone https://github.com/godwillcho/amazon-connect-voicemail.git
cd amazon-connect-voicemail

# Deploy
./deploy.sh

# Import Connect flow
# Upload connect-flow/VoiceMailModule.json to Amazon Connect
```

## System Requirements

- AWS Account
- Amazon Connect instance
- S3 bucket for recordings
- SES configured for email
- Python 3.9+ (for Lambda)

## Cost

Approximately **$0.024 per voicemail** (~$24/month for 1,000 voicemails)

## Architecture

```
Caller → Connect → Lambda (Async) → Transcribe → SES → Email
              ↓
           S3 Recording
```

## Configuration

### Required Environment Variables
- `BASE_PATH` - S3 bucket/prefix
- `EMAIL_SENDER` - Sender email address

### Optional Environment Variables
- `URL_EXPIRATION` - Presigned URL expiration (default: 604800)
- `RECORDING_WAIT_TIME` - Wait before searching (default: 70)

## Support

- 📚 Documentation: https://github.com/godwillcho/amazon-connect-voicemail/tree/main/docs
- 🐛 Issues: https://github.com/godwillcho/amazon-connect-voicemail/issues
- 💬 Discussions: https://github.com/godwillcho/amazon-connect-voicemail/discussions

## Contact

**Email**: godwill.achu.cho@gmail.com  
**GitHub**: https://github.com/godwillcho

---

**Ready to deploy!** 🚀
