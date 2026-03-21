import requests
from bs4 import BeautifulSoup
import re
from typing import Tuple, Optional

def scrape_wikipedia(url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/117.0.0.0 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        title_tag = soup.find('h1', {'class': 'firstHeading'})
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        content_div = soup.find('div', {'id': 'mw-content-text'})
        if not content_div:
            return None, title

        main_content = content_div.find('div', {'class': 'mw-parser-output'}) or content_div

        for tag in main_content.find_all(['sup', 'table', 'style', 'script', 'figure', 'span']):
            tag.decompose()

        paragraphs = main_content.find_all('p', recursive=True)

        if not paragraphs:
            return None, title

        clean_text = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        clean_text = re.sub(r'\[\d+\]', '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        if not clean_text:
            return None, title

        return clean_text[:10000], title

    except Exception as e:
        return None, None


def validate_wikipedia_url(url: str) -> bool:
    pattern = r'^https://([a-z]{2,3}\.)?wikipedia\.org/wiki/.+'
    return bool(re.match(pattern, url))
