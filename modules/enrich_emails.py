import os
import re
import json
import html
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin, unquote
import requests
from bs4 import BeautifulSoup

try:
    from modules.email_validator import verify_email, filter_valid_emails, is_clean_syntax, sanitize_email_candidate
except ImportError:
    from email_validator import verify_email, filter_valid_emails, is_clean_syntax, sanitize_email_candidate

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

# Domains to skip crawling (social media, platforms, directory portals)
SKIP_DOMAINS = {
    'facebook.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com',
    'linkedin.com', 'youtube.com', 'pinterest.com', 'dabadoc.com', 'doctolib.fr',
    'wa.me', 'whatsapp.com', 'google.com', 'maps.google.com', 'waze.com',
    'yelp.com', 'tripadvisor.com', 'pagesjaunes.fr', 'telecontact.ma'
}

# Multilingual keywords for high-priority subpages (French, English, Spanish)
CONTACT_SUBPAGE_KEYWORDS = [
    'contact', 'contactez', 'contacter', 'nous-contacter', 'contact-us',
    'a-propos', 'apropos', 'qui-sommes-nous', 'about', 'about-us',
    'mentions-legales', 'mentions', 'legal', 'impressum', 'politique-de-confidentialite',
    'notre-equipe', 'equipe', 'le-cabinet', 'cabinet', 'team',
    'rdv', 'rendez-vous', 'prendre-rendez-vous', 'rendezvous', 'booking'
]


def decode_cf_email(cf_hex: str) -> str:
    """Decodes Cloudflare email obfuscation (data-cfemail or /cdn-cgi/l/email-protection#...)."""
    try:
        if not cf_hex or len(cf_hex) < 4:
            return ""
        r = int(cf_hex[:2], 16)
        email = ''.join([chr(int(cf_hex[i:i+2], 16) ^ r) for i in range(2, len(cf_hex), 2)])
        return email.strip()
    except Exception:
        return ""


def clean_url(url: str):
    if not url:
        return None
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def is_crawlable_domain(netloc: str) -> bool:
    """Returns False for social networks, chat apps, and directory aggregators."""
    if not netloc:
        return False
    clean_host = netloc.lower().split(':')[0]
    for skip in SKIP_DOMAINS:
        if clean_host == skip or clean_host.endswith('.' + skip):
            return False
    return True


def extract_emails_from_html(html_content: str) -> set:
    found = set()
    if not html_content:
        return found

    # Unescape HTML entities (e.g. &#64; -> @) and URL encoding
    decoded_html = html.unescape(unquote(html_content))

    # 1. Regex search across raw HTML
    for raw_match in EMAIL_REGEX.findall(decoded_html):
        clean = sanitize_email_candidate(raw_match)
        if is_clean_syntax(clean):
            found.add(clean)

    # 2. BeautifulSoup parsing for mailto, Cloudflare, and DOM links
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check Cloudflare protected emails: <span data-cfemail="..."> or <a href="/cdn-cgi/l/email-protection#...">
        for cf_tag in soup.find_all(attrs={"data-cfemail": True}):
            cf_val = cf_tag.get("data-cfemail")
            decoded_cf = decode_cf_email(cf_val)
            if decoded_cf and is_clean_syntax(decoded_cf):
                found.add(sanitize_email_candidate(decoded_cf))

        # Check hrefs
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()

            # Mailto links
            if href.lower().startswith('mailto:'):
                email = href.split('mailto:')[1].split('?')[0].split('&')[0].strip()
                clean = sanitize_email_candidate(email)
                if is_clean_syntax(clean):
                    found.add(clean)

            # Cloudflare email protection link URL
            if '/email-protection#' in href:
                cf_hex = href.split('/email-protection#')[-1].split('?')[0]
                decoded_cf = decode_cf_email(cf_hex)
                if decoded_cf and is_clean_syntax(decoded_cf):
                    found.add(sanitize_email_candidate(decoded_cf))

        # Check stripped text strings
        for text in soup.stripped_strings:
            for match in EMAIL_REGEX.findall(html.unescape(text)):
                clean = sanitize_email_candidate(match)
                if is_clean_syntax(clean):
                    found.add(clean)

    except Exception:
        pass

    return found


