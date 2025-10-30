import os
import json
import requests
from bs4 import BeautifulSoup
import re
import io
import PyPDF2
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("A_GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("A_SEARCH_ENGINE_ID")

def _extract_pdf_text_from_url(url, headers):
    """Download and extract text from a PDF URL."""
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        with io.BytesIO(resp.content) as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            cleaned = re.sub(r'\s+', ' ', text).strip()
            return cleaned[:10000] if cleaned else "Warning: PDF contained no extractable text."
    except Exception as e:
        return f"Error extracting PDF content: {e}"

def specific_agriculture_search(query: str, num_results: int = 5) -> str:
    """Search Google and return results with full page content. The return is a string representation of a JSON object."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'q': query,
        'num': num_results
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        items = data.get('items', [])
        if not items:
            return json.dumps([{'error': 'No results found for the query.'}])

        for i, item in enumerate(items, 1):
            page_content = ""
            page_url = item.get('link')
            if not page_url:
                page_content = "Error: No URL found for this search result."
            elif page_url.lower().endswith('.pdf'):
                page_content = _extract_pdf_text_from_url(page_url, headers)
            else:
                try:
                    page_response = requests.get(page_url, timeout=10, headers=headers)
                    if page_response.status_code == 200:
                        soup = BeautifulSoup(page_response.text, "html.parser")
                        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'menu']):
                            element.decompose()
                        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main', 'article'])
                        if main_content:
                            raw_text = main_content.get_text(separator=" ")
                        else:
                            body = soup.find('body')
                            raw_text = body.get_text(separator=" ") if body else soup.get_text(separator=" ")
                        cleaned_text = re.sub(r'\s+', ' ', raw_text)
                        cleaned_text = re.sub(r'(Log in|Sign up|Subscribe|Cookie|Privacy|Terms)', '', cleaned_text, flags=re.IGNORECASE)
                        cleaned_text = cleaned_text.strip()
                        if len(cleaned_text) > 200:
                            page_content = cleaned_text[200:10200]
                        else:
                            page_content = cleaned_text[:10000]
                        if not page_content.strip():
                            page_content = f"Warning: Page content was empty or too short after cleaning for URL: {page_url}"
                    else:
                        page_content = f"Error: Failed to fetch content from {page_url}. Status code: {page_response.status_code}"
                except requests.exceptions.Timeout:
                    page_content = f"Error: Timeout fetching content from {page_url}."
                except requests.exceptions.RequestException as e:
                    page_content = f"Error: Request error fetching content from {page_url}: {e}"
                except Exception as e:
                    page_content = f"Error: Parsing content from {page_url} failed: {e}"
            results.append({
                'number': i,
                'title': item.get('title', ''),
                'url': page_url,
                'snippet': item.get('snippet', ''),
                'page_content': page_content
            })
        return json.dumps(results)
    except requests.exceptions.RequestException as e:
        return json.dumps([{"number": 1, "title": "Search Error", "url": "", "snippet": f"Could not perform search: {e}", "page_content": f"Error: Could not perform initial search: {e}"}])
    except json.JSONDecodeError as e:
        return json.dumps([{"number": 1, "title": "JSON Error", "url": "", "snippet": f"Could not decode search response: {e}", "page_content": f"Error: Could not decode search response: {e}"}])