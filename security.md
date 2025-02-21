# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the AWS Resource Inventory Tool, please follow these steps:

1. **DO NOT** create a public GitHub issue
2. Email me at rodrigofreis@gmail.com
3. Include detailed information about the vulnerability
4. Wait for confirmation before any public disclosure

## Security Best Practices

### AWS Credentials

1. **Never commit credentials:**
   - AWS access keys
   - Secret keys
   - Private keys
   - Environment files
   - Configuration files with secrets

2. **Use secure credential storage:**
   - AWS CLI credentials file (`~/.aws/credentials`)
   - Environment variables
   - AWS IAM roles
   - AWS Secrets Manager for production environments

3. **Credential rotation:**
   - Regularly rotate access keys
   - Use temporary credentials when possible
   - Enable MFA for AWS accounts
   - Monitor AWS CloudTrail for unauthorized API usage

### Development Guidelines

1. **Code Security:**
   - No hardcoded secrets in code
   - Use environment variables for configuration
   - Implement proper error handling for credential failures
   - Use the principle of least privilege

2. **Git Practices:**
   - Use to prevent committing sensitive files
   - Enable pre-commit hooks to detect secrets
   - Regularly audit git history for secrets
   - Use signed commits when possible

3. **Dependencies:**
   - Keep dependencies updated
   - Regularly check for security vulnerabilities
   - Use fixed versions in requirements.txt
   - Implement dependency scanning in CI/CD

### Running the Tool

1. **Authentication:**
   - Use IAM roles when running in AWS
   - Use named profiles for local development
   - Never share AWS credentials
   - Monitor and audit tool usage

2. **Access Control:**
   - Use minimal IAM permissions required
   - Implement resource tagging
   - Enable AWS Organizations SCPs
   - Use AWS CloudWatch for monitoring

3. **Data Protection:**
   - Encrypt data at rest
   - Use secure transport (HTTPS/TLS)
   - Implement proper logging
   - Handle errors securely

## Security Checklist

Before contributing, ensure:

- [ ] No credentials in code
- [ ] No sensitive data in comments
- [ ] Proper error handling
- [ ] Updated dependencies
- [ ] Security tests passed
- [ ] Documentation updated

## Contact

For security concerns, contact:
- Security Team: rodrigofreis@gmail.com
- Maintainers: rodrigofreis@gmail.com

## Updates

This security policy will be updated as needed. Check back regularly for changes.

Last updated: 2025-02-20