def fetch_emails_from_website(website_url: str, timeout: int = 7) -> list:
    emails = set()
    url = clean_url(website_url)
    if not url:
        return []

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not is_crawlable_domain(domain):
            return []
    except Exception:
        return []

    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Scrape Homepage
    homepage_html = None
    try:
        resp = session.get(url, timeout=timeout, verify=False, allow_redirects=True)
        if resp.status_code == 200:
            homepage_html = resp.text
            emails.update(extract_emails_from_html(homepage_html))
    except Exception:
        pass

    # 2. If no email found on homepage, discover and crawl contact / about subpages
    if not emails and homepage_html:
        try:
            soup = BeautifulSoup(homepage_html, 'html.parser')
            contact_links = []
            seen_urls = {url.rstrip('/')}

            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                text = a.get_text().strip().lower()
                href_lower = href.lower()

                # Check if link or anchor text matches any contact keyword
                matches_keyword = any(k in href_lower or k in text for k in CONTACT_SUBPAGE_KEYWORDS)

                if matches_keyword:
                    full_url = urljoin(url, href).split('#')[0].rstrip('/')
                    try:
                        link_domain = urlparse(full_url).netloc.lower()
                        # Ensure subpage stays within same business domain
                        if (link_domain == domain or link_domain.endswith('.' + domain)) and full_url not in seen_urls:
                            seen_urls.add(full_url)
                            contact_links.append(full_url)
                            if len(contact_links) >= 4:  # Crawl up to 4 relevant subpages
                                break
                    except Exception:
                        continue

            # Crawl subpages
            for c_url in contact_links:
                try:
                    c_resp = session.get(c_url, timeout=timeout, verify=False, allow_redirects=True)
                    if c_resp.status_code == 200:
                        c_emails = extract_emails_from_html(c_resp.text)
                        emails.update(c_emails)
                        if emails:  # Stop searching once an email is discovered
                            break
                except Exception:
                    continue

        except Exception:
            pass

    # Perform Deep Deliverability & MX Verification on all found candidate emails
    if emails:
        valid_deliverable = filter_valid_emails(list(emails))
        return valid_deliverable

    return []


def process_lead(lead: dict, timeout: int):
    existing_emails = lead.get('emails', []) or []
    website = lead.get('website')

    # If existing emails are already present, verify their deliverability
    if existing_emails:
        valid_existing = filter_valid_emails(existing_emails)
        lead['emails'] = valid_existing
        if valid_existing:
            return lead, 0

    if not website:
        return lead, 0

    found_emails = fetch_emails_from_website(website, timeout=timeout)
    if found_emails:
        combined = list(dict.fromkeys(existing_emails + found_emails))
        valid_combined = filter_valid_emails(combined)
        lead['emails'] = valid_combined
        return lead, len(valid_combined)

    return lead, 0


def enrich_file(json_filepath: str, max_workers: int = 12, timeout: int = 7):
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

    # Disable SSL warnings for crawler requests
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
                print(f"--> Progress: {completed}/{total_to_process} websites scanned | Verified Enriched: {enriched_count} leads ({new_emails_found} valid emails)", flush=True)

    # Save updated JSON back to workspace
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)

    print(f"Saved verified enriched data to {json_filepath}", flush=True)
    print(f"Successfully added {new_emails_found} verified deliverable emails across {enriched_count} leads!", flush=True)


def find_all_cleaned_leads(root_dir="output"):
    matched_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f == "cleaned_leads.json":
                matched_files.append(os.path.join(dirpath, f))
    return matched_files


def main():
    parser = argparse.ArgumentParser(description="Enrich Scraped JSON Leads with Verified Deliverable Emails")
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
    print(f"Starting Deliverability-Verified Email Enrichment Engine")
    print(f"Found {len(files)} JSON lead file(s) to process")
    print(f"Threads: {args.threads} | Timeout: {args.timeout}s | Deliverability Check: ACTIVE")
    print("=" * 60)

    for f in files:
        enrich_file(f, max_workers=args.threads, timeout=args.timeout)

    print("\n" + "=" * 60)
    print("Email Enrichment & Deliverability Validation Completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
