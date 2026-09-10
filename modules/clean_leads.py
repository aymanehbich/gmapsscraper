import json
import sys


def clean_and_deduplicate_leads(input_file, output_file, default_city=None, default_country=None, default_category=None):
  cleaned_leads = []
  seen_ids = set()

  # Read file line by line (NDJSON format)
  with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
      line = line.strip()
      if not line:
        continue
      try:
        item = json.loads(line)
      except json.JSONDecodeError:
        continue

      # Use placeId or cid as the unique identifier to prevent duplicates
      unique_id = item.get("placeId") or item.get("cid")

      if unique_id:
        if unique_id in seen_ids:
          continue
        seen_ids.add(unique_id)

      # Extract emails if available (scraper stores this in an 'emails' list)
      raw_emails = item.get("emails", []) or []
      emails_list = []
      if isinstance(raw_emails, list):
        for e in raw_emails:
          if isinstance(e, str):
            emails_list.append(e)
          elif isinstance(e, dict) and "email" in e:
            emails_list.append(e["email"])

      # Extract reviews from 'user_reviews'
      raw_reviews = item.get("user_reviews", []) or []
      streamlined_reviews = []
      for rev in raw_reviews[:10]:
        streamlined_reviews.append({
            "author": rev.get("Name"),
            "rating": rev.get("Rating"),
            "text": rev.get("Description"),
            "date": rev.get("When"),
        })

      # Intelligent Fallbacks for Service-Area Businesses
      comp_addr = item.get("complete_address") or {}
      city = comp_addr.get("city") or default_city or ""
      state = comp_addr.get("state") or ""
      postal_code = comp_addr.get("postal_code") or ""
      
      raw_addr = item.get("address")
      if not raw_addr:
        addr_parts = [p for p in [default_city, default_country] if p]
        address = ", ".join(addr_parts) if addr_parts else ""
      else:
        address = raw_addr

      category = item.get("categoryName") or item.get("category") or default_category

      filtered_item = {
          "title": item.get("title"),
          "category": category,
          "phone": item.get("phone"),
          "emails": emails_list,
          "website": item.get("web_site"),
          "address": address,
          "city": city,
          "state": state,
          "postalCode": postal_code,
          "totalScore": item.get("review_rating"),
          "reviewsCount": item.get("review_count"),
          "placeId": item.get("placeId"),
          "cid": item.get("cid"),
          "openingHours": item.get("open_hours") or {},
          "reviews": streamlined_reviews,
      }

      cleaned_leads.append(filtered_item)

  # Save the optimized output
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(cleaned_leads, f, indent=2, ensure_ascii=False)

  print(
      f"Successfully processed {len(cleaned_leads)} unique leads with emails"
      f" & reviews. Saved to {output_file}"
  )


if __name__ == "__main__":
  if len(sys.argv) > 2:
    clean_and_deduplicate_leads(sys.argv[1], sys.argv[2])
  else:
    clean_and_deduplicate_leads("../gmaps-output/results.json", "cleaned_leads.json")