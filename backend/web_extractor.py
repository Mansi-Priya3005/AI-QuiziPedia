"""Fetch quiz-source text from an arbitrary user-supplied link.

Supported sources (everything except Wikipedia, which keeps its dedicated
MediaWiki-API path in scraper.py):

  * Regular web pages (HTML articles, blog posts, docs sites, ...)
  * Google Docs and Google Slides links (via their public text export)
  * Google Drive file links (PDF / plain-text files)
  * Direct links to a PDF or plain-text file anywhere on the web

Google content only works when its sharing setting is "Anyone with the
link" -- the server has no access to the user's Google account, so a
private document just redirects to a login page, which we detect and turn
into a clear, actionable error.

SECURITY: this endpoint makes the *server* fetch a URL chosen by a user,
which is a classic SSRF (server-side request forgery) vector -- e.g. a
user pasting http://169.254.169.254/ (cloud metadata) or
http://localhost:5432/ to make the server talk to its own internal
network. Every hop of the request (including redirects, which are
followed manually for exactly this reason) is checked to resolve only to
public IP addresses before any connection is made.
"""

import asyncio
import ipaddress
import logging
import re
import socket
from typing import List, NamedTuple, Optional, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from document_extractor import (
    MAX_CONTENT_CHARS,
    MAX_FILE_SIZE_BYTES,
    DocumentExtractionError,
    _sanitize_extracted_text,
    extract_text_from_upload,
)
from scraper import USER_AGENT, ScrapeError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20.0
MAX_REDIRECTS = 5
# A page with less readable text than this almost always means the real
# content is rendered by JavaScript (a single-page app) or sits behind a
# login/paywall, neither of which a plain HTTP fetch can see.
MIN_HTML_CONTENT_CHARS = 200
# Only standard web ports -- there's no legitimate reason for a quiz
# source to live on, say, :6379, and it narrows what a crafted link can
# probe on an otherwise-public host.
ALLOWED_PORTS = (None, 80, 443)

GOOGLE_SHARING_HINT = (
    "Couldn't access that Google link. Open it in Google, click Share, and set "
    "General access to \"Anyone with the link\" (Viewer), then try again."
)

_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_UTF8_BOM = b"\xef\xbb\xbf"

# Tags that never contain the main readable content. <form> is deliberately
# NOT in this list: some frameworks (e.g. classic ASP.NET) wrap the entire
# page in a single <form>, and removing it would wipe out everything.
_NOISE_TAGS = [
    "script", "style", "noscript", "template", "svg", "iframe",
    "nav", "footer", "aside", "header", "button",
]


class FetchedContent(NamedTuple):
    text: str
    title: str
    # "google_doc" | "google_slides" | "google_drive" | "web"
    source_type: str


class _Download(NamedTuple):
    final_url: str
    content_type: str
    content_disposition: str
    body: bytes


# --------------------------------------------------------------------------
# URL classification
# --------------------------------------------------------------------------

def resolve_source(url: str) -> Tuple[str, str]:
    """Classify a link and return (source_type, url_to_actually_fetch).

    Google Docs/Slides/Drive "view" links return an interactive HTML app,
    not the content -- but each has an official export URL that returns the
    raw text/file for anyone with link access, so those get rewritten here.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if host == "docs.google.com":
        # ".../d/e/<token>/pub" is a "Publish to web" page: plain public
        # HTML, handled fine by the generic path below.
        if "/d/e/" not in path:
            match = re.match(r"^/document/(?:u/\d+/)?d/([\w-]+)", path)
            if match:
                return (
                    "google_doc",
                    f"https://docs.google.com/document/d/{match.group(1)}/export?format=txt",
                )
            match = re.match(r"^/presentation/(?:u/\d+/)?d/([\w-]+)", path)
            if match:
                return (
                    "google_slides",
                    f"https://docs.google.com/presentation/d/{match.group(1)}/export/txt",
                )
            if re.match(r"^/(spreadsheets|forms)/", path):
                raise ScrapeError(
                    "Google Sheets and Forms aren't supported yet. Try a Google Doc, "
                    "Google Slides, PDF, or web page link instead."
                )

    if host == "drive.google.com":
        if "/folders/" in path:
            raise ScrapeError(
                "That's a Google Drive folder link. Please share a link to a single "
                "file (or a Google Doc) instead."
            )
        match = re.match(r"^/file/(?:u/\d+/)?d/([\w-]+)", path)
        file_id = match.group(1) if match else None
        if not file_id and path in ("/open", "/uc"):
            candidate = (parse_qs(parsed.query).get("id") or [None])[0]
            if candidate and re.fullmatch(r"[\w-]+", candidate):
                file_id = candidate
        if file_id:
            return (
                "google_drive",
                f"https://drive.google.com/uc?export=download&id={file_id}",
            )

    return "web", url


# --------------------------------------------------------------------------
# SSRF protection
# --------------------------------------------------------------------------

async def _resolve_host(host: str, port: int) -> List[str]:
    """Resolve a hostname to its IP addresses. Kept as its own function so
    tests can substitute it without touching real DNS."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ScrapeError(
            "Couldn't find that website. Please check the link and try again."
        ) from e
    return [info[4][0] for info in infos]


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%")[0])  # drop IPv6 zone id
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped  # ::ffff:127.0.0.1 must be judged as 127.0.0.1
    return ip.is_global and not ip.is_multicast


