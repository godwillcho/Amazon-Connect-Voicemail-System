# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-11

### Added
- Initial release of Amazon Connect Voicemail System
- Automatic voicemail recording and transcription
- Email notifications with HTML formatting
- AWS Transcribe integration for speech-to-text
- Duration detection (excludes trailing silence)
- Configurable wait time via environment variable
- Support for # press, timeout, and hangup scenarios
- Professional email design with mobile responsiveness
- Presigned S3 URLs for secure audio access
- Comprehensive error handling and logging

### Features
- Asynchronous Lambda invocation from Connect flow
- Smart recording search with expanding time windows
- Retry logic for improved reliability
- Clean, production-ready code
- Full documentation and deployment guides

## [Unreleased]

### Planned
- Multi-language transcription support configuration
- Voicemail duration limits
- Custom email templates
- Integration with other notification channels (SMS, Slack)
- Voicemail management dashboard
