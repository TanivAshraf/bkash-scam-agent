# ULTIMATE VERSION: This agent uses a multi-tool "waterfall" fallback system.

import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from supabase import create_client, Client
import time
import json

# --- 1. CONFIGURATION ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')
SCRAPINGBEE_API_KEY = os.environ.get('SCRAPINGBEE_API_KEY') # New Key

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

SEARCH_KEYWORDS = ["বিকাশ বেটিং সাইট"]

# --- 2. MULTI-TOOL "WATERFALL" FUNCTIONS ---

# --- Search Tools ---
def search_with_serpapi(keyword):
    print("  -> Trying Search Tool: SerpApi...")
    params = {"api_key": SERPAPI_KEY, "engine": "google", "q": keyword, "num": "10"}
    response = requests.get("https://serpapi.com/search.json", params=params)
    if response.status_code == 200 and response.json().get('organic_results'):
        results = response.json()['organic_results']
        sites = [{'url': r.get('link'), 'title': r.get('title')} for r in results]
        print(f"  -> SerpApi SUCCESS: Found {len(sites)} links.")
        return sites
    return None

def search_with_scrapingbee(keyword):
    print("  -> Trying Search Tool: ScrapingBee...")
    params = {'api_key': SCRAPINGBEE_API_KEY, 'url': f"https://www.google.com/search?q={keyword}", 'search_config': 'json_results'}
    response = requests.get('https://app.scrapingbee.com/api/v1/', params=params)
    if response.status_code == 200 and response.json().get('organic_results'):
        results = response.json()['organic_results']
        sites = [{'url': r.get('url'), 'title': r.get('title')} for r in results]
        print(f"  -> ScrapingBee SUCCESS: Found {len(sites)} links.")
        return sites
    return None

def get_search_results(keyword):
    """Tries multiple search tools until one succeeds."""
    print(f"Searching for keyword: {keyword}")
    search_tools = [search_with_serpapi, search_with_scrapingbee]
    for tool in search_tools:
        results = tool(keyword)
        if results:
            return results
    print("  -> All search tools failed.")
    return []

# --- Scraper Tools ---
def scrape_with_scraperapi(url):
    print(f"  -> Trying Scraper: ScraperAPI...")
    params = {'api_key': SCRAPER_API_KEY, 'url': url, 'render': 'true'}
    response = requests.get('http://api.scraperapi.com', params=params, timeout=45)
    response.raise_for_status()
    return response.content

def scrape_with_scrapingbee(url):
    print(f"  -> Trying Scraper: ScrapingBee...")
    params = {'api_key': SCRAPINGBEE_API_KEY, 'url': url, 'render_js': 'true'}
    response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
    response.raise_for_status()
    return response.content

def scrape_with_direct_request(url):
    print(f"  -> Trying Scraper: Direct Request...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.content

def analyze_url_content(url):
    """Tries multiple scrapers to get page content, then analyzes it."""
    content = None
    scraper_tools = [scrape_with_scraperapi, scrape_with_scrapingbee, scrape_with_direct_request]
    
    print(f"Analyzing URL: {url}")
    for tool in scraper_tools:
        try:
            content = tool(url)
            if content:
                print("  -> Scrape SUCCESS.")
                break # Stop trying once we have content
        except Exception as e:
            print(f"  -> Scraper failed: {e}")
            
    if not content:
        return {"is_relevant": False, "analysis": "All scraping attempts failed."}

    try:
        soup = BeautifulSoup(content, 'html.parser')
        page_text = ' '.join(soup.stripped_strings)[:8000]
        if not page_text:
            return {"is_relevant": False, "analysis": "Could not extract text."}

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Analyze text. Is this website promoting online betting/gambling using 'bKash'? Format: Relevant: [Yes/No]\nAnalysis: [Summary]"
        ai_response = model.generate_content(prompt)
        lines = ai_response.text.strip().split('\n')
        is_relevant = "yes" in lines[0].lower()
        analysis = lines[1].replace("Analysis: ", "").strip()
        print(f"  -> Gemini Analysis Successful. Relevant: {is_relevant}")
        return {"is_relevant": is_relevant, "analysis": analysis}
    except Exception as e:
        return {"is_relevant": False, "analysis": f"AI analysis failed: {str(e)}"}

# --- 3. MAIN AGENT LOGIC ---
def run_agent():
    print("--- Starting AI Agent Run (ENGLISH ONLY via GitHub Actions) ---")
    for keyword in SEARCH_KEYWORDS:
        sites = get_search_results(keyword)
        for site in sites:
            url = site.get('url')
            if not url or not url.startswith('http'): continue
            try:
                result = supabase.table('suspicious_sites').select('id', count='exact').eq('url', url).execute()
                if result.count > 0:
                    print(f"Skipping already recorded URL: {url}")
                    continue
            except Exception as e:
                print(f"Error checking Supabase: {e}")
                continue
            
            analysis_result = analyze_url_content(url)
            
            if analysis_result['is_relevant']:
                print(f"  -> RELEVANT SITE FOUND! Saving...")
                data_to_insert = { 'url': url, 'title': site.get('title'), 'source_keyword': keyword, 'is_relevant': analysis_result['is_relevant'], 'gemini_analysis': analysis_result['analysis'] }
                try:
                    supabase.table('suspicious_sites').insert(data_to_insert).execute()
                    print(f"  -> Successfully saved to Supabase.\n")
                except Exception as e:
                    print(f"  -> Failed to insert into Supabase: {e}\n")
            else:
                print(f"  -> Site not relevant. Skipping.\n")
                
    print("--- AI Agent Run Finished ---")

if __name__ == "__main__":
    run_agent()
