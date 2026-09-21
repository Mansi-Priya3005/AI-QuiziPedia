import httpx
import pytest

import web_extractor
from scraper import ScrapeError
from web_extractor import (
    _is_public_ip,
    extract_text_from_html,
    fetch_url_content,
    resolve_source,
)

PUBLIC_IP = "93.184.216.34"

LONG_ARTICLE = "This is a sentence about photosynthesis in plants. " * 20


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Resolve every hostname to a public IP by default so tests never hit
    real DNS. Individual tests override this to simulate private targets."""

    async def fake_resolve(host, port):
        return [PUBLIC_IP]

    monkeypatch.setattr(web_extractor, "_resolve_host", fake_resolve)


def _mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: orig_client(*a, transport=transport, **kw)
    )


# ---------------------------------------------------------------- resolve_source


def test_resolve_google_doc_to_export_url():
    kind, url = resolve_source("https://docs.google.com/document/d/1AbC_dEf-123456/edit?usp=sharing")
    assert kind == "google_doc"
    assert url == "https://docs.google.com/document/d/1AbC_dEf-123456/export?format=txt"


def test_resolve_google_slides_to_export_url():
    kind, url = resolve_source("https://docs.google.com/presentation/d/1AbC_dEf-123456/edit")
    assert kind == "google_slides"
    assert url == "https://docs.google.com/presentation/d/1AbC_dEf-123456/export/txt"


def test_resolve_published_google_doc_is_treated_as_plain_web_page():
    url = "https://docs.google.com/document/d/e/2PACX-1vAbc/pub"
    assert resolve_source(url) == ("web", url)


@pytest.mark.parametrize(
    "url",
    [
        "https://drive.google.com/file/d/1AbC_dEf-123456/view?usp=sharing",
        "https://drive.google.com/open?id=1AbC_dEf-123456",
        "https://drive.google.com/uc?id=1AbC_dEf-123456",
    ],
)
def test_resolve_drive_file_links(url):
    kind, fetch_url = resolve_source(url)
    assert kind == "google_drive"
    assert fetch_url == "https://drive.google.com/uc?export=download&id=1AbC_dEf-123456"


def test_resolve_drive_folder_rejected():
    with pytest.raises(ScrapeError, match="folder"):
        resolve_source("https://drive.google.com/drive/folders/1AbC_dEf-123456")


def test_resolve_google_sheets_rejected():
    with pytest.raises(ScrapeError, match="Sheets"):
        resolve_source("https://docs.google.com/spreadsheets/d/1AbC_dEf-123456/edit")


def test_resolve_ordinary_url_passthrough():
    url = "https://example.com/blog/post"
    assert resolve_source(url) == ("web", url)


# -------------------------------------------------------------------- SSRF guard


@pytest.mark.parametrize(
    "addr,expected",
    [
        ("93.184.216.34", True),
        ("8.8.8.8", True),
        ("127.0.0.1", False),
        ("10.0.0.5", False),
        ("192.168.1.1", False),
        ("172.16.0.1", False),
        ("169.254.169.254", False),  # cloud metadata endpoint
        ("100.64.0.1", False),  # carrier-grade NAT
        ("0.0.0.0", False),
        ("::1", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),  # IPv4-mapped loopback
        ("not-an-ip", False),
    ],
)
def test_is_public_ip(addr, expected):
    assert _is_public_ip(addr) is expected


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://foo.localhost/",
        "http://printer.local/",
        "ftp://example.com/file",
        "http://user:pass@example.com/",
        "http://example.com:6379/",
    ],
)
async def test_blocked_urls_never_reach_the_network(monkeypatch, url):
    def handler(request):
        raise AssertionError("request should have been blocked before being sent")

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ScrapeError):
        await fetch_url_content(url)


async def test_hostname_resolving_to_private_ip_is_blocked(monkeypatch):
    async def private_resolve(host, port):
        return ["10.0.0.7"]

    monkeypatch.setattr(web_extractor, "_resolve_host", private_resolve)
    _mock_transport(monkeypatch, lambda r: pytest.fail("must not be fetched"))

    with pytest.raises(ScrapeError, match="private or internal"):
        await fetch_url_content("https://sneaky.example.com/page")


async def test_any_private_address_among_several_blocks_the_request(monkeypatch):
    async def mixed_resolve(host, port):
        return [PUBLIC_IP, "127.0.0.1"]

    monkeypatch.setattr(web_extractor, "_resolve_host", mixed_resolve)
    _mock_transport(monkeypatch, lambda r: pytest.fail("must not be fetched"))

    with pytest.raises(ScrapeError, match="private or internal"):
        await fetch_url_content("https://mixed.example.com/")


async def test_redirect_to_private_address_is_blocked(monkeypatch):
    """The classic SSRF bypass: a public URL that 302s to an internal one.
    Redirects are followed manually so each hop is re-validated."""

    async def resolve(host, port):
        return ["169.254.169.254"] if host == "169.254.169.254" else [PUBLIC_IP]

    monkeypatch.setattr(web_extractor, "_resolve_host", resolve)

    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        pytest.fail("internal address must never be requested")

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ScrapeError, match="private or internal"):
        await fetch_url_content("https://example.com/redirector")


async def test_too_many_redirects(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.com/loop"})

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ScrapeError, match="too many times"):
        await fetch_url_content("https://example.com/loop")


async def test_safe_redirect_is_followed(monkeypatch):
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=f"<html><head><title>New</title></head><body><p>{LONG_ARTICLE}</p></body></html>".encode(),
        )

    _mock_transport(monkeypatch, handler)
    result = await fetch_url_content("https://example.com/old")
    assert result.title == "New"
    assert "photosynthesis" in result.text


# ----------------------------------------------------------------- HTML extraction


def test_extract_html_prefers_article_and_strips_noise():
    html = f"""
    <html><head><title>Ignored Title</title>
      <meta property="og:title" content="Real Title"></head>
    <body>
      <nav>Home About Contact</nav>
      <script>var tracking = 1;</script>
      <article><h1>Heading</h1><p>{LONG_ARTICLE}</p></article>
      <aside>Related posts you might like</aside>
      <footer>Copyright 2026</footer>
    </body></html>
    """.encode()
    text, title = extract_text_from_html(html)
    assert title == "Real Title"
    assert "photosynthesis" in text
    assert "tracking" not in text
    assert "Home About Contact" not in text
    assert "Related posts" not in text
    assert "Copyright" not in text


def test_extract_html_falls_back_to_body_without_article_tag():
    html = f"<html><head><title>Plain</title></head><body><div>{LONG_ARTICLE}</div></body></html>".encode()
    text, title = extract_text_from_html(html)
    assert title == "Plain"
    assert "photosynthesis" in text


def test_extract_html_keeps_content_wrapped_in_form_tag():
    """Some frameworks wrap the whole page in <form>; it must not be stripped."""
    html = f"<html><body><form><div>{LONG_ARTICLE}</div></form></body></html>".encode()
    text, _ = extract_text_from_html(html)
    assert "photosynthesis" in text


# ---------------------------------------------------------------- fetch_url_content


async def test_fetch_regular_web_page(monkeypatch):
    html = f"<html><head><title>Cell Biology</title></head><body><main>{LONG_ARTICLE}</main></body></html>"
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=html.encode()),
    )
    result = await fetch_url_content("https://example.com/biology")
    assert result.source_type == "web"
    assert result.title == "Cell Biology"
    assert "photosynthesis" in result.text


async def test_fetch_google_doc_uses_export_url_and_first_line_as_title(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        body = "\ufeffOperating Systems Notes\r\nProcesses and threads are the basic units of execution."
        return httpx.Response(200, headers={"content-type": "text/plain; charset=utf-8"}, content=body.encode())

    _mock_transport(monkeypatch, handler)
    result = await fetch_url_content("https://docs.google.com/document/d/1AbC_dEf-123456/edit")

    assert seen["url"] == "https://docs.google.com/document/d/1AbC_dEf-123456/export?format=txt"
    assert result.source_type == "google_doc"
    assert result.title == "Operating Systems Notes"
    assert "Processes and threads" in result.text


async def test_private_google_doc_redirect_to_login_gives_sharing_hint(monkeypatch):
    def handler(request):
        if request.url.host == "docs.google.com":
            return httpx.Response(
                307, headers={"location": "https://accounts.google.com/ServiceLogin?continue=x"}
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>Sign in</html>")

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ScrapeError, match="Anyone with the link"):
        await fetch_url_content("https://docs.google.com/document/d/1AbC_dEf-123456/edit")


async def test_google_doc_returning_html_gives_sharing_hint(monkeypatch):
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>err</html>"),
    )
    with pytest.raises(ScrapeError, match="Anyone with the link"):
        await fetch_url_content("https://docs.google.com/document/d/1AbC_dEf-123456/edit")


async def test_drive_html_response_gives_drive_hint(monkeypatch):
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>warning</html>"),
    )
    with pytest.raises(ScrapeError, match="Drive file"):
        await fetch_url_content("https://drive.google.com/file/d/1AbC_dEf-123456/view")


async def test_fetch_plain_text_file(monkeypatch):
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200, headers={"content-type": "text/plain"}, content=b"Just some study notes about graphs."
        ),
    )
    result = await fetch_url_content("https://example.com/notes/graphs.txt")
    assert result.title == "graphs.txt"
    assert "study notes" in result.text


async def test_fetch_pdf_is_routed_to_pdf_extractor(monkeypatch):
    captured = {}

    def fake_extract(filename, content_type, file_bytes):
        captured["args"] = (filename, content_type, file_bytes)
        return "extracted pdf text"

    monkeypatch.setattr(web_extractor, "extract_text_from_upload", fake_extract)
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200,
            headers={
                "content-type": "application/octet-stream",  # wrong type; magic bytes win
                "content-disposition": 'attachment; filename="Lecture 3.pdf"',
            },
            content=b"%PDF-1.7 fake",
        ),
    )
    result = await fetch_url_content("https://drive.google.com/file/d/1AbC_dEf-123456/view")
    assert captured["args"][1] == "application/pdf"
    assert result.text == "extracted pdf text"
    assert result.title == "Lecture 3.pdf"
    assert result.source_type == "google_drive"


async def test_js_only_page_gives_helpful_error(monkeypatch):
    html = b'<html><head><title>App</title></head><body><div id="root"></div><script src="app.js"></script></body></html>'
    _mock_transport(
        monkeypatch, lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=html)
    )
    with pytest.raises(ScrapeError, match="JavaScript"):
        await fetch_url_content("https://spa.example.com/")


async def test_unsupported_content_type(monkeypatch):
    _mock_transport(
        monkeypatch, lambda r: httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")
    )
    with pytest.raises(ScrapeError, match="Unsupported content type"):
        await fetch_url_content("https://example.com/pic.png")


@pytest.mark.parametrize(
    "status,fragment",
    [(403, "private"), (404, "couldn't be found"), (429, "limiting requests"), (500, "HTTP 500")],
)
async def test_http_errors_map_to_specific_messages(monkeypatch, status, fragment):
    _mock_transport(monkeypatch, lambda r: httpx.Response(status))
    with pytest.raises(ScrapeError, match=fragment):
        await fetch_url_content("https://example.com/x")


async def test_oversized_response_is_rejected(monkeypatch):
    monkeypatch.setattr(web_extractor, "MAX_FILE_SIZE_BYTES", 1000)
    _mock_transport(
        monkeypatch,
        lambda r: httpx.Response(200, headers={"content-type": "text/plain"}, content=b"x" * 5000),
    )
    with pytest.raises(ScrapeError, match="too large"):
        await fetch_url_content("https://example.com/huge.txt")


async def test_timeout_maps_to_friendly_error(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    _mock_transport(monkeypatch, handler)
    with pytest.raises(ScrapeError, match="in time"):
        await fetch_url_content("https://example.com/slow")
