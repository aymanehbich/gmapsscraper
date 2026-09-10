import os
import sys
import json
import argparse
import subprocess
from modules.clean_leads import clean_and_deduplicate_leads
from modules.enrich_emails import enrich_file

def safe_name(name):
    # Sanitize names for folder paths
    return name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("(", "").replace(")", "")

def get_default_config_path(filename):
    config_path = os.path.join("config", filename)
    if os.path.exists(config_path):
        return config_path
    return filename

def run_scraper():
    parser = argparse.ArgumentParser(description="Google Maps Scraper Orchestrator")
    parser.add_argument("--niche", required=True, help="Niche to scrape (must exist in niches.json)")
    parser.add_argument("--targets", default=get_default_config_path("targets.json"), help="Path to targets.json file")
    parser.add_argument("--niches-file", default=get_default_config_path("niches.json"), help="Path to niches.json file")
    default_proxy_file = "proxies.txt" if os.path.exists("proxies.txt") else (
        get_default_config_path("proxies.txt") if os.path.exists(get_default_config_path("proxies.txt")) else None
    )

    parser.add_argument("--depth", type=int, default=30, help="Scroll depth (default: 30)")
    parser.add_argument("--concurrency", type=int, default=6, help="Concurrency level -c (default: 6)")
    parser.add_argument("--pages-per-browser", type=int, default=5, help="Number of pages per browser process")
    parser.add_argument("--browser-pool-size", type=int, help="Size of the browser pool")
    parser.add_argument("--exit-on-inactivity", default="5m", help="Exit on inactivity (default: 5m)")
    parser.add_argument("--proxy", help="Single proxy URL (e.g. http://user:pass@host:port)")
    parser.add_argument("--proxy-file", default=default_proxy_file, help="Path to proxy file (default: proxies.txt if exists)")
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw_results.json after cleaning")
    parser.add_argument("--city", help="Limit scrape to a specific city name (e.g. 'Austin TX' or 'Lyon')")
    parser.add_argument("--enrich-emails", action="store_true", help="Crawl business websites to extract contact emails after scraping")

    args = parser.parse_args()

    # Load targets
    if not os.path.exists(args.targets):
        print(f"Error: Targets file not found at '{args.targets}'")
        sys.exit(1)
    
    with open(args.targets, "r", encoding="utf-8") as f:
        targets = json.load(f)

    # Filter targets by city if specified
    if args.city:
        filtered_targets = {}
        for country, country_data in targets.items():
            matching_cities = [c for c in country_data.get("cities", []) if args.city.lower() in c.lower()]
            if matching_cities:
                filtered_targets[country] = {
                    "lang": country_data.get("lang", "EN"),
                    "country_name": country_data.get("country_name", country.replace('_', ' ')),
                    "cities": matching_cities
                }
        targets = filtered_targets
        if not targets:
            print(f"Error: City '{args.city}' not found in target locations.")
            sys.exit(1)

    # Load niches
    if not os.path.exists(args.niches_file):
        print(f"Error: Niches file not found at '{args.niches_file}'")
        sys.exit(1)
        
    with open(args.niches_file, "r", encoding="utf-8") as f:
        niches_data = json.load(f)

    if args.niche not in niches_data:
        print(f"Error: Niche '{args.niche}' not found in {args.niches_file}")
        print("Available niches:")
        for n in sorted(niches_data.keys()):
            print(f"  - {n}")
        sys.exit(1)

    niche_translations = niches_data[args.niche]

    # Calculate total targets for progress reporting
    total_jobs = sum(len(country_data["cities"]) for country_data in targets.values())
    current_job = 0

    print("=" * 60)
    print(f"Starting GMaps Scrape Orchestration")
    print(f"Target Niche: {args.niche}")
    print(f"Total Targets: {total_jobs} cities across {len(targets)} countries/regions")
    print("=" * 60)

    for country, country_data in targets.items():
        lang = country_data.get("lang", "EN").upper()
        country_display = country_data.get("country_name", country.replace('_', ' '))
        prep = "à" if lang == "FR" else "in"

        # Find correct translation keyword
        keyword = niche_translations.get(lang, niche_translations.get("EN"))
        if not keyword:
            print(f"Warning: No translation found for {args.niche} in language {lang}. Falling back to default.")
            keyword = args.niche

        cities = country_data.get("cities", [])
        safe_country_name = safe_name(country)
        safe_niche_name = safe_name(args.niche)

        for city in cities:
            current_job += 1
            safe_city_name = safe_name(city)

            # Establish directories
            dir_path = os.path.join("output", safe_niche_name, safe_country_name, safe_city_name)
            os.makedirs(dir_path, exist_ok=True)

            raw_output = os.path.join(dir_path, "raw_results.json")
            clean_output = os.path.join(dir_path, "cleaned_leads.json")

            print(f"\n[{current_job}/{total_jobs}] {country} -> {city}")
            
            # Checkpoint: Skip if already cleaned
            if os.path.exists(clean_output):
                print(f"--> Checkpoint: Already scraped and cleaned. Skipping.")
                continue

            # Write temporary query file inside the target directory
            # Format: "[Keyword] [prep] [City], [Country]" (e.g. "plombier à Rabat, Maroc")
            query_str = f"{keyword} {prep} {city}, {country_display}"
            temp_queries_file = os.path.join(dir_path, "queries_temp.txt")
            with open(temp_queries_file, "w", encoding="utf-8") as qf:
                qf.write(query_str + "\n")

            # Absolute paths for Docker volumes
            abspath_queries = os.path.abspath(temp_queries_file)
            abspath_out = os.path.abspath(dir_path)

            # Build Docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", "gmaps-playwright-cache:/opt",
                "-v", f"{abspath_queries}:/queries.txt:ro",
                "-v", f"{abspath_out}:/out",
            ]

            # Mount and set proxy file if provided
            if args.proxy_file:
                abspath_proxy = os.path.abspath(args.proxy_file)
                docker_cmd.extend(["-v", f"{abspath_proxy}:/proxies.txt:ro"])
                
            docker_cmd.append("gosom/google-maps-scraper")
            
            # CLI flags for scraper inside container
            docker_cmd.extend([
                "-input", "/queries.txt",
                "-results", "/out/raw_results.json",
                "-json",
                "-extra-reviews",
                "-depth", str(args.depth),
                "-exit-on-inactivity", args.exit_on_inactivity,
                "-c", str(args.concurrency)
            ])

            if args.pages_per_browser:
                docker_cmd.extend(["-pages-per-browser", str(args.pages_per_browser)])
            if args.browser_pool_size:
                docker_cmd.extend(["-browser-pool-size", str(args.browser_pool_size)])
            if args.proxy:
                docker_cmd.extend(["-proxies", args.proxy])
            elif args.proxy_file:
                docker_cmd.extend(["-proxies-file", "/proxies.txt"])

            print(f"--> Running scrape: '{query_str}'")
            # Execute scraper
            try:
                result = subprocess.run(docker_cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"--> ERROR: Docker scraper run failed for {city}, {country}. Error: {e}")
                # Keep temporary query file for debugging, move to next city
                continue

            # Process and clean output
            if os.path.exists(raw_output):
                print(f"--> Scrape finished. Cleaning results (capping reviews to 10)...")
                try:
                    clean_and_deduplicate_leads(
                        raw_output, 
                        clean_output, 
                        default_city=city, 
                        default_country=country_display, 
                        default_category=args.niche
                    )
                    # Clean up temporary query file on success
                    if os.path.exists(temp_queries_file):
                        os.remove(temp_queries_file)
                    # Clean up raw_results if keep_raw is False
                    if not args.keep_raw and os.path.exists(raw_output):
                        os.remove(raw_output)
                    print(f"--> Success! Cleaned file saved to {clean_output}")

                    if args.enrich_emails:
                        print(f"--> Starting email enrichment from websites...")
                        enrich_file(clean_output, max_workers=args.concurrency * 3)
                except Exception as e:
                    print(f"--> ERROR: Post-processing failed for {city}, {country}. Error: {e}")
            else:
                print(f"--> ERROR: raw_results.json was not generated. The scraper might have been blocked or found no results.")

    print("\n" + "=" * 60)
    print("Orchestration complete!")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
