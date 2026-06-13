"""Company website signal — fetches careers pages and engineering blogs.

Given a company domain, checks for:
- /careers or /jobs — hiring signal with role descriptions
- /blog or /engineering-blog — technical problem signal

All fetches are plain HTTP GET — no JS, no auth, free.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {
    "User-Agent": "UpSearchCompanySignal/0.1",
    "Accept": "text/html,text/plain;q=0.8,*/*;q=0.5",
}
_MAX_TEXT_CHARS = 20_000

# Common blog and careers path patterns
BLOG_PATHS = ["/blog", "/engineering-blog", "/engineering", "/tech-blog", "/devblog", "/updates", "/news"]
CAREERS_PATHS = ["/careers", "/jobs", "/join", "/about", "/team", "/company/careers", "/about-us"]


def _clean_html(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[: _MAX_TEXT_CHARS]


def _headings(html: str) -> list[str]:
    matches = re.findall(r"<h[1-3][^>]*>([\s\S]*?)</h[1-3]>", html, re.I)
    return [re.sub(r"<[^>]+>", "", h).strip() for h in matches if h.strip()][:12]


def _role_keywords(text: str) -> list[str]:
    """Extract job role keywords from careers page text."""
    keywords = set()
    patterns = [
        r"(?:intern|internship|software engineer|ML engineer|research scientist|data scientist|SDE|full[- ]stack|backend|frontend|infrastructure|platform|systems|applied scientist)",
        r"(?:Python|Rust|Go|CUDA|PyTorch|TensorFlow|Kubernetes|Docker|Spark|Kafka|AWS|GCP|Azure)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            keywords.add(match.group(0).lower())
    return sorted(keywords)[:20]


def _blog_headlines(html: str) -> list[str]:
    """Extract blog post titles from engineering blog HTML."""
    titles = _headings(html)
    # Also catch article titles in common CMS patterns
    for match in re.finditer(r'class="[^"]*(?:entry-title|post-title|headline|title)[^"]*"[^>]*>([^<]+)', html, re.I):
        t = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if t and len(t) > 15:
            titles.append(t)
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{20,})</a>', html):
        href = match.group(1)
        t = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        # Only include links that look like blog posts (contain date or /blog/ or are longer titles)
        if t and len(t) > 20 and (t[0].isupper() or t[0].isdigit()):
            titles.append(t)
    return list(dict.fromkeys(titles))[:15]


def _try_get(client: httpx.Client, base_url: str, path: str) -> tuple[str | None, str]:
    """Try fetching a path from a base URL. Returns (full_url, cleaned_text) or (None, '')."""
    url = base_url.rstrip("/") + path
    try:
        resp = client.get(url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200:
            text = _clean_html(resp.text)
            if len(text) > 50:
                return url, text
        return None, ""
    except Exception:
        return None, ""


def fetch_company_signal(domain: str) -> dict[str, Any]:
    """Fetch hiring and technical blog signal from a company website.

    Args:
        domain: The company's domain (e.g. 'baseten.co', 'modal.com').

    Returns:
        Dict with 'careers' and 'blog' sections, each containing url, text, and extracted keywords.
    """
    base_url = f"https://{domain}" if not domain.startswith("http") else domain
    result: dict[str, Any] = {
        "domain": domain,
        "blog": {"found": False, "url": "", "headlines": [], "raw_text": ""},
        "careers": {"found": False, "url": "", "title": "", "roles": [], "raw_text": ""},
        "error": None,
    }

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            # Check careers paths
            for path in CAREERS_PATHS:
                url, text = _try_get(client, base_url, path)
                if url and text:
                    title_match = re.search(r"<title[^>]*>([^<]+)</title>", text)
                    title = _clean_html(title_match.group(1)) if title_match else ""
                    result["careers"] = {
                        "found": True,
                        "url": url,
                        "title": title,
                        "roles": _role_keywords(text),
                        "raw_text": text[:5000],
                    }
                    break

            # Check blog paths
            for path in BLOG_PATHS:
                url, text = _try_get(client, base_url, path)
                if url and text:
                    result["blog"] = {
                        "found": True,
                        "url": url,
                        "headlines": _blog_headlines(text),
                        "raw_text": text[:5000],
                    }
                    break

    except Exception as exc:
        result["error"] = str(exc)

    return result
