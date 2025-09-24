# Environment Configuration Guide

This document provides a comprehensive guide for configuring the Python backend with Mastercard API and MTN MOMO API integrations.

## Overview

The backend now supports real API integrations with:
- **Mastercard API**: For payment processing, card validation, tokenization, and transfers
- **MTN MOMO API**: For mobile money transactions in supported regions

## Environment Variables

### Required Environment Variables

Add the following environment variables to your `.env` file in the `fintech_backend/` directory:

```bash
# Mastercard API Configuration
MASTERCARD_API_KEY=gP3tqRnkR0w3y4Wg_XQXtHpob3XbS26MD7gjYsTc8dccc84
MASTERCARD_PARTNER_ID=1741965455194-Client-MTF-000000
MASTERCARD_ENVIRONMENT=sandbox
MASTERCARD_CERT_PATH=/secure/certs/mastercard/hoardrun.p12
MASTERCARD_PRIVATE_KEY_PATH=/secure/certs/mastercard/hoardrun.key
MASTERCARD_CLIENT_ID=1741965455194-Client-MTF-000000
MASTERCARD_ORG_NAME=Hoardrun
MASTERCARD_COUNTRY=GH
MASTERCARD_CERT_PASSWORD=your_cert_password_here

# MTN MOMO API Configuration
MOMO_API_URL=https://sandbox.momodeveloper.mtn.com
MOMO_PRIMARY_KEY=b0432b6329f7448289100f0c0963147a
MOMO_SECONDARY_KEY=0b4e640ea72f443fb4910cbf50f8d712
MOMO_TARGET_ENVIRONMENT=sandbox
```

### Environment Variable Descriptions

#### Mastercard API Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MASTERCARD_API_KEY` | Your Mastercard API key | Yes | - |
| `MASTERCARD_PARTNER_ID` | Mastercard Partner ID | Yes | - |
| `MASTERCARD_ENVIRONMENT` | Environment (sandbox/production) | No | sandbox |
| `MASTERCARD_CERT_PATH` | Path to P12 certificate file | Yes | /secure/certs/mastercard/hoardrun.p12 |
| `MASTERCARD_PRIVATE_KEY_PATH` | Path to private key file | Yes | /secure/certs/mastercard/hoardrun.key |
| `MASTERCARD_CLIENT_ID` | Mastercard Client ID | Yes | - |
| `MASTERCARD_ORG_NAME` | Organization name | No | Hoardrun |
| `MASTERCARD_COUNTRY` | Country code | No | GH |
| `MASTERCARD_CERT_PASSWORD` | Certificate password | Yes | - |

#### MTN MOMO API Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MOMO_API_URL` | MTN MOMO API base URL | No | https://sandbox.momodeveloper.mtn.com |
| `MOMO_PRIMARY_KEY` | MTN MOMO Primary subscription key | Yes | - |
| `MOMO_SECONDARY_KEY` | MTN MOMO Secondary subscription key | Yes | - |
| `MOMO_TARGET_ENVIRONMENT` | Target environment | No | sandbox |

## Certificate Setup

### Mastercard Certificates

1. **Obtain Certificates**: Get your P12 certificate and private key from Mastercard Developer Portal
2. **Secure Storage**: Store certificates in a secure directory (e.g., `/secure/certs/mastercard/`)
3. **File Permissions**: Ensure proper file permissions (600) for certificate files
4. **Path Configuration**: Update `MASTERCARD_CERT_PATH` and `MASTERCARD_PRIVATE_KEY_PATH` accordingly

```bash
# Example certificate setup
mkdir -p /secure/certs/mastercard/
chmod 700 /secure/certs/mastercard/
cp hoardrun.p12 /secure/certs/mastercard/
cp hoardrun.key /secure/certs/mastercard/
chmod 600 /secure/certs/mastercard/*
```

## API Integration Features

### Mastercard API Integration

The backend now supports:

