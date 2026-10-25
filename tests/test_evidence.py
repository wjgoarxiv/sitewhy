from pathlib import Path

import httpx
import pytest

from app.evidence import EvidenceFetcher, normalize_text

PDF = (Path(__file__).parent / "fixtures/sources/ordinance.pdf").read_bytes()
HTML = (
    "<html><head><script>var x='moratorium on data centers'</script></head><body>"
    "<p>The Board hereby establishes a\n  twelve (12)&nbsp;month moratorium on the "
    "“acceptance” of data­center applications. Ofﬁcial regu-\nlation.</p>"
    "</body></html>"
)


def route(request):
    url = str(request.url)
    if url.endswith("/robots.txt"):
        if "blocked.gov" in url:
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return httpx.Response(404)
    if url.endswith(".pdf"):
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    if "forbidden" in url:
        return httpx.Response(403)
    if "timeout" in url:
        raise httpx.ReadTimeout("slow")
    return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})


@pytest.fixture
def fetcher(tmp_path):
    return EvidenceFetcher(
        client=httpx.Client(transport=httpx.MockTransport(route)), cache_dir=tmp_path
    )


def test_exact_quote_verified_with_span(fetcher):
    r = fetcher.verify("twelve (12) month moratorium", "https://county.gov/ord")
    assert r["status"] == "verified" and r["fetched_at"]
    assert "twelve (12)" in r["matched_span"]


def test_whitespace_quotes_softhyphen_ligature_and_linebreak_hyphen_normalized(fetcher):
    assert (
        fetcher.verify('"acceptance" of datacenter applications', "https://county.gov/ord")[
            "status"
        ]
        == "verified"
    )
    assert fetcher.verify("Official regulation.", "https://county.gov/ord")["status"] == "verified"


def test_script_text_is_not_evidence(fetcher):
    assert fetcher.verify("moratorium on data centers", "https://county.gov/ord")["status"] == (
        "not_found"
    )


def test_absent_quote_not_found(fetcher):
    assert (
        fetcher.verify("a 24 month moratorium", "https://county.gov/ord")["status"] == "not_found"
    )


def test_pdf_text_extracted(fetcher):
    r = fetcher.verify(
        "moratorium on the acceptance, processing, review, or approval of applications",
        "https://county.gov/ordinance.pdf",
    )
    assert r["status"] == "verified"


def test_http_errors_timeouts_robots_and_blocked_hosts_are_unverifiable(fetcher):
    for url in (
        "https://county.gov/forbidden",
        "https://county.gov/timeout",
        "https://blocked.gov/page",
        "https://library.municode.com/md/washington_county",
    ):
        assert fetcher.verify("anything at all here", url)["status"] == "unverifiable", url


def test_fetch_is_cached(tmp_path):
    calls = []

    def counting(request):
        calls.append(str(request.url))
        return route(request)

    f = EvidenceFetcher(
        client=httpx.Client(transport=httpx.MockTransport(counting)), cache_dir=tmp_path
    )
    f.verify("twelve (12) month moratorium", "https://county.gov/ord")
    f.verify("month moratorium", "https://county.gov/ord")
    assert len([c for c in calls if not c.endswith("robots.txt")]) == 1


def test_short_quotes_are_rejected(fetcher):
    assert fetcher.verify("the", "https://county.gov/ord")["status"] == "unverifiable"


def test_normalize_text():
    assert normalize_text("Ofﬁcial  “A” – regu-\nlation") == 'official "a" - regulation'