async def _assert_public_url(url: str) -> None:
    """Raise ScrapeError unless url is a plain http(s) link to a host that
    resolves exclusively to public IP addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ScrapeError("Only http:// and https:// links are supported.")

    host = parsed.hostname
    if not host:
        raise ScrapeError("That link doesn't look valid.")
    if parsed.username or parsed.password:
        raise ScrapeError("Links containing a username or password aren't supported.")

    try:
        port = parsed.port
    except ValueError:
        raise ScrapeError("That link has an invalid port number.")
    if port not in ALLOWED_PORTS:
        raise ScrapeError("Links using a non-standard port aren't supported.")

    lowered = host.lower().rstrip(".")
    if lowered == "localhost" or lowered.endswith((".localhost", ".local", ".internal")):
        raise ScrapeError("That link points to a private or internal address, which isn't allowed.")

    addresses = await _resolve_host(host, port or (443 if parsed.scheme == "https" else 80))
    if not addresses or not all(_is_public_ip(a) for a in addresses):
        raise ScrapeError("That link points to a private or internal address, which isn't allowed.")


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def _status_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return (
            "That page is private or doesn't allow automated access. If it's a Google "
            "Doc or Drive file, set sharing to \"Anyone with the link\"."
        )
    if status_code in (404, 410):
        return f"That page couldn't be found (HTTP {status_code}). Please check the link."
    if status_code == 429:
        return "That site is limiting requests right now. Please try again in a bit."
    return f"That site returned an error (HTTP {status_code})."


async def _download(url: str) -> _Download:
    """GET a URL with manual redirect handling (re-validating every hop
    against the SSRF check) and a hard cap on downloaded size."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.5",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                await _assert_public_url(current)
                async with client.stream("GET", current, headers=headers) as response:
                    location = response.headers.get("location")
                    if response.status_code in _REDIRECT_STATUSES and location:
                        current = urljoin(current, location)
                        continue

                    response.raise_for_status()

                    declared = response.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > MAX_FILE_SIZE_BYTES:
                        raise ScrapeError(_too_large_message())

                    # Streamed (not response.read()) so an oversized or
                    # malicious response is cut off at the cap instead of
                    # being fully buffered in memory first. aiter_bytes()
                    # yields *decompressed* data, so this also covers
                    # gzip-bomb style responses.
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_FILE_SIZE_BYTES:
                            raise ScrapeError(_too_large_message())

                    return _Download(
                        final_url=current,
                        content_type=response.headers.get("content-type", ""),
                        content_disposition=response.headers.get("content-disposition", ""),
                        body=bytes(body),
                    )
            raise ScrapeError("That link redirected too many times.")
    except httpx.TimeoutException as e:
        raise ScrapeError("That site didn't respond in time. Please try again.") from e
    except httpx.HTTPStatusError as e:
        raise ScrapeError(_status_error_message(e.response.status_code)) from e
    except httpx.HTTPError as e:
        logger.error("Network error fetching %s: %s", url, e)
        raise ScrapeError("Couldn't reach that site. Please check the link and try again.") from e


def _too_large_message() -> str:
    return f"That content is too large (max {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)."


