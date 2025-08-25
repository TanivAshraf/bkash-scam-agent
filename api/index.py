import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from supabase import create_client, Client
import time
from http.server import BaseHTTPRequestHandler

# --- 1. CONFIGURATION ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SEARCH_KEYWORDS = ["bKash Betting Sites", "বিকাশ বেটিং সাইট"]

# --- 2. CORE FUNCTIONS ---

def get_search_results_with_serpapi(keyword):
    print(f"Searching for keyword with SerpApi: {keyword}")
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
                return {"is_relevant": False, "analysis": "Could not extract text from the page."}
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"Analyze the following text from a website. The goal is to determine if this website is promoting or listing online betting/gambling sites that claim to use 'bKash'. Website Text: \"{page_text}\" Based on the text, answer two questions: 1. Is this website directly promoting or listing betting/gambling sites related to bKash? Answer only with \"Yes\" or \"No\". 2. Provide a one-sentence summary explaining your reasoning. Format your response as: Relevant: [Yes/No]\nAnalysis: [Your one-sentence summary]"
            ai_response = model.generate_content(prompt)
            lines = ai_response.text.strip().split('\n')
            is_relevant = "yes" in lines[0].lower()
            analysis = lines[1].replace("Analysis: ", "").strip()
            print(f"  -> Gemini Analysis Successful. Relevant: {is_relevant}")
            return {"is_relevant": is_relevant, "analysis": analysis}
        except requests.exceptions.RequestException as e:
            print(f"  -> Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(3)
            else:
                return {"is_relevant": False, "analysis": f"Failed after 3 retries: {str(e)}"}
    return {"is_relevant": False, "analysis": "Analysis failed after all retries."}

def run_agent():
    print("--- Starting AI Agent Run (Smart Filtering Version) ---")
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
        
        # --- THIS IS THE UPGRADE ---
        # Only save to the database IF the site is relevant.
        if analysis_result['is_relevant']:
            print(f"  -> RELEVANT SITE FOUND! Saving to database...")
            data_to_insert = {
                'url': url,
                'title': site.get('title'),
                'source_keyword': site.get('source_keyword'),
                'is_relevant': analysis_result['is_relevant'],
                'gemini_analysis': analysis_result['analysis']
            }
            try:
                supabase.table('suspicious_sites').insert(data_to_insert).execute()
                print(f"  -> Successfully saved analysis for {url} to Supabase.\n")
            except Exception as e:
                print(f"  -> Failed to insert data into Supabase: {e}\n")
        else:
            # If not relevant, just log it and move on.
            print(f"  -> Site is not relevant. Skipping database insert.\n")
            
    print("--- AI Agent Run Finished ---")

# Vercel Handler
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        run_agent()
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write('Agent run completed.'.encode('utf-8'))
        return
