"""Monitoring clients — uptime, API health, UptimeRobot."""

import time

import requests


class MonitoringClient:

    @staticmethod
    def check_api_health(url, timeout=10):
        """Simple HTTP health check with response-time measurement."""
        try:
            start = time.time()
            r = requests.get(url, timeout=timeout, allow_redirects=True)
            ms = int((time.time() - start) * 1000)
            ok = 200 <= r.status_code < 400
            return {
                "status": "success" if ok else "warning",
                "summary": f"HTTP {r.status_code} in {ms}ms",
                "data": {
                    "status_code": r.status_code,
                    "response_time_ms": ms,
                },
            }
        except requests.RequestException as exc:
            return {
                "status": "failure",
                "summary": f"Unreachable: {str(exc)[:120]}",
                "data": {"error": str(exc)},
            }

    @staticmethod
    def uptimerobot_status(api_key):
        """Fetch monitor status from UptimeRobot API."""
        try:
            r = requests.post(
                "https://api.uptimerobot.com/v2/getMonitors",
                data={"api_key": api_key, "format": "json"},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                monitors = data.get("monitors", [])
                down = [m for m in monitors if m.get("status") != 2]
                return {
                    "status": "warning" if down else "success",
                    "summary": (
                        f"{len(monitors)} monitors — "
                        f"{len(down)} down" if down
                        else f"{len(monitors)} monitors — all up"
                    ),
                    "data": {
                        "total": len(monitors),
                        "down": len(down),
                        "monitors": [
                            {
                                "name": m.get("friendly_name", "?"),
                                "url": m.get("url"),
                                "status": m.get("status"),
                            }
                            for m in monitors
                        ],
                    },
                }
            return {
                "status": "failure",
                "summary": f"UptimeRobot API returned {r.status_code}",
                "data": {"status_code": r.status_code},
            }
        except Exception as exc:
            return {
                "status": "failure",
                "summary": f"Error: {str(exc)[:150]}",
                "data": {"error": str(exc)},
            }
