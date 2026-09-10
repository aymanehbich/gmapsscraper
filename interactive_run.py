import os
import sys
import json
import subprocess

def get_config_path(filename):
    config_path = os.path.join("config", filename)
    if os.path.exists(config_path):
        return config_path
    return filename

def load_json(filename):
    filepath = get_config_path(filename)
    if not os.path.exists(filepath):
        print(f"Error: Required file '{filename}' is missing.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def display_grid(items, cols=3):
    # Display items in a clean grid layout
    rows = (len(items) + cols - 1) // cols
    for r in range(rows):
        line = ""
        for c in range(cols):
            idx = r + c * rows
            if idx < len(items):
                item_str = f"[{idx + 1}] {items[idx]}"
                line += f"{item_str:<28}"
        print(line)

def get_choice(prompt, min_val, max_val, default=None):
    while True:
        default_str = f" [Default: {default}]" if default is not None else ""
        val = input(f"{prompt}{default_str}: ").strip()
        if not val and default is not None:
            return default
        try:
            choice = int(val)
            if min_val <= choice <= max_val:
                return choice
            print(f"Please enter a number between {min_val} and {max_val}.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

def interactive_wizard():
    print("=" * 60)
    print("      🎯 Google Maps Scraper Interactive Wizard 🎯")
    print("=" * 60)

    # 1. Load Niches
    niches_data = load_json("niches.json")
    niche_list = sorted(list(niches_data.keys()))
    
    print("\nSelect a Niche to scrape:")
    display_grid(niche_list, cols=3)
    niche_idx = get_choice("Select option (1-37)", 1, len(niche_list)) - 1
    selected_niche = niche_list[niche_idx]
    print(f"--> Selected Niche: {selected_niche}")

    # 2. Load Targets
    targets_data = load_json("targets.json")
    countries = sorted(list(targets_data.keys()))

    print("\nSelect target location mode:")
    print("[1] Scrape ALL cities in target list")
    print("[2] Select a specific city from target countries")
    print("[3] Type a custom city search query")
    
    loc_mode = get_choice("Choose mode (1-3)", 1, 3, default=1)
    
    selected_city = None
    
    if loc_mode == 2:
        print("\nSelect a Country:")
        for idx, country in enumerate(countries):
            print(f"[{idx + 1}] {country}")
        country_idx = get_choice("Select country", 1, len(countries)) - 1
        selected_country = countries[country_idx]
        
        cities = targets_data[selected_country]["cities"]
        print(f"\nSelect a City in {selected_country}:")
        for idx, city in enumerate(cities):
            print(f"[{idx + 1}] {city}")
        city_idx = get_choice("Select city", 1, len(cities)) - 1
        selected_city = cities[city_idx]
        print(f"--> Selected Target: {selected_city} ({selected_country})")
        
    elif loc_mode == 3:
        selected_city = input("\nEnter the custom city/region search query (e.g. 'Austin TX' or 'Lyon, France'): ").strip()
        while not selected_city:
            selected_city = input("City cannot be empty. Please enter a city search query: ").strip()
        print(f"--> Custom Target: {selected_city}")

    # 3. Customize Advanced Options?
    print("\nWould you like to customize advanced scraper settings?")
    print("[1] No, use default settings (Recommended)")
    print("[2] Yes, customize settings (concurrency, depth, proxies, etc.)")
    customize = get_choice("Choose option (1-2)", 1, 2, default=1)

    depth = 30
    concurrency = 4
    timeout = "5m"
    proxy_url = None
    proxy_file = None
    keep_raw = False

    if customize == 2:
        print("\n--- Advanced Settings ---")
        
        # Depth
        while True:
            val = input("Scroll depth (default 30, lower is faster): ").strip()
            if not val:
                break
            try:
                depth = int(val)
                break
            except ValueError:
                print("Please enter a valid integer.")
                
        # Concurrency
        while True:
            val = input("Concurrency level -c (default 4): ").strip()
            if not val:
                break
            try:
                concurrency = int(val)
                break
            except ValueError:
                print("Please enter a valid integer.")

        # Timeout
        val = input("Exit on inactivity timeout (default 5m): ").strip()
        if val:
            timeout = val

        # Proxies
        has_proxies_file = os.path.exists("proxies.txt") or os.path.exists("config/proxies.txt")
        default_p_mode = 3 if has_proxies_file else 1
        print("\nConfigure Proxies (Optional):")
        print("[1] No proxies")
        print("[2] Single proxy URL")
        print(f"[3] Proxy file list {'(proxies.txt detected)' if has_proxies_file else ''}")
        proxy_mode = get_choice("Choose proxy mode (1-3)", 1, 3, default=default_p_mode)
        
        if proxy_mode == 2:
            proxy_url = input("Enter proxy URL (e.g. http://user:pass@host:port): ").strip()
        elif proxy_mode == 3:
            default_p_path = "proxies.txt" if os.path.exists("proxies.txt") else "config/proxies.txt" if os.path.exists("config/proxies.txt") else ""
            prompt_str = f"Enter path to proxy file (default: {default_p_path}): " if default_p_path else "Enter path to proxy file (e.g. proxies.txt): "
            proxy_file = input(prompt_str).strip() or default_p_path
            while not os.path.exists(proxy_file):
                print(f"Error: File not found at '{proxy_file}'")
                proxy_file = input("Enter path to proxy file (or press Enter to cancel): ").strip()
                if not proxy_file:
                    proxy_file = None
                    break
        
        # Keep raw
        val = input("\nKeep raw_results.json files after cleaning? (y/n, default n): ").strip().lower()
        keep_raw = val == 'y'

    # Auto Enrich Emails option
    val = input("\nAutomatically fetch contact emails from business websites after scrape? (y/n, default y): ").strip().lower()
    enrich_emails = val != 'n'

    # Build command
    cmd = ["py", "run_scraper.py", "--niche", selected_niche]
    if selected_city:
        cmd.extend(["--city", selected_city])
    if depth != 30:
        cmd.extend(["--depth", str(depth)])
    if concurrency != 4:
        cmd.extend(["--concurrency", str(concurrency)])
    if timeout != "5m":
        cmd.extend(["--exit-on-inactivity", timeout])
    if proxy_url:
        cmd.extend(["--proxy", proxy_url])
    elif proxy_file:
        cmd.extend(["--proxy-file", proxy_file])
    if keep_raw:
        cmd.append("--keep-raw")
    if enrich_emails:
        cmd.append("--enrich-emails")

    cmd_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in cmd])

    print("\n" + "=" * 60)
    print("                  Ready to Start Scrape")
    print("=" * 60)
    print(f"Niche:         {selected_niche}")
    print(f"Target:        {selected_city if selected_city else 'ALL CITIES'}")
    print(f"Depth:         {depth}")
    print(f"Concurrency:   {concurrency}")
    print(f"Timeout:       {timeout}")
    print(f"Proxies:       {proxy_url if proxy_url else (proxy_file if proxy_file else 'None')}")
    print(f"Keep Raw Logs: {keep_raw}")
    print("-" * 60)
    print(f"Generated Command:\n  {cmd_str}")
    print("=" * 60)

    confirm = input("Launch scraper now? (y/n, default y): ").strip().lower()
    if confirm == 'n':
        print("Cancelled. You can run the scraper manually using the command above.")
        return

    print("\nLaunching scraper orchestrator...\n")
    try:
        # Run orchestrator
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"\nFailed to execute orchestrator: {e}")

if __name__ == "__main__":
    try:
        interactive_wizard()
    except KeyboardInterrupt:
        print("\nWizard cancelled.")
