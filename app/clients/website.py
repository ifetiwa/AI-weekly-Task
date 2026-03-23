"""Website health, SSL, and link-checking client."""

import re
import socket
import ssl
import time
from urllib.parse import urlparse

import requests


class WebsiteClient:

    @staticmethod
    def check_health(url, timeout=10):
        """HTTP GET check — is the site live?"""
        try:
            start = time.time()
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            ms = int((time.time() - start) * 1000)
            ok = 200 <= resp.status_code < 400
            return {
                "status": "success" if ok else "warning",
                "summary": f"HTTP {resp.status_code} in {ms}ms",
                "data": {
                    "status_code": resp.status_code,
                    "response_time_ms": ms,
                    "final_url": resp.url,
                    "content_length": len(resp.content),
                },
            }
        except requests.ConnectionError as exc:
            # Provide a human-friendly message for common connection issues
            err = str(exc)
            if "NameResolutionError" in err or "getaddrinfo failed" in err:
                return {
                    "status": "failure",
                    "summary": f"DNS resolution failed — domain not found for {url}",
                    "data": {"error": "DNS lookup failed. Check that the domain is correct and publicly resolvable.", "url": url},
                }
            if "ConnectionRefusedError" in err:
                return {
                    "status": "failure",
                    "summary": f"Connection refused by {url}",
                    "data": {"error": "The server refused the connection. It may be down or blocking requests.", "url": url},
                }
            return {
                "status": "failure",
                "summary": f"Could not connect to {url}",
                "data": {"error": err[:300], "url": url},
            }
        except requests.Timeout:
            return {
                "status": "failure",
                "summary": f"Request timed out after {timeout}s for {url}",
                "data": {"error": "The server did not respond within the timeout period.", "url": url},
            }
        except requests.RequestException as exc:
            return {
                "status": "failure",
                "summary": f"Request failed: {str(exc)[:120]}",
                "data": {"error": str(exc)[:300], "url": url},
            }

    @staticmethod
    def check_ssl(url, timeout=10):
        """Check SSL certificate validity and days until expiry."""
        hostname = urlparse(url).hostname
        if not hostname:
            return {"status": "failure", "summary": "Invalid URL", "data": {}}
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as tls:
                    cert = tls.getpeercert()
                    not_after = ssl.cert_time_to_seconds(cert["notAfter"])
                    days = int((not_after - time.time()) / 86400)
                    status = (
                        "success" if days > 30
                        else "warning" if days > 0
                        else "failure"
                    )
                    return {
                        "status": status,
                        "summary": f"SSL valid — expires in {days} days",
                        "data": {
                            "issuer": dict(x[0] for x in cert.get("issuer", [])),
                            "expires": cert["notAfter"],
                            "days_remaining": days,
                        },
                    }
        except Exception as exc:
            return {
                "status": "failure",
                "summary": f"SSL check failed: {str(exc)[:120]}",
                "data": {"error": str(exc)},
            }

    @staticmethod
    def check_links(url, timeout=8):
        """Crawl a page and report broken links (limited to first 25)."""
        try:
            resp = requests.get(url, timeout=timeout)
            hrefs = re.findall(r'href=["\']([^"\']+)["\']', resp.text)
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            broken, checked = [], 0
            for href in hrefs[:25]:
                if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                    continue
                full = href if href.startswith("http") else base + href
                checked += 1
                try:
                    r = requests.head(full, timeout=5, allow_redirects=True)
                    if r.status_code >= 400:
                        broken.append({"url": full, "status": r.status_code})
                except requests.RequestException:
                    broken.append({"url": full, "status": "timeout"})
            status = "success" if not broken else "warning"
            return {
                "status": status,
                "summary": f"Checked {checked} links — {len(broken)} broken",
                "data": {"checked": checked, "broken": broken},
            }
        except Exception as exc:
            return {
                "status": "failure",
                "summary": f"Link check failed: {str(exc)[:120]}",
                "data": {"error": str(exc)},
            }
