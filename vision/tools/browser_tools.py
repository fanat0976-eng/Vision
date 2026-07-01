"""Browser tool — web fetching and content extraction."""

import ipaddress
import re
import urllib.parse

import httpx


def _is_safe_url(url: str) -> bool:
    """Block private IPs, link-local, and file:// scheme."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        # Block file:// and other non-http schemes
        if parsed.scheme == "file":
            return False
        # Try to parse as IP
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # Not an IP — check hostname patterns
            if hostname in ("localhost", "127.0.0.1", "::1"):
                return False
            if hostname.endswith(".local"):
                return False
        return True
    except Exception:
        return False


async def fetch_url(url: str, format: str = "text") -> dict:
    """Fetch URL content."""
    if not _is_safe_url(url):
        return {"error": f"Blocked: {url} is a private/internal URL"}
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Vision/0.1"})
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            if format == "html":
                return {"url": url, "content": resp.text[:50000], "status": resp.status_code}

            # Extract text from HTML
            text = resp.text
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            return {
                "url": url,
                "content": text[:30000],
                "status": resp.status_code,
                "content_type": content_type,
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {url}"}
    except Exception as e:
        return {"error": str(e)}


async def search_web(query: str, num_results=5) -> dict:
    """Web search via DuckDuckGo HTML."""
    try:
        num_results = int(num_results)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Vision/0.1"},
            )
            text = resp.text

            results = []
            pattern = r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, text)

            for url, title in matches[:num_results]:
                if "uddg=" in url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                    url = parsed.get("uddg", [url])[0]
                results.append({"title": title.strip(), "url": url})

            if not results:
                pattern2 = r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]{10,})</a>'
                matches2 = re.findall(pattern2, text)
                for url, title in matches2[:num_results]:
                    if "duckduckgo" not in url:
                        results.append({"title": title.strip(), "url": url})

            return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}
