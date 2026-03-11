import os
import time
import random
from serpapi import GoogleSearch

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")


def scrape_google(keyword, target_domain):
    """
    Use SerpAPI to search google.fr for a keyword and find target_domain's position.
    Returns: (position, url_found) or (None, None) if not found in top 100.
    """
    params = {
        "engine": "google",
        "q": keyword,
        "google_domain": "google.fr",
        "gl": "fr",
        "hl": "fr",
        "num": 100,
        "api_key": SERPAPI_KEY,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        organic = results.get("organic_results", [])
        clean_target = target_domain.lower().replace("www.", "")

        for item in organic:
            link = item.get("link", "")
            position = item.get("position", 0)
            domain = item.get("displayed_link", "").lower().replace("www.", "")

            # Check if target domain is in the result URL or displayed link
            if clean_target in link.lower() or clean_target in domain:
                return (position, link)

        return (None, None)

    except Exception as e:
        print(f"SerpAPI error for '{keyword}': {e}")
        return (None, None)


def check_keyword(keyword, target_domain, retry=True):
    """
    Check a single keyword with retry logic.
    Returns: (position, url_found)
    """
    try:
        return scrape_google(keyword, target_domain)
    except Exception as e:
        if retry:
            time.sleep(5)
            return check_keyword(keyword, target_domain, retry=False)
        print(f"Failed for '{keyword}': {e}")
        return (None, None)


def delay_between_keywords():
    """Short delay between SerpAPI calls (no need for 5min with API)."""
    time.sleep(random.uniform(2, 5))
