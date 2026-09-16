import re
import socket
import smtplib
from urllib.parse import unquote

# In-memory DNS MX cache to prevent redundant queries
_MX_CACHE = {}

# Common junk extensions and asset noise patterns
JUNK_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif',
    '.css', '.js', '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z', '.woff', '.woff2', '.ttf',
    '.mp3', '.mp4', '.avi', '.mov', '.webm', '.exe', '.dmg', '.iso', '.map'
)

# Template placeholders, theme demos, and automated bot traps
JUNK_PATTERNS = [
    'sentry', 'wixpress', 'example.com', 'domain.com', 'email.com', 'schema.org',
    'bootstrap', 'wordpress', 'fontawesome', 'react', 'jquery', 'cloudflare',
    'mysite.com', 'yourdomain', 'yourcompany', 'example@', 'test@', 'admin@example',
    'user@domain', 'contact@yourdomain', 'info@mysite', 'username@', 'mywebsite.com',
    'themeforest', 'envato', 'elementor', 'webflow.io', 'squarespace.com', 'weebly.com',
    'shopify.com', 'godaddy.com', 'johndoe', 'janedoe', 'yourname', 'firstname', 'lastname',
    'sample@', 'lorem', 'ipsum', 'placeholder', 'nobody@', 'dummy@'
]

# Role-based addresses that lead to bounces, spam traps, or automated rejections
ROLE_BASED_PREFIXES = (
    'noreply@', 'no-reply@', 'donotreply@', 'do-not-reply@', 'mailer-daemon@',
    'postmaster@', 'abuse@', 'privacy@', 'legal@', 'security@', 'compliance@',
    'gdpr@', 'unsubscribe@', 'auto-reply@', 'auto-response@', 'system@'
)

DISPOSABLE_DOMAINS = {
    'tempmail.com', 'mailinator.com', '10minutemail.com', 'guerrillamail.com',
    'trashmail.com', 'yopmail.com', 'sharklasers.com', 'dispostable.com',
    'throwawaymail.com', 'temp-mail.org', 'fakeinbox.com', 'getnada.com',
    'dropmail.me', 'disposablemail.com', 'inboxkitten.com', 'crazymailing.com',
    '10mail.org', 'mytemp.email', 'tempail.com', 'burnermail.io'
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', re.IGNORECASE)


def sanitize_email_candidate(email: str) -> str:
    """Strips quotes, trailing punctuation, and URL encoding."""
    if not email or not isinstance(email, str):
        return ""
    clean = unquote(email).strip().lower()
    # Strip wrapping quotes, brackets, and trailing dots/commas
    clean = clean.strip("\"'<>[](){}:;, \t\r\n").lstrip('.').rstrip('.')
    return clean


def is_clean_syntax(email: str) -> bool:
    """Checks format, extensions, role-based traps, and noise patterns."""
    clean = sanitize_email_candidate(email)
    if not clean or len(clean) > 254:
        return False

    if not EMAIL_REGEX.match(clean):
        return False

    # Prevent consecutive dots in local part or domain
    if '..' in clean:
        return False

    if any(clean.endswith(ext) for ext in JUNK_EXTENSIONS):
        return False

    if any(clean.startswith(prefix) for prefix in ROLE_BASED_PREFIXES):
        return False

    if any(junk in clean for junk in JUNK_PATTERNS):
        return False

    parts = clean.split('@')
    if len(parts) != 2:
        return False

    local_part, domain = parts[0], parts[1]
    if len(local_part) < 1 or len(domain) < 3:
        return False

    # Domain must contain at least one dot and a valid TLD
    if '.' not in domain or domain.endswith('.'):
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

    clean_email = sanitize_email_candidate(email)
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
        cleaned = sanitize_email_candidate(e)
        if not cleaned or cleaned in seen:
            continue
        if verify_email(cleaned):
            valid.append(cleaned)
            seen.add(cleaned)
    return valid