# --------------------------------------------------------------------------
# Content extraction
# --------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    return " ".join(_sanitize_extracted_text(text).split())


def extract_text_from_html(html: bytes) -> Tuple[str, Optional[str]]:
    """Return (readable_text, page_title) from raw HTML bytes.

    Takes bytes rather than str on purpose: BeautifulSoup sniffs the
    document's declared encoding itself, which is more reliable than us
    guessing one from headers.
    """
    soup = BeautifulSoup(html, "html.parser")

    title: Optional[str] = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # Prefer the main article body over the whole page (sidebars, "related
    # posts", cookie banners...). On listing pages with many <article>
    # tags, the one with the most text is the best guess.
    candidates = soup.find_all("article") + soup.find_all("main")
    best = ""
    for element in candidates:
        candidate_text = _clean_text(element.get_text(" "))
        if len(candidate_text) > len(best):
            best = candidate_text

    if len(best) >= MIN_HTML_CONTENT_CHARS:
        return best, title

    return _clean_text(soup.get_text(" ")), title


def _filename_from(download: _Download) -> Optional[str]:
    match = re.search(
        r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", download.content_disposition, re.IGNORECASE
    )
    if match:
        return unquote(match.group(1)).strip() or None
    last_segment = unquote(urlparse(download.final_url).path.rsplit("/", 1)[-1]).strip()
    return last_segment or None


def _extract_via_document_extractor(filename: str, content_type: str, body: bytes) -> str:
    try:
        return extract_text_from_upload(filename=filename, content_type=content_type, file_bytes=body)
    except DocumentExtractionError as e:
        raise ScrapeError(str(e)) from e


def _first_line(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:100]
    return fallback


async def fetch_url_content(url: str) -> FetchedContent:
    """Fetch and extract quiz-source text from any supported link.

    Raises ScrapeError with a specific, user-facing reason on any failure.
    """
    source_type, fetch_url = resolve_source(url.strip())
    download = await _download(fetch_url)

    if (urlparse(download.final_url).hostname or "") == "accounts.google.com":
        raise ScrapeError(GOOGLE_SHARING_HINT)

    content_type = download.content_type.split(";")[0].strip().lower()
    body = download.body
    is_pdf = content_type == "application/pdf" or body[:5] == b"%PDF-"
    is_html = content_type in ("text/html", "application/xhtml+xml")
    is_text = content_type == "text/plain"

    filename = _filename_from(download)
    google_native = source_type in ("google_doc", "google_slides")

    if is_pdf:
        text = _extract_via_document_extractor("document.pdf", "application/pdf", body)
        title = filename or "PDF document"
    elif is_text:
        text = _extract_via_document_extractor(
            "document.txt", "text/plain", body.removeprefix(_UTF8_BOM)
        )
        if google_native:
            # Google's export has no separate title field, and the extractor
            # above collapses newlines -- so read the first line from the
            # raw body instead. Doc titles are usually the first line.
            title = _first_line(
                body.decode("utf-8-sig", errors="replace"),
                "Google Doc" if source_type == "google_doc" else "Google Slides",
            )
        else:
            title = filename or "Text document"
    elif is_html:
        if source_type in ("google_doc", "google_slides"):
            # A real export is text/plain; HTML here means Google served an
            # error/login page instead.
            raise ScrapeError(GOOGLE_SHARING_HINT)
        if source_type == "google_drive":
            raise ScrapeError(
                "Couldn't download that Drive file. Make sure it's shared as \"Anyone with "
                "the link\" and is a PDF or text file under 10 MB. (For Google Docs, paste "
                "the Doc's own link.)"
            )
        text, page_title = extract_text_from_html(body)
        if len(text) < MIN_HTML_CONTENT_CHARS:
            raise ScrapeError(
                "Couldn't find enough readable text on that page. It may load its content "
                "with JavaScript or require a login. Try a different link, or save the "
                "page as a PDF and upload it instead."
            )
        title = page_title or urlparse(download.final_url).hostname or "Web page"
    else:
        raise ScrapeError(
            f"Unsupported content type ({content_type or 'unknown'}). Links to web pages, "
            "PDFs, text files, Google Docs and Google Slides are supported."
        )

    return FetchedContent(
        text=text[:MAX_CONTENT_CHARS],
        title=title.strip()[:150] or "Untitled",
        source_type=source_type,
    )