- **Payment Processing**: Create and process payments
- **Payment Status**: Check payment status and history
- **Refunds**: Process payment refunds
- **Card Validation**: Validate card information
- **Card Tokenization**: Securely tokenize cards
- **Money Transfers**: Create and track transfers
- **Exchange Rates**: Get real-time exchange rates
- **Transaction History**: Retrieve transaction history

### MTN MOMO API Integration

The backend now supports:

- **Request to Pay**: Initiate payment requests
- **Transfers**: Send money to recipients
- **Deposits**: Process account deposits
- **Account Verification**: Validate mobile money accounts
- **Transaction Status**: Check transaction status
- **Account Balance**: Get account balance information

## Service Architecture

### New Services Added

1. **MastercardService** (`app/services/mastercard_service.py`)
   - Handles all Mastercard API operations
   - Provides payment processing capabilities
   - Manages card validation and tokenization

2. **MTN MOMO Integration** (Updated `app/services/mobile_money_service.py`)
   - Real MTN MOMO API integration for MTN_MOMO provider
   - Fallback to mock implementation for other providers
   - Enhanced transaction processing

### API Clients

1. **MastercardAPIClient** (`app/external/mastercard_api.py`)
   - HTTP client for Mastercard API
   - SSL certificate authentication
   - Request signing and security

2. **MTNMomoAPIClient** (`app/external/mtn_momo_api.py`)
   - HTTP client for MTN MOMO API
   - OAuth2 token management
   - Sandbox and production support

## Environment-Specific Configuration

### Development Environment

```bash
MASTERCARD_ENVIRONMENT=sandbox
MOMO_TARGET_ENVIRONMENT=sandbox
MOMO_API_URL=https://sandbox.momodeveloper.mtn.com
```

### Production Environment

```bash
MASTERCARD_ENVIRONMENT=production
MOMO_TARGET_ENVIRONMENT=production
MOMO_API_URL=https://api.momodeveloper.mtn.com
```

## Security Considerations

### Certificate Security

- Store certificates outside the application directory
- Use proper file permissions (600 for files, 700 for directories)
- Never commit certificates to version control
- Rotate certificates regularly

### API Key Security

- Use environment variables for all sensitive data
- Never hardcode API keys in source code
- Use different keys for different environments
- Monitor API key usage and rotate regularly

### Network Security

- Use HTTPS for all API communications
- Implement proper SSL certificate validation
- Use secure network connections in production

## Testing

### API Integration Testing

1. **Mastercard API Testing**:
   - Test payment processing with sandbox credentials
   - Verify card validation functionality
   - Test refund processing

2. **MTN MOMO API Testing**:
   - Test payment requests in sandbox
   - Verify account validation
   - Test transfer functionality

### Environment Testing

```bash
# Test configuration loading
python -c "from app.config.settings import settings; print(f'Mastercard: {settings.mastercard_environment}, MOMO: {settings.momo_target_environment}')"
```

## Troubleshooting

### Common Issues

1. **Certificate Issues**:
   - Verify certificate file paths
   - Check file permissions
   - Validate certificate password

2. **API Connection Issues**:
   - Verify API URLs
   - Check network connectivity
   - Validate API keys

3. **Authentication Issues**:
   - Verify API credentials
   - Check token expiration
   - Validate request signatures

### Logging

The system provides comprehensive logging for debugging:

```python
# Enable debug logging
LOG_LEVEL=DEBUG
```

## Migration Guide

### From Mock to Real APIs

1. **Update Environment Variables**: Add the new API configuration variables
2. **Install Dependencies**: Ensure all required Python packages are installed
3. **Certificate Setup**: Configure Mastercard certificates
4. **Test Integration**: Verify API connectivity in sandbox environment
5. **Production Deployment**: Update production environment variables

## Support

For issues related to:
- **Mastercard API**: Contact Mastercard Developer Support
- **MTN MOMO API**: Contact MTN Developer Support
- **Backend Integration**: Check application logs and error messages

## Next Steps

1. Add required Python dependencies to `requirements.txt`
2. Test API integrations in sandbox environment
3. Create comprehensive API endpoint documentation
4. Implement error handling and retry mechanisms
5. Add monitoring and alerting for API failures
