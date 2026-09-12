import os
import re
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin, unquote
import requests
from bs4 import BeautifulSoup

try:
    from modules.email_validator import verify_email, filter_valid_emails, is_clean_syntax
except ImportError:
    from email_validator import verify_email, filter_valid_emails, is_clean_syntax

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)


def clean_url(url):
    if not url:
        return None
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def extract_emails_from_html(html_content):
    found = set()
    if not html_content:
        return found
    
    # 1. Regex find directly in raw text
    for raw_match in EMAIL_REGEX.findall(html_content):
        decoded = unquote(raw_match).strip().lower()
        if is_clean_syntax(decoded):
            found.add(decoded)

    # 2. BeautifulSoup mailto: links
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.lower().startswith('mailto:'):
                email = href.split('mailto:')[1].split('?')[0].strip()
                decoded = unquote(email).lower()
                if is_clean_syntax(decoded):
                    found.add(decoded)
    except Exception:
        pass

    # 3. Hidden comments, script tags or metadata
    try:
        if not soup:
            soup = BeautifulSoup(html_content, 'html.parser')
        for text in soup.stripped_strings:
            for match in EMAIL_REGEX.findall(text):
                decoded = unquote(match).strip().lower()
                if is_clean_syntax(decoded):
                    found.add(decoded)
    except Exception:
        pass

    return found


def fetch_emails_from_website(website_url, timeout=7):
    emails = set()
    url = clean_url(website_url)
    if not url:
        return []

    try:
        domain = urlparse(url).netloc
    except Exception:
        return []

    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Scrape Homepage
    try:
        resp = session.get(url, timeout=timeout, verify=False, allow_redirects=True)
        if resp.status_code == 200:
            emails.update(extract_emails_from_html(resp.text))
            
            # If no email on homepage, look for Contact / About subpages
            if not emails:
                soup = BeautifulSoup(resp.text, 'html.parser')
                contact_links = []
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    text = a.get_text().lower()
                    
                    # Target contact/about pages
                    if any(k in href.lower() or k in text for k in ['contact', 'about', 'reach', 'team', 'support', 'impressum']):
                        full_url = urljoin(url, href)
                        # Keep within same domain
                        if urlparse(full_url).netloc == domain and full_url not in contact_links:
                            contact_links.append(full_url)
                            if len(contact_links) >= 3:  # Limit subpages to keep speed fast
                                break
                
                # Scrape candidate contact pages
                for c_url in contact_links:
                    try:
                        c_resp = session.get(c_url, timeout=timeout, verify=False)
                        if c_resp.status_code == 200:
                            c_emails = extract_emails_from_html(c_resp.text)
                            emails.update(c_emails)
                            if emails:  # Stop searching subpages once an email is found
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


def process_lead(lead, timeout):
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
        # Keep strictly deliverable emails
        valid_combined = filter_valid_emails(combined)
        lead['emails'] = valid_combined
        return lead, len(valid_combined)

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
            except Exception as e:
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
