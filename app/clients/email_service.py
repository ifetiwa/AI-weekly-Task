"""Email service API client — SendGrid & Mailgun."""

import requests


class EmailClient:

    # ── SendGrid ────────────────────────────────────────────────

    @staticmethod
    def sendgrid_stats(api_key):
        """Fetch today's global stats from SendGrid."""
        from datetime import date
        today = date.today().isoformat()
        try:
            r = requests.get(
                "https://api.sendgrid.com/v3/stats",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"start_date": today},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    metrics = data[0].get("stats", [{}])[0].get("metrics", {})
                    return {
                        "status": "success",
                        "summary": (
                            f"Delivered: {metrics.get('delivered', 0)}, "
                            f"Opens: {metrics.get('opens', 0)}, "
                            f"Bounces: {metrics.get('bounces', 0)}"
                        ),
                        "data": metrics,
                    }
                return {
                    "status": "success",
                    "summary": "No email activity today",
                    "data": {},
                }
            return _fail(r)
        except Exception as exc:
            return _exc(exc)

    @staticmethod
    def sendgrid_bounces(api_key):
        """Fetch recent bounces."""
        try:
            r = requests.get(
                "https://api.sendgrid.com/v3/suppression/bounces",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if r.status_code == 200:
                bounces = r.json()
                return {
                    "status": "warning" if bounces else "success",
                    "summary": f"{len(bounces)} bounces on record",
                    "data": {"count": len(bounces),
                             "recent": bounces[:10]},
                }
            return _fail(r)
        except Exception as exc:
            return _exc(exc)

    @staticmethod
    def sendgrid_spam_reports(api_key):
        """Fetch spam report count."""
        try:
            r = requests.get(
                "https://api.sendgrid.com/v3/suppression/spam_reports",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if r.status_code == 200:
                reports = r.json()
                return {
                    "status": "warning" if reports else "success",
                    "summary": f"{len(reports)} spam reports",
                    "data": {"count": len(reports),
                             "recent": reports[:10]},
                }
            return _fail(r)
        except Exception as exc:
            return _exc(exc)

    @staticmethod
    def sendgrid_send_test(api_key, from_email, to_email=None):
        """Send a test email via SendGrid."""
        to_email = to_email or from_email
        try:
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_email},
                "subject": "Checklist System — Test Email",
                "content": [
                    {
                        "type": "text/plain",
                        "value": "This is an automated test from the Tech Checklist system.",
                    }
                ],
            }
            r = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if r.status_code in (200, 201, 202):
                return {
                    "status": "success",
                    "summary": f"Test email sent to {to_email}",
                    "data": {"to": to_email},
                }
            return _fail(r)
        except Exception as exc:
            return _exc(exc)

    # ── Mailgun ─────────────────────────────────────────────────

    @staticmethod
    def mailgun_stats(api_key, domain):
        """Fetch basic Mailgun stats."""
        try:
            r = requests.get(
                f"https://api.mailgun.net/v3/{domain}/stats/total",
                auth=("api", api_key),
                params={"event": ["delivered", "failed", "opened"], "duration": "1d"},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                return {
                    "status": "success",
                    "summary": f"Mailgun stats retrieved for {domain}",
                    "data": data,
                }
            return _fail(r)
        except Exception as exc:
            return _exc(exc)


# ── Private helpers ─────────────────────────────────────────────────

def _fail(resp):
    return {
        "status": "failure",
        "summary": f"API returned HTTP {resp.status_code}",
        "data": {"status_code": resp.status_code, "body": resp.text[:400]},
    }


def _exc(exc):
    return {
        "status": "failure",
        "summary": f"Error: {str(exc)[:150]}",
        "data": {"error": str(exc)},
    }
