import os
import re
import json
import html
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin, unquote
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US,en;q=0.8',
}

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)

JUNK_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico',
    '.css', '.js', '.pdf', '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf'
)

DUMMY_EMAILS = {
    'example@email.com', 'example@gmail.com', 'example@example.com',
    'votre@email.com', 'votre-email@domaine.com', 'name@email.com',
    'info@mysite.com', 'user@domain.com', 'test@test.com', 'email@example.com'
}

CONTACT_KEYWORDS = [
    'contact', 'contactez', 'nous-contacter', 'reach', 'touch', 'about',
    'propos', 'qui-sommes-nous', 'mentions', 'legal', 'support', 'help',
    'team', 'equipe', 'rdv', 'appointment', 'info', 'service'
]


def decode_cf_email(cf_hex: str) -> str:
    """Decodes Cloudflare email obfuscation."""
    try:
        if not cf_hex or len(cf_hex) < 4:
            return ""
        r = int(cf_hex[:2], 16)
        return ''.join([chr(int(cf_hex[i:i+2], 16) ^ r) for i in range(2, len(cf_hex), 2)]).strip()
    except Exception:
        return ""


def clean_url(url):
    if not url:
        return None
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def is_valid_email(email):
    if not email:
        return False
    email_clean = unquote(email).strip().lower().strip("\"'<>[](){}:;, \t\r\n").lstrip('.')
    if any(email_clean.endswith(ext) for ext in JUNK_EXTENSIONS):
        return False
    if email_clean in DUMMY_EMAILS:
        return False
    parts = email_clean.split('@')
    if len(parts) != 2:
        return False
    local, domain = parts[0], parts[1]
    if len(local) < 1 or '.' not in domain:
        return False
    domain_parts = domain.split('.')
    if len(domain_parts[-1]) < 2:
        return False
    return True


def extract_emails_from_html(html_content):
    found = set()
    if not html_content:
        return found
    
    # 1. Unescape HTML entities (&#64; -> @)
    decoded_html = html.unescape(unquote(html_content))

    # 2. Regex find in raw HTML
    for raw_match in EMAIL_REGEX.findall(decoded_html):
        clean = unquote(raw_match).strip().lower()
        if is_valid_email(clean):
            found.add(clean)

    # 3. BeautifulSoup parsing for mailto, Cloudflare, and links
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Cloudflare data-cfemail
        for cf_tag in soup.find_all(attrs={"data-cfemail": True}):
            decoded_cf = decode_cf_email(cf_tag.get("data-cfemail"))
            if is_valid_email(decoded_cf):
                found.add(decoded_cf.lower())

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if href.lower().startswith('mailto:'):
                email = href.split('mailto:')[1].split('?')[0].split('&')[0].strip()
                clean = unquote(email).lower()
                if is_valid_email(clean):
                    found.add(clean)
            elif '/email-protection#' in href:
                cf_hex = href.split('/email-protection#')[-1].split('?')[0]
                decoded_cf = decode_cf_email(cf_hex)
                if is_valid_email(decoded_cf):
                    found.add(decoded_cf.lower())
    except Exception:
        pass

    return found


def find_contact_links(soup, base_url):
    contact_urls = set()
    if not soup:
        return contact_urls

    base_netloc = urlparse(base_url).netloc.lower().replace('www.', '')

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        text = a_tag.get_text().strip().lower()
        href_lower = href.lower()

        if any(kw in href_lower or kw in text for kw in CONTACT_KEYWORDS):
            full_url = urljoin(base_url, href).split('#')[0].rstrip('/')
            try:
                link_netloc = urlparse(full_url).netloc.lower().replace('www.', '')
                # Ensure it belongs to the same business domain
                if link_netloc == base_netloc and full_url not in contact_urls and full_url != base_url:
                    contact_urls.add(full_url)
                    if len(contact_urls) >= 4:
                        break
            except Exception:
                continue

    return contact_urls


