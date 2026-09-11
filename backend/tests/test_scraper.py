import json

import httpx
import pytest

from scraper import ScrapeError, _parse_wikipedia_url, scrape_wikipedia, validate_wikipedia_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://en.wikipedia.org/wiki/Ada_Lovelace", True),
        ("https://simple.wikipedia.org/wiki/Cat", True),
        ("http://en.wikipedia.org/wiki/Cat", False),  # not https
        ("https://evil.com/wikipedia.org/wiki/x", False),
        ("https://en.wikipedia.org/", False),  # no article
        ("not a url at all", False),
    ],
)
def test_validate_wikipedia_url(url, expected):
    assert validate_wikipedia_url(url) is expected


def test_parse_wikipedia_url_extracts_lang_and_title():
    lang, title = _parse_wikipedia_url("https://en.wikipedia.org/wiki/Ada_Lovelace")
    assert lang == "en"
    assert title == "Ada Lovelace"


def test_parse_wikipedia_url_handles_simple_subdomain():
    lang, title = _parse_wikipedia_url("https://simple.wikipedia.org/wiki/Cat")
    assert lang == "simple"
    assert title == "Cat"


def _mock_api_response(pages):
    def handler(request):
        return httpx.Response(200, content=json.dumps({"query": {"pages": pages}}).encode())

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_scrape_wikipedia_extracts_clean_text(monkeypatch):
    transport = _mock_api_response(
        [
            {
                "title": "Ada Lovelace",
                "extract": "== Early life ==\nAda Lovelace was an English mathematician.\n\n== Work ==\nShe worked on Charles Babbage's Analytical Engine.",
            }
        ]
    )
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    text, title = await scrape_wikipedia("https://en.wikipedia.org/wiki/Ada_Lovelace")
    assert title == "Ada Lovelace"
    assert "Ada Lovelace was an English mathematician" in text
    assert "Charles Babbage's Analytical Engine" in text
    assert "==" not in text  # section header markers stripped


@pytest.mark.asyncio
async def test_scrape_wikipedia_missing_page_raises(monkeypatch):
    transport = _mock_api_response(
        [{"title": "Nonexistent Article Xyz", "missing": True}]
    )
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    with pytest.raises(ScrapeError, match="doesn't exist"):
        await scrape_wikipedia("https://en.wikipedia.org/wiki/Nonexistent_Article_Xyz")


@pytest.mark.asyncio
async def test_scrape_wikipedia_empty_extract_raises(monkeypatch):
    transport = _mock_api_response([{"title": "Empty Page", "extract": ""}])
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    with pytest.raises(ScrapeError, match="no readable content"):
        await scrape_wikipedia("https://en.wikipedia.org/wiki/Empty_Page")


@pytest.mark.asyncio
async def test_scrape_wikipedia_http_error_raises(monkeypatch):
    def handler(request):
        return httpx.Response(403, content=b"blocked")

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    with pytest.raises(ScrapeError, match="HTTP 403"):
        await scrape_wikipedia("https://en.wikipedia.org/wiki/Something")
