import logging
import re
from typing import Optional, Tuple

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 12000
REQUEST_TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/117.0.0.0 Safari/537.36"
)


class ScrapeError(Exception):
    """Raised with a specific, user-facing reason the scrape failed —
    replaces the old behavior of catching every exception and returning
    (None, None) with no indication of *why* (network error? no such
    page? article has no body text?)."""


async def scrape_wikipedia(url: str) -> Tuple[str, Optional[str]]:
    """Fetch and extract the main body text of a Wikipedia article.

    Returns (clean_text, title). Raises ScrapeError with a specific
    message on any failure — network, HTTP status, or "page has no
    extractable content" — instead of silently returning (None, None).
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
    except httpx.TimeoutException as e:
        raise ScrapeError("Wikipedia did not respond in time. Please try again.") from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ScrapeError("That Wikipedia page doesn't exist.") from e
        raise ScrapeError(
            f"Wikipedia returned an error (HTTP {e.response.status_code})."
        ) from e
    except httpx.HTTPError as e:
        logger.error("Network error scraping %s: %s", url, e)
        raise ScrapeError("Couldn't reach Wikipedia. Please try again shortly.") from e

    soup = BeautifulSoup(response.content, "html.parser")

    title_tag = soup.find("h1", {"class": "firstHeading"})
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    content_div = soup.find("div", {"id": "mw-content-text"})
    if not content_div:
        raise ScrapeError("Couldn't find article content on that page.")

    main_content = content_div.find("div", {"class": "mw-parser-output"}) or content_div

    for tag in main_content.find_all(["sup", "table", "style", "script", "figure", "span"]):
        tag.decompose()

    paragraphs = main_content.find_all("p", recursive=True)
    if not paragraphs:
        raise ScrapeError("That article page has no readable paragraph content.")

    clean_text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    clean_text = re.sub(r"\[\d+\]", "", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if not clean_text:
        raise ScrapeError("That article page has no readable paragraph content.")

    return clean_text[:MAX_CONTENT_CHARS], title


def validate_wikipedia_url(url: str) -> bool:
    pattern = r"^https://([a-z]{2,12}\.)?wikipedia\.org/wiki/.+"
    return bool(re.match(pattern, url))
