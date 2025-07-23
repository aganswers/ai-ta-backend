import os
import json
import requests
from openai import OpenAI
from bs4 import BeautifulSoup
import re
import io
import PyPDF2
from typing import Iterator, List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("A_OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("A_GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("A_SEARCH_ENGINE_ID")


class LLMSearchService:
    def __init__(self, openai_api_key: str = None):
        self.client = OpenAI(api_key=openai_api_key or OPENAI_API_KEY)
    
    def stream_response(self, question: str, chat_history: Optional[List[Dict]] = None) -> Iterator[str]:
        """Stream response tokens from the LLM with web search capabilities."""
        tools = [{
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "num_results": {"type": "integer", "description": "Number of results to return", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        }]
        
        system_prompt = """You are AgAnswers, a helpful agricultural and farming assistant with access to web search. Use the search_web tool to find current information when needed. Always cite your sources using [1], [2], etc. based on the search results. You only need in-text citations. Do not list references at the end."""
        
        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": question})
        
        assistant_message = {"role": "assistant", "content": "", "tool_calls": []}
        
        response_stream = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto", 
            temperature=0.25,
            stream=True
        )
        
        for chunk in response_stream:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                assistant_message["content"] += delta.content
                yield delta.content
            
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tool_call_chunk in delta.tool_calls:
                    index = tool_call_chunk.index
                    
                    if len(assistant_message["tool_calls"]) <= index:
                        assistant_message["tool_calls"].append({
                            "id": "",
                            "function": {"arguments": "", "name": None},
                            "type": "function"
                        })
                    
                    if tool_call_chunk.id:
                        assistant_message["tool_calls"][index]["id"] = tool_call_chunk.id
                    if tool_call_chunk.function.name:
                        assistant_message["tool_calls"][index]["function"]["name"] = tool_call_chunk.function.name
                    if tool_call_chunk.function.arguments:
                        assistant_message["tool_calls"][index]["function"]["arguments"] += tool_call_chunk.function.arguments
        
        messages.append(assistant_message)
        
        if assistant_message["tool_calls"]:
            for tool_call in assistant_message["tool_calls"]:
                if tool_call["function"]["name"] == "search_web":
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        query = args.get("query")
                        num_results = args.get("num_results", 5)
                        
                        search_results = self._search_web(query, num_results)
                        formatted_results = [
                            {
                                "number": result['number'],
                                "title": result['title'],
                                "url": result['url'],
                                "snippet": result['snippet'],
                                "page_content": result.get('page_content', '')
                            }
                            for result in search_results
                        ]
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(formatted_results)
                        })
                    except json.JSONDecodeError:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps({"error": "Failed to parse tool arguments."})
                        })
            
            final_stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
            )
            
            for chunk in final_stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    yield delta.content

    def _extract_pdf_text_from_url(self, url, headers):
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

    def _search_web(self, query, num_results=5):
        """Search Google and return results with full page content."""
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
            for i, item in enumerate(data.get('items', []), 1):
                page_content = ""
                page_url = item.get('link')
                if not page_url:
                    page_content = "Error: No URL found for this search result."
                elif page_url.lower().endswith('.pdf'):
                    page_content = self._extract_pdf_text_from_url(page_url, headers)
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
            return results
        except requests.exceptions.RequestException as e:
            return [{"number": 1, "title": "Search Error", "url": "", "snippet": f"Could not perform search: {e}", "page_content": f"Error: Could not perform initial search: {e}"}]
        except json.JSONDecodeError as e:
            return [{"number": 1, "title": "JSON Error", "url": "", "snippet": f"Could not decode search response: {e}", "page_content": f"Error: Could not decode search response: {e}"}]

# Backward compatibility wrapper
def ask_with_tools(question, chat_history=None):
    """Ask GPT a question with web search tool and optional chat history."""
    service = LLMSearchService()
    answer = ""
    for token in service.stream_response(question, chat_history):
        answer += token
    return answer, chat_history or []