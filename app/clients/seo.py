"""SEO clients — sitemap validation, meta-tag scanning, PageSpeed, GSC, GA4."""

import re
import xml.etree.ElementTree as ET

import requests


class SEOClient:

    # ── Sitemap validation ──────────────────────────────────────

    @staticmethod
    def validate_sitemap(site_url, timeout=10):
        """Fetch /sitemap.xml and validate it."""
        sitemap_url = site_url.rstrip("/") + "/sitemap.xml"
        try:
            r = requests.get(sitemap_url, timeout=timeout)
            if r.status_code != 200:
                return {
                    "status": "failure",
                    "summary": f"Sitemap returned HTTP {r.status_code}",
                    "data": {"url": sitemap_url, "status_code": r.status_code},
                }
            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as pe:
                return {
                    "status": "failure",
                    "summary": f"Sitemap XML is malformed: {pe}",
                    "data": {"url": sitemap_url, "error": str(pe)},
                }
            # Count <url> or <sitemap> entries
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = root.findall(".//sm:url", ns) or root.findall(".//url")
            sitemaps = root.findall(".//sm:sitemap", ns) or root.findall(".//sitemap")
            count = len(urls) + len(sitemaps)
            return {
                "status": "success",
                "summary": f"Sitemap valid — {count} entries",
                "data": {"url": sitemap_url, "entries": count},
            }
        except Exception as exc:
            return _exc(exc)

    # ── Meta tags ───────────────────────────────────────────────

    @staticmethod
    def check_meta_tags(site_url, timeout=10):
        """Scrape a page for title and meta description."""
        try:
            r = requests.get(site_url, timeout=timeout)
            title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
            desc_m = re.search(
                r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
                r.text, re.I,
            )
            title = title_m.group(1).strip() if title_m else ""
            desc = desc_m.group(1).strip() if desc_m else ""
            issues = []
            if not title:
                issues.append("Missing <title>")
            elif len(title) > 70:
                issues.append(f"Title too long ({len(title)} chars)")
            if not desc:
                issues.append("Missing meta description")
            elif len(desc) > 160:
                issues.append(f"Description too long ({len(desc)} chars)")

            status = "success" if not issues else "warning"
            return {
                "status": status,
                "summary": (
                    "; ".join(issues) if issues
                    else f"Title ({len(title)} chars) & description ({len(desc)} chars) OK"
                ),
                "data": {"title": title, "description": desc, "issues": issues},
            }
        except Exception as exc:
            return _exc(exc)

    # ── PageSpeed Insights ──────────────────────────────────────

    @staticmethod
    def pagespeed(url, api_key=None, strategy="mobile"):
        """Query Google PageSpeed Insights."""
        params = {"url": url, "strategy": strategy}
        if api_key:
            params["key"] = api_key
        try:
            r = requests.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params=params,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                cat = data.get("lighthouseResult", {}).get("categories", {})
                perf = cat.get("performance", {}).get("score")
                score = int(perf * 100) if perf is not None else None
                status = (
                    "success" if score and score >= 70
                    else "warning" if score and score >= 40
                    else "failure"
                )
                return {
                    "status": status,
                    "summary": f"PageSpeed score: {score}/100 ({strategy})",
                    "data": {
                        "score": score,
                        "strategy": strategy,
                        "fcp": _audit(data, "first-contentful-paint"),
                        "lcp": _audit(data, "largest-contentful-paint"),
                        "cls": _audit(data, "cumulative-layout-shift"),
                    },
                }
            return {
                "status": "failure",
                "summary": f"PageSpeed API returned {r.status_code}",
                "data": {"status_code": r.status_code, "body": r.text[:400]},
            }
        except Exception as exc:
            return _exc(exc)

    # ── Google Search Console (placeholder) ─────────────────────

    @staticmethod
    def search_console_check(config_data):
        """Placeholder — real implementation needs OAuth2 flow."""
        if not config_data.get("api_key") or not config_data.get("site_url"):
            return {
                "status": "skipped",
                "summary": "Search Console credentials incomplete",
                "data": {},
            }
        return {
            "status": "warning",
            "summary": (
                "Search Console integration requires OAuth2 setup. "
                "Visit Google Cloud Console to configure credentials."
            ),
            "data": {
                "site_url": config_data.get("site_url"),
                "hint": "Full OAuth2 flow needed for production use.",
            },
        }

    # ── Google Analytics (placeholder) ──────────────────────────

    @staticmethod
    def analytics_check(config_data):
        """Placeholder — real implementation needs OAuth2 / service account."""
        if not config_data.get("property_id"):
            return {
                "status": "skipped",
                "summary": "GA4 property ID not configured",
                "data": {},
            }
        return {
            "status": "warning",
            "summary": (
                "GA4 integration requires service-account credentials. "
                "Configure in Google Cloud Console."
            ),
            "data": {
                "property_id": config_data.get("property_id"),
                "hint": "Service account JSON key required for API access.",
            },
        }


# ── Private helpers ─────────────────────────────────────────────────

def _audit(data, audit_id):
    audits = data.get("lighthouseResult", {}).get("audits", {})
    a = audits.get(audit_id, {})
    return a.get("displayValue", "N/A")


def _exc(exc):
    return {
        "status": "failure",
        "summary": f"Error: {str(exc)[:150]}",
        "data": {"error": str(exc)},
    }
