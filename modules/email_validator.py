import re
import socket
import smtplib
from urllib.parse import unquote

# In-memory DNS MX cache to prevent redundant queries
_MX_CACHE = {}

# Common junk extensions and noise patterns
JUNK_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico',
    '.css', '.js', '.pdf', '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf'
)

JUNK_PATTERNS = [
    'sentry', 'wixpress', 'example.com', 'domain.com', 'email.com', 'schema.org',
    'bootstrap', 'wordpress', 'fontawesome', 'react', 'jquery', 'cloudflare',
    'mysite.com', 'yourdomain', 'yourcompany', 'example@', 'test@', 'admin@example',
    'user@domain', 'contact@yourdomain', 'info@mysite', 'username@'
]

DISPOSABLE_DOMAINS = {
    'tempmail.com', 'mailinator.com', '10minutemail.com', 'guerrillamail.com',
    'trashmail.com', 'yopmail.com', 'sharklasers.com', 'dispostable.com',
    'throwawaymail.com', 'temp-mail.org', 'fakeinbox.com', 'getnada.com'
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', re.IGNORECASE)


def is_clean_syntax(email: str) -> bool:
    """Checks format, extensions, and noise patterns."""
    if not email or not isinstance(email, str):
        return False
    
    clean = unquote(email).strip().lower().lstrip('.')
    if len(clean) > 254:
        return False

    if not EMAIL_REGEX.match(clean):
        return False

    if any(clean.endswith(ext) for ext in JUNK_EXTENSIONS):
        return False

    if any(junk in clean for junk in JUNK_PATTERNS):
        return False

    parts = clean.split('@')
    if len(parts) != 2:
        return False

    local_part, domain = parts[0], parts[1]
    if len(local_part) < 1 or len(domain) < 3:
        return False

    if domain in DISPOSABLE_DOMAINS:
        return False

    return True


def get_mx_records(domain: str, timeout: float = 2.0):
    """
    Fetches DNS MX records for domain.
    Caches results in _MX_CACHE for maximum speed.
    """
    domain = domain.lower().strip()
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]

    mx_hosts = []

    # Try dnspython first
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout
        answers = resolver.resolve(domain, 'MX')
        mx_hosts = [str(r.exchange).rstrip('.') for r in answers]
    except Exception:
        # Fallback to standard socket A/AAAA check if dnspython not available or MX resolution fails
        try:
            socket.getaddrinfo(domain, 25, proto=socket.IPPROTO_TCP)
            mx_hosts = [domain]
        except Exception:
            mx_hosts = []

    _MX_CACHE[domain] = mx_hosts
    return mx_hosts


def check_smtp_mailbox(mx_host: str, recipient_email: str, timeout: float = 2.0) -> bool:
    """
    Performs non-intrusive SMTP Handshake (HELO -> MAIL FROM -> RCPT TO).
    Returns True if accepted (250) or if server doesn't reject explicitly.
    Returns False on hard bounce codes (550, 551, 553, 554).
    """
    try:
        smtp = smtplib.SMTP(timeout=timeout)
        code, _ = smtp.connect(mx_host, 25)
        if code != 220:
            smtp.close()
            return True

        smtp.helo('validator.local')
        smtp.mail('verify@validator.local')
        rcpt_code, _ = smtp.rcpt(recipient_email)
        smtp.quit()

        # 250 / 251 = Mailbox definitively exists & accepts mail
        if rcpt_code in (250, 251):
            return True

        # 550 / 551 / 553 / 554 = Definite rejection / User Unknown
        if rcpt_code in (550, 551, 552, 553, 554):
            return False

        return True
    except Exception:
        # If port 25 times out or is blocked by local ISP, MX record existence was confirmed
        return True


def verify_email(email: str, perform_smtp_check: bool = True) -> bool:
    """
    Full 3-layer deliverability verification:
    1. Syntax & Junk filter
    2. DNS MX Record lookup
    3. SMTP Handshake
    """
    if not is_clean_syntax(email):
        return False

    clean_email = unquote(email).strip().lower().lstrip('.')
    domain = clean_email.split('@')[1]

    # Layer 2: DNS MX Records
    mx_records = get_mx_records(domain)
    if not mx_records:
        return False

    # Layer 3: SMTP Handshake
    if perform_smtp_check and mx_records:
        primary_mx = mx_records[0]
        is_mailbox_active = check_smtp_mailbox(primary_mx, clean_email)
        if not is_mailbox_active:
            return False

    return True


def filter_valid_emails(emails: list) -> list:
    """
    Takes a list of candidate emails and returns only verified deliverable ones.
    """
    valid = []
    seen = set()
    for e in emails:
        if not e or not isinstance(e, str):
            continue
        cleaned = unquote(e).strip().lower().lstrip('.')
        if cleaned in seen:
            continue
        if verify_email(cleaned):
            valid.append(cleaned)
            seen.add(cleaned)
    return valid
