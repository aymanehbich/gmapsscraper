import re
import socket
import smtplib
from urllib.parse import unquote

# In-memory DNS MX/Host cache to prevent redundant queries
_MX_CACHE = {}

# Junk asset extensions falsely captured by regex in web pages
JUNK_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif',
    '.css', '.js', '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z', '.woff', '.woff2', '.ttf',
    '.mp3', '.mp4', '.avi', '.mov', '.webm', '.exe', '.dmg', '.iso', '.map'
)

# Explicit placeholder and dummy domains (exact domain match or domain ending)
JUNK_DOMAINS = {
    'example.com', 'domain.com', 'mysite.com', 'mywebsite.com', 'yourdomain.com',
    'yourcompany.com', 'sample.com', 'test.com', 'schema.org', 'wixpress.com',
    'sentry.io', 'themeforest.net', 'envato.com', 'elementor.com', 'weebly.com',
    'bootstrap.com', 'fontawesome.com', 'tempuri.org', 'localhost', 'test.test'
}

# Explicit dummy/placeholder local parts (e.g., test@..., dummy@...)
JUNK_LOCAL_PARTS = {
    'example', 'test', 'sample', 'placeholder', 'nobody', 'dummy',
    'username', 'yourname', 'firstname', 'lastname', 'user', 'johndoe',
    'janedoe', 'lorem', 'ipsum'
}

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
    """Checks format, extensions, role-based traps, and dummy placeholder patterns."""
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

    parts = clean.split('@')
    if len(parts) != 2:
        return False

    local_part, domain = parts[0], parts[1]
    if len(local_part) < 1 or len(domain) < 3:
        return False

    # Check exact dummy local parts
    if local_part in JUNK_LOCAL_PARTS:
        return False

    # Check exact dummy / disposable domains
    if domain in JUNK_DOMAINS or domain in DISPOSABLE_DOMAINS:
        return False

    for jd in JUNK_DOMAINS:
        if domain.endswith('.' + jd):
            return False

    # Domain must contain at least one dot and a valid TLD
    if '.' not in domain or domain.endswith('.'):
        return False

    return True


def get_mx_records(domain: str, timeout: float = 2.0):
    """
    Fetches DNS MX records for domain.
    1. Uses system resolver first (works in all CI/CD, local, and restricted environments).
    2. Falls back to public DNS if system resolver fails.
    3. Falls back to host IP resolution (A/AAAA records under RFC 5321).
    Caches results in _MX_CACHE for high performance.
    """
    domain = domain.lower().strip()
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]

    mx_hosts = []

    # 1. Try dnspython with System Default Resolver
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout
        try:
            answers = resolver.resolve(domain, 'MX')
            mx_hosts = [str(r.exchange).rstrip('.') for r in answers]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            # Domain exists or no MX -> try A record on domain
            try:
                a_answers = resolver.resolve(domain, 'A')
                if a_answers:
                    mx_hosts = [domain]
            except Exception:
                mx_hosts = []
        except Exception:
            # Fallback to public DNS if system resolver failed or timed out
            try:
                resolver.nameservers = ['8.8.8.8', '1.1.1.1']
                answers = resolver.resolve(domain, 'MX')
                mx_hosts = [str(r.exchange).rstrip('.') for r in answers]
            except Exception:
                mx_hosts = []
    except Exception:
        pass

    # 2. Universal Socket Fallback (works when dnspython is absent or DNS port 53 is firewalled)
    if not mx_hosts:
        try:
            # gethostbyname checks system hosts/DNS cache without binding to specific port
            socket.gethostbyname(domain)
            mx_hosts = [domain]
        except Exception:
            try:
                # Also check www. subdomain if apex domain doesn't resolve
                socket.gethostbyname('www.' + domain)
                mx_hosts = [domain]
            except Exception:
                mx_hosts = []

    _MX_CACHE[domain] = mx_hosts
    return mx_hosts


def check_smtp_mailbox(mx_host: str, recipient_email: str, timeout: float = 2.0) -> bool:
    """
    Performs non-intrusive SMTP Handshake (HELO -> MAIL FROM -> RCPT TO).
    Returns True on 250 (OK) or if connection is refused/firewalled.
    Only returns False on explicit permanent user rejection (550, 551, 553, 554).
    """
    try:
        smtp = smtplib.SMTP(timeout=timeout)
        code, _ = smtp.connect(mx_host, 25)
        if code != 220:
            try:
                smtp.close()
            except Exception:
                pass
            return True

        smtp.helo('validator.local')
        smtp.mail('verify@validator.local')
        rcpt_code, _ = smtp.rcpt(recipient_email)
        try:
            smtp.quit()
        except Exception:
            pass

        # 550 / 551 / 553 / 554 = Definite mailbox rejection
        if rcpt_code in (550, 551, 552, 553, 554):
            return False

        return True
    except Exception:
        # Port 25 blocked on cloud/ISP -> treat as valid if DNS MX/A was confirmed
        return True


def verify_email(email: str, perform_smtp_check: bool = False) -> bool:
    """
    Multi-layer deliverability verification:
    1. Syntax & Junk filter (fast, precise)
    2. DNS MX / Host record lookup (with Google DNS fallback)
    3. Optional SMTP handshake (non-blocking)
    """
    if not is_clean_syntax(email):
        return False

    clean_email = sanitize_email_candidate(email)
    parts = clean_email.split('@')
    if len(parts) != 2:
        return False
    domain = parts[1]

    # Layer 2: DNS MX / A Records
    mx_records = get_mx_records(domain)
    if not mx_records:
        return False

    # Layer 3: Optional SMTP Handshake
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
