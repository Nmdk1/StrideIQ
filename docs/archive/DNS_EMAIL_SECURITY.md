# DNS Email Security Configuration

**Reference:** M10 in Security Audit Report (External Security Report - Feb 2026)

This document describes the required DNS configuration to prevent email spoofing attacks.

## Overview

Three DNS records work together to authenticate emails from your domain:
- **SPF** - Specifies which servers can send email for your domain
- **DKIM** - Adds a cryptographic signature to verify email authenticity
- **DMARC** - Tells receivers what to do with emails that fail SPF/DKIM checks

## Required DNS Records

### 1. SPF Record (Sender Policy Framework)

**Record Type:** TXT  
**Host:** `@` or `strideiq.run`  
**Value:**
```
v=spf1 include:_spf.google.com include:amazonses.com -all
```

**Explanation:**
- `v=spf1` - SPF version 1
- `include:_spf.google.com` - Allow Google Workspace to send
- `include:amazonses.com` - Allow AWS SES to send
- `-all` - Hard fail for all other sources (reject spoofed emails)

**Note:** Adjust the `include:` statements based on your actual email providers:
- Google Workspace: `include:_spf.google.com`
- AWS SES: `include:amazonses.com`
- SendGrid: `include:sendgrid.net`
- Mailgun: `include:mailgun.org`

### 2. DKIM Record (DomainKeys Identified Mail)

DKIM requires generating a key pair. The setup depends on your email provider:

**Google Workspace:**
1. Admin Console → Apps → Google Workspace → Gmail → Authenticate email
2. Generate DKIM key
3. Add the provided TXT record

**AWS SES:**
1. AWS Console → SES → Identities → Domain → DKIM
2. Enable Easy DKIM
3. Add the 3 provided CNAME records

**Example DKIM Record:**
```
Record Type: TXT
Host: google._domainkey.strideiq.run
Value: v=DKIM1; k=rsa; p=MIIBIjANBgkqh... (your public key)
```

### 3. DMARC Record (Domain-based Message Authentication)

**Record Type:** TXT  
**Host:** `_dmarc` or `_dmarc.strideiq.run`  
**Value:**
```
v=DMARC1; p=reject; rua=mailto:dmarc-reports@strideiq.run; ruf=mailto:dmarc-forensics@strideiq.run; fo=1; adkim=s; aspf=s
```

**Explanation:**
- `v=DMARC1` - DMARC version 1
- `p=reject` - Reject emails that fail authentication (strictest policy)
- `rua=mailto:...` - Where to send aggregate reports
- `ruf=mailto:...` - Where to send forensic reports
- `fo=1` - Generate forensic report for any failure
- `adkim=s` - Strict DKIM alignment
- `aspf=s` - Strict SPF alignment

**Recommended Rollout:**
1. Start with `p=none` to monitor without affecting delivery
2. Move to `p=quarantine` after 2 weeks of clean reports
3. Move to `p=reject` after another 2 weeks

## Verification

### Check SPF
```bash
nslookup -type=TXT strideiq.run
# or
dig TXT strideiq.run
```

### Check DKIM
```bash
nslookup -type=TXT google._domainkey.strideiq.run
```

### Check DMARC
```bash
nslookup -type=TXT _dmarc.strideiq.run
```

### Online Tools
- [MXToolbox DMARC Check](https://mxtoolbox.com/DMARC.aspx)
- [Google Admin Toolbox](https://toolbox.googleapps.com/apps/checkmx/)
- [DMARC Analyzer](https://www.dmarcanalyzer.com/)

## Setting Up DMARC Reporting

Create email addresses to receive reports:
- `dmarc-reports@strideiq.run` - Daily aggregate reports (XML)
- `dmarc-forensics@strideiq.run` - Individual failure reports

Consider using a DMARC reporting service to parse reports:
- [Valimail](https://www.valimail.com/)
- [Dmarcian](https://dmarcian.com/)
- [Postmark DMARC](https://dmarc.postmarkapp.com/)

## Timeline

1. **Immediately:** Add SPF record
2. **Week 1:** Configure DKIM with email provider, add DMARC with `p=none`
3. **Week 3:** Review reports, move to `p=quarantine`
4. **Week 5:** If no issues, move to `p=reject`

## Impact

With proper email authentication:
- Attackers cannot spoof emails from `@strideiq.run`
- Phishing attacks using your domain will be rejected
- Email deliverability improves (authenticated emails are trusted)
- Brand reputation is protected

## Related Security Items

- H6: Email change verification (code fix)
- M9: Security headers (Caddyfile fix)
- M2: Password policy (code fix)