def fetch_emails_from_website(website_url, timeout=7):
    emails = set()
    website_url = clean_url(website_url)
    if not website_url:
        return list(emails)

    # Skip social networks and maps links
    skip_domains = ('facebook.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com', 'linkedin.com', 'youtube.com', 'google.com', 'wa.me')
    netloc = urlparse(website_url).netloc.lower()
    if any(s in netloc for s in skip_domains):
        return list(emails)

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Fetch homepage
        resp = session.get(website_url, timeout=timeout, allow_redirects=True, verify=False)
        if resp.status_code == 200:
            html_text = resp.text
            emails.update(extract_emails_from_html(html_text))

            # If no email found on homepage, check contact / about subpages
            if not emails:
                soup = BeautifulSoup(html_text, 'html.parser')
                contact_links = find_contact_links(soup, resp.url)

                for link in contact_links:
                    try:
                        c_resp = session.get(link, timeout=timeout, allow_redirects=True, verify=False)
                        if c_resp.status_code == 200:
                            c_emails = extract_emails_from_html(c_resp.text)
                            emails.update(c_emails)
                            if emails:
                                break
                    except Exception:
                        continue
    except Exception:
        pass

    return list(emails)


def process_lead(lead, timeout):
    existing_emails = lead.get('emails', []) or []
    website = lead.get('website')

    if existing_emails:
        return lead, 0

    if not website:
        return lead, 0

    found_emails = fetch_emails_from_website(website, timeout=timeout)
    if found_emails:
        combined = list(dict.fromkeys(existing_emails + found_emails))
        lead['emails'] = combined
        return lead, len(found_emails)

    return lead, 0


def enrich_file(json_filepath, max_workers=12, timeout=7):
    if not os.path.exists(json_filepath):
        print(f"File not found: {json_filepath}", flush=True)
        return

    print(f"\nProcessing file: {json_filepath}", flush=True)
    with open(json_filepath, 'r', encoding='utf-8') as f:
        try:
            leads = json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {e}", flush=True)
            return

    total_leads = len(leads)
    indices_to_enrich = [i for i, l in enumerate(leads) if not l.get('emails') and l.get('website')]
    
    print(f"Total leads: {total_leads} | Leads needing emails: {len(indices_to_enrich)}", flush=True)

    if not indices_to_enrich:
        print("All leads already have emails or no websites available.", flush=True)
        return

    # Disable SSL warnings for scraper requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    enriched_count = 0
    new_emails_found = 0
    total_to_process = len(indices_to_enrich)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(process_lead, leads[idx], timeout): idx 
            for idx in indices_to_enrich
        }

        completed = 0
        for future in as_completed(future_to_idx):
            completed += 1
            idx = future_to_idx[future]
            try:
                updated_lead, count = future.result()
                leads[idx] = updated_lead
                if count > 0:
                    enriched_count += 1
                    new_emails_found += count
            except Exception:
                pass

            if completed % 5 == 0 or completed == total_to_process:
                print(f"--> Progress: {completed}/{total_to_process} websites scanned | Enriched: {enriched_count} leads ({new_emails_found} emails found)", flush=True)

    # Save updated JSON back to workspace
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)

    print(f"Saved enriched data to {json_filepath}", flush=True)
    print(f"Successfully added {new_emails_found} emails across {enriched_count} leads!", flush=True)


def find_all_cleaned_leads(root_dir="output"):
    matched_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f == "cleaned_leads.json":
                matched_files.append(os.path.join(dirpath, f))
    return matched_files


def main():
    parser = argparse.ArgumentParser(description="Enrich Scraped JSON Leads with Emails from Websites")
    parser.add_argument("--file", help="Path to specific cleaned_leads.json file")
    parser.add_argument("--dir", default="output", help="Directory to search recursively for cleaned_leads.json (default: output)")
    parser.add_argument("--threads", type=int, default=12, help="Number of concurrent scraper threads (default: 12)")
    parser.add_argument("--timeout", type=int, default=7, help="HTTP request timeout per website in seconds (default: 7)")

    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = find_all_cleaned_leads(args.dir)

    if not files:
        print(f"No cleaned_leads.json files found in '{args.dir}'.")
        return

    print("=" * 60)
    print(f"Starting Email Enrichment Engine")
    print(f"Found {len(files)} JSON lead file(s) to process")
    print(f"Threads: {args.threads} | Timeout: {args.timeout}s")
    print("=" * 60)

    for f in files:
        enrich_file(f, max_workers=args.threads, timeout=args.timeout)

    print("\n" + "=" * 60)
    print("Email Enrichment Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
