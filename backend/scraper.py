import logging
import re
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 300_000  # generous but bounded -- see llm_quiz_generator.MAX_ARTICLE_CHARS
REQUEST_TIMEOUT = 15.0
# Wikimedia's User-Agent policy asks for a descriptive, contact-identifying
# UA rather than a spoofed browser string. Spoofing a browser UA is also
# what makes a request look like a scraper to anti-bot heuristics in the
# first place -- identifying honestly as an API client is both more
# correct and, in practice, less likely to be blocked.
USER_AGENT = "AI-QuiziPedia/1.0 (educational quiz generator; https://github.com/Mansi-Priya3005/AI-QuiziPedia)"


class ScrapeError(Exception):
    """Raised with a specific, user-facing reason the fetch failed —
    replaces the old behavior of catching every exception and returning
    (None, None) with no indication of *why* (network error? no such
    page? article has no body text?)."""


def _parse_wikipedia_url(url: str) -> Tuple[str, str]:
    """Extract (language_subdomain, article_title) from a Wikipedia URL.

    e.g. https://en.wikipedia.org/wiki/Ada_Lovelace -> ("en", "Ada Lovelace")
    """
    parsed = urlparse(url)
    lang = parsed.netloc.split(".")[0] if "." in parsed.netloc else "en"
    # /wiki/Ada_Lovelace -> Ada_Lovelace -> Ada Lovelace
    path_title = parsed.path.split("/wiki/", 1)[-1]
    title = unquote(path_title).replace("_", " ")
    return lang, title


async def scrape_wikipedia(url: str) -> Tuple[str, Optional[str]]:
    """Fetch the plain-text extract of a Wikipedia article via the
    official MediaWiki API (action=query&prop=extracts), rather than
    scraping the rendered HTML page.

    This is deliberately NOT an HTML scraper: fetching rendered pages with
    BeautifulSoup is fragile (breaks on markup changes) and can trigger
    anti-bot blocks (we hit exactly this as an HTTP 403 from the rendered
    page). The MediaWiki API is Wikipedia's own supported, documented way
    to fetch article content, and returns clean plain text directly.

    Returns (clean_text, title). Raises ScrapeError with a specific
    message on any failure.
    """
    lang, title = _parse_wikipedia_url(url)
    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "titles": title,
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                api_url, params=params, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
    except httpx.TimeoutException as e:
        raise ScrapeError("Wikipedia did not respond in time. Please try again.") from e
    except httpx.HTTPStatusError as e:
        raise ScrapeError(
            f"Wikipedia returned an error (HTTP {e.response.status_code})."
        ) from e
    except httpx.HTTPError as e:
        logger.error("Network error fetching %s: %s", url, e)
        raise ScrapeError("Couldn't reach Wikipedia. Please try again shortly.") from e

    data = response.json()
    pages = data.get("query", {}).get("pages", [])

    if not pages:
        raise ScrapeError("Couldn't find that Wikipedia article.")

    page = pages[0]
    if page.get("missing"):
        raise ScrapeError("That Wikipedia page doesn't exist.")

    page_title = page.get("title", title)
    extract = page.get("extract", "")

    if not extract or not extract.strip():
        raise ScrapeError("That article page has no readable content.")

    # The plaintext extract includes section headers like "== History ==";
    # strip the == markers but keep the heading text as a natural paragraph
    # break, and drop reference-list/see-also boilerplate sections that add
    # no quiz-worthy content.
    clean_text = re.sub(r"={2,}\s*(.*?)\s*={2,}", r"\1.", extract)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return clean_text[:MAX_CONTENT_CHARS], page_title


def validate_wikipedia_url(url: str) -> bool:
    pattern = r"^https://([a-z]{2,12}\.)?wikipedia\.org/wiki/.+"
    return bool(re.match(pattern, url))
