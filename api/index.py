# This agent runs inside GitHub Actions - analyzing the TOP 10 English results.

import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from supabase import create_client, Client
import time

# --- 1. CONFIGURATION ---
# Reads secrets from the GitHub Actions environment
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

SEARCH_KEYWORDS = ["bKash Betting Sites"]

# --- 2. CORE FUNCTIONS ---
def get_search_results_with_serpapi(keyword):
    print(f"Searching for keyword: {keyword}")
    # We can go back to searching for 10 results now!
    params = {"api_key": SERPAPI_KEY, "engine": "google", "q": keyword, "num": "10"}
    response = requests.get("https://serpapi.com/search.json", params=params)
    if response.status_code == 200:
        results = response.json().get('organic_results', [])
        sites = [{'url': r.get('link'), 'title': r.get('title')} for r in results]
        print(f"  -> Found {len(sites)} links.")
        return sites
    else:
        print(f"  -> Error from SerpApi: {response.text}")
        return []

def analyze_url_content_with_scraperapi(url):
    for attempt in range(3):
        try:
            print(f"Analyzing URL (Attempt {attempt + 1}/3): {url}")
            params = {'api_key': SCRAPER_API_KEY, 'url': url, 'render': 'true'}
            response = requests.get('http://api.scraperapi.com', params=params, timeout=45)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = ' '.join(soup.stripped_strings)[:8000]
            if not page_text:
                return {"is_relevant": False, "analysis": "Could not extract text."}
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"Analyze the following text. Is this website promoting or listing online betting/gambling sites that claim to use 'bKash'? Answer only with \"Yes\" or \"No\", followed by a new line and a one-sentence summary. Format: Relevant: [Yes/No]\nAnalysis: [Summary]"
            ai_response = model.generate_content(prompt)
            lines = ai_response.text.strip().split('\n')
            is_relevant = "yes" in lines[0].lower()
            analysis = lines[1].replace("Analysis: ", "").strip()
            print(f"  -> Gemini Analysis Successful. Relevant: {is_relevant}")
            return {"is_relevant": is_relevant, "analysis": analysis}
        except Exception as e:
            print(f"  -> Attempt {attempt + 1} failed: {e}")
            if attempt < 2: time.sleep(3)
            else: return {"is_relevant": False, "analysis": f"Failed after 3 retries: {str(e)}"}
    return {"is_relevant": False, "analysis": "Analysis failed."}

def run_agent():
    print("--- Starting AI Agent Run (ENGLISH ONLY via GitHub Actions) ---")
    all_sites = []
    for keyword in SEARCH_KEYWORDS:
        sites = get_search_results_with_serpapi(keyword)
        for site in sites:
            site['source_keyword'] = keyword
        all_sites.extend(sites)
    for site in all_sites:
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
        
        analysis_result = analyze_url_content_with_scraperapi(url)
        
        if analysis_result['is_relevant']:
            print(f"  -> RELEVANT SITE FOUND! Saving...")
            data_to_insert = { 'url': url, 'title': site.get('title'), 'source_keyword': site.get('source_keyword'), 'is_relevant': analysis_result['is_relevant'], 'gemini_analysis': analysis_result['analysis'] }
            try:
                supabase.table('suspicious_sites').insert(data_to_insert).execute()
                print(f"  -> Successfully saved to Supabase.\n")
            except Exception as e:
                print(f"  -> Failed to insert into Supabase: {e}\n")
        else:
            print(f"  -> Site not relevant. Skipping.\n")
            
    print("--- AI Agent Run Finished ---")

# This line makes the script run when called directly
if __name__ == "__main__":
    run_agent()
