"""DNS record checker — SPF, DKIM, DMARC lookups."""

try:
    import dns.resolver as _resolver
    _HAS_DNSPYTHON = True
except ImportError:
    _HAS_DNSPYTHON = False

import subprocess
import re


class DNSClient:

    @staticmethod
    def check_spf(domain):
        records = _txt_records(domain)
        spf = [r for r in records if "v=spf1" in r]
        if spf:
            return {
                "status": "success",
                "summary": f"SPF record found for {domain}",
                "data": {"records": spf},
            }
        return {
            "status": "failure",
            "summary": f"No SPF record found for {domain}",
            "data": {"all_txt": records},
        }

    @staticmethod
    def check_dkim(domain, selector="default"):
        dkim_domain = f"{selector}._domainkey.{domain}"
        records = _txt_records(dkim_domain)
        dkim = [r for r in records if "v=DKIM1" in r or "k=rsa" in r]
        if dkim:
            return {
                "status": "success",
                "summary": f"DKIM record found ({selector}._domainkey)",
                "data": {"selector": selector, "records": dkim},
            }
        return {
            "status": "warning",
            "summary": f"No DKIM record for selector '{selector}'",
            "data": {"selector": selector, "all_txt": records,
                     "hint": "Try a different selector (google, mail, etc.)"},
        }

    @staticmethod
    def check_dmarc(domain):
        dmarc_domain = f"_dmarc.{domain}"
        records = _txt_records(dmarc_domain)
        dmarc = [r for r in records if "v=DMARC1" in r]
        if dmarc:
            return {
                "status": "success",
                "summary": f"DMARC record found for {domain}",
                "data": {"records": dmarc},
            }
        return {
            "status": "failure",
            "summary": f"No DMARC record found for {domain}",
            "data": {"all_txt": records},
        }

    @staticmethod
    def check_all(domain):
        """Run SPF + DKIM + DMARC and return a combined result."""
        spf = DNSClient.check_spf(domain)
        dkim = DNSClient.check_dkim(domain)
        dmarc = DNSClient.check_dmarc(domain)
        statuses = [spf["status"], dkim["status"], dmarc["status"]]
        if "failure" in statuses:
            overall = "failure"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "success"
        return {
            "status": overall,
            "summary": (
                f"SPF: {spf['status']}, "
                f"DKIM: {dkim['status']}, "
                f"DMARC: {dmarc['status']}"
            ),
            "data": {"spf": spf, "dkim": dkim, "dmarc": dmarc},
        }


# ── TXT record lookup ──────────────────────────────────────────────

def _txt_records(domain):
    """Return a list of TXT record strings for *domain*."""
    if _HAS_DNSPYTHON:
        return _txt_dnspython(domain)
    return _txt_nslookup(domain)


def _txt_dnspython(domain):
    try:
        answers = _resolver.resolve(domain, "TXT")
        return [
            b"".join(rdata.strings).decode("utf-8", errors="replace")
            for rdata in answers
        ]
    except Exception:
        return []


def _txt_nslookup(domain):
    """Fallback using the system nslookup command."""
    try:
        proc = subprocess.run(
            ["nslookup", "-type=TXT", domain],
            capture_output=True, text=True, timeout=10,
        )
        return re.findall(r'"([^"]+)"', proc.stdout)
    except Exception:
        return []
