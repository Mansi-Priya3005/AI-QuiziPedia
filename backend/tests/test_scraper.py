import httpx
import pytest

from scraper import ScrapeError, scrape_wikipedia, validate_wikipedia_url


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


FAKE_ARTICLE_HTML = """
<html><body>
<h1 class="firstHeading">Ada Lovelace</h1>
<div id="mw-content-text"><div class="mw-parser-output">
<p>Ada Lovelace was an English mathematician.<sup>[1]</sup></p>
<table><tr><td>junk table data</td></tr></table>
<p>She worked on Charles Babbage's Analytical Engine.</p>
</div></div>
</body></html>
"""


@pytest.mark.asyncio
async def test_scrape_wikipedia_extracts_clean_text(monkeypatch):
    def handler(request):
        return httpx.Response(200, content=FAKE_ARTICLE_HTML.encode())

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    text, title = await scrape_wikipedia("https://en.wikipedia.org/wiki/Ada_Lovelace")
    assert title == "Ada Lovelace"
    assert "junk table data" not in text
    assert "[1]" not in text
    assert "Ada Lovelace was an English mathematician" in text


@pytest.mark.asyncio
async def test_scrape_wikipedia_404_raises_specific_error(monkeypatch):
    def handler(request):
        return httpx.Response(404, content=b"not found")

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    with pytest.raises(ScrapeError, match="doesn't exist"):
        await scrape_wikipedia("https://en.wikipedia.org/wiki/Nonexistent")


@pytest.mark.asyncio
async def test_scrape_wikipedia_no_content_raises(monkeypatch):
    def handler(request):
        return httpx.Response(
            200, content=b'<html><body><h1 class="firstHeading">X</h1></body></html>'
        )

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )

    with pytest.raises(ScrapeError):
        await scrape_wikipedia("https://en.wikipedia.org/wiki/Empty")
