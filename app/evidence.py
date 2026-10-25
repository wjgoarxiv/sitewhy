"""Evidence fetcher and verbatim quote verifier.

A quote counts as verified only when its normalized text is contained in the
normalized source text. No model decides this and nothing is fuzzy-matched:
anything that cannot be fetched or checked is `unverifiable`.
"""

import hashlib
import io
import json
import re
import unicodedata
import warnings
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from pypdf import PdfReader

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = ROOT / "data/sources"
USER_AGENT = "SiteWhy/0.1 (data center site screening research)"
BLOCKED_HOSTS = ("municode.com", "ecode360.com", "amlegal.com")
MIN_QUOTE_CHARS = 12
PUNCT = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'",
                       "–": "-", "—": "-", " ": " "})  # fmt: skip


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("­", "").translate(PUNCT)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    return soup.get_text("\n")


def pdf_to_text(data: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)


class EvidenceFetcher:
    def __init__(self, client: httpx.Client | None = None, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.client = client or httpx.Client(
            timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self.cache_dir = Path(cache_dir)
        self._robots: dict[str, RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS):
            return False
        if host not in self._robots:
            parser = None
            try:
                resp = self.client.get(f"{urlparse(url).scheme}://{host}/robots.txt")
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                parser = None
            self._robots[host] = parser
        parser = self._robots[host]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> dict:
        """Return {url, fetched_at, text} or {url, error}. Successful fetches are cached."""
        cache = self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:24]}.json"
        if cache.is_file():
            return json.loads(cache.read_text())
        if not self._allowed(url):
            return {"url": url, "error": "blocked by robots.txt or platform policy"}
        try:
            resp = self.client.get(url)
        except httpx.HTTPError as exc:
            return {"url": url, "error": f"fetch failed: {type(exc).__name__}"}
        if resp.status_code != 200:
            return {"url": url, "error": f"HTTP {resp.status_code}"}
        kind = resp.headers.get("content-type", "")
        try:
            is_pdf = "pdf" in kind or resp.content[:5] == b"%PDF-"
            text = pdf_to_text(resp.content) if is_pdf else html_to_text(resp.text)
        except Exception as exc:  # noqa: BLE001 - malformed documents are unverifiable, not fatal
            return {"url": url, "error": f"parse failed: {type(exc).__name__}"}
        doc = {"url": url, "fetched_at": datetime.now(UTC).isoformat(), "text": text}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(doc))
        return doc

    def verify(self, quote: str, url: str) -> dict:
        needle = normalize_text(quote)
        if len(needle) < MIN_QUOTE_CHARS:
            return {"status": "unverifiable", "reason": "quote too short", "matched_span": None,
                    "fetched_at": None}  # fmt: skip
        doc = self.fetch(url)
        if "error" in doc:
            return {"status": "unverifiable", "reason": doc["error"], "matched_span": None,
                    "fetched_at": None}  # fmt: skip
        haystack = normalize_text(doc["text"])
        pos = haystack.find(needle)
        if pos == -1:
            return {"status": "not_found", "matched_span": None, "fetched_at": doc["fetched_at"]}
        span = haystack[max(0, pos - 60) : pos + len(needle) + 60]
        return {"status": "verified", "matched_span": span, "fetched_at": doc["fetched_at"]}
