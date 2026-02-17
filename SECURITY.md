# Security Guidelines

## 🛡️ Security Features Implemented

### 1. Rate Limiting

- **Search endpoint**: 30 requests per minute
- **Books API**: 20 requests per minute
- **Captcha generation**: 10 requests per minute
- **Global limits**: 200 requests per day, 50 per hour

### 2. Input Validation & Sanitization

- Search queries are validated and sanitized
- HTML tags are stripped to prevent XSS
- Maximum query length enforced (500 characters)
- Suspicious patterns are blocked (script tags, javascript:, etc.)

### 3. Session Security

- HTTPOnly cookies (prevents XSS access)
- Secure cookies in HTTPS environments
- SameSite protection against CSRF
- Session timeout after 1 hour

### 4. Security Headers

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (HTTPS only)

### 5. Captcha Protection

- 15-minute timeout per captcha
- Maximum 3 attempts per captcha
- Automatic cleanup of expired captchas
- Session-based captcha tracking

### 6. Logging & Monitoring

- Security events are logged
- Failed captcha attempts tracked
- Error logging without sensitive data exposure

## 🔧 Configuration Requirements

### Environment Variables (Required for Production)

```bash
# Strong secret key (32+ characters)
FLASK_SECRET_KEY=your-very-long-random-secret-key-here

# Enable HTTPS cookies in production
HTTPS_ENABLED=true

# Production environment
FLASK_ENV=production
```

### Google Sheets Security

- Use service account with minimal permissions
- Only grant "Viewer" access to spreadsheets
- Regularly rotate service account keys
- Keep credentials in environment variables only

## 🚨 Security Checklist Before Deployment

### ✅ Environment

- [ ] Strong `FLASK_SECRET_KEY` set (32+ characters)
- [ ] All credentials in environment variables
- [ ] No hardcoded secrets in code
- [ ] `.env` file in `.gitignore`

### ✅ Production Settings

- [ ] `FLASK_ENV=production`
- [ ] `HTTPS_ENABLED=true` if using HTTPS
- [ ] Debug mode disabled
- [ ] Error pages don't expose stack traces

### ✅ Infrastructure

- [ ] HTTPS enabled (SSL/TLS certificate)
- [ ] Reverse proxy configured (nginx/cloudflare)
- [ ] Firewall rules configured
- [ ] Regular security updates scheduled

### ✅ Monitoring

- [ ] Log monitoring set up
- [ ] Rate limit alerts configured
- [ ] Failed authentication tracking
- [ ] Resource usage monitoring

## 🔒 Additional Recommendations

### For Public Deployment

1. **Use HTTPS everywhere** - Never deploy without SSL
2. **Implement CSP headers** - Content Security Policy
3. **Regular security audits** - Scan for vulnerabilities
4. **Update dependencies** - Keep packages current
5. **Backup strategy** - Secure data backups

### For High-Traffic Sites

1. **Redis for rate limiting** - Replace in-memory storage
2. **Database for sessions** - Replace file-based sessions
3. **Load balancing** - Distribute traffic
4. **DDoS protection** - CloudFlare or similar
5. **Security monitoring** - Real-time threat detection

### API Security

1. **API versioning** - /api/v1/ prefix
2. **Request signing** - HMAC verification
3. **OAuth2/JWT** - For authenticated endpoints
4. **API documentation** - Security requirements

## 🚫 Security Don'ts

❌ **Never commit these to Git:**

- `.env` files
- Service account JSON files
- SSL certificates/private keys
- Database passwords
- API keys

❌ **Never expose in logs:**

- User passwords
- API keys
- Session tokens
- Personal information

❌ **Never trust user input:**

- Always validate and sanitize
- Use parameterized queries
- Escape output
- Implement CSRF protection

## 📞 Security Incident Response

1. **Immediate Actions:**
   - Rotate all credentials
   - Enable emergency rate limiting
   - Review access logs
   - Notify users if data compromised

2. **Investigation:**
   - Preserve logs for analysis
   - Identify attack vectors
   - Assess data impact
   - Document timeline

3. **Recovery:**
   - Patch vulnerabilities
   - Update security measures
   - Monitor for repeat attacks
   - Update incident procedures

## 📚 Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Guide](https://flask.palletsprojects.com/en/2.3.x/security/)
- [Google Cloud Security](https://cloud.google.com/security)
- [Python Security Guidelines](https://python.org/dev/security/)
