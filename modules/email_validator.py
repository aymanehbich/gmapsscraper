from urllib.parse import unquote

JUNK_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico',
    '.css', '.js', '.pdf', '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf'
)


def filter_valid_emails(emails: list) -> list:
    """Returns all clean candidate emails."""
    if not emails:
        return []
    valid = []
    seen = set()
    for e in emails:
        if not e or not isinstance(e, str):
            continue
        clean = unquote(e).strip().lower().strip("\"'<>[](){}:;, \t\r\n").lstrip('.').rstrip('.')
        if not clean or clean in seen or '@' not in clean:
            continue
        if any(clean.endswith(ext) for ext in JUNK_EXTENSIONS):
            continue
        valid.append(clean)
        seen.add(clean)
    return valid
