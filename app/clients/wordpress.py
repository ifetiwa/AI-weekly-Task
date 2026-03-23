"""WordPress REST API client for plugin/theme management."""

import requests


class WordPressClient:

    def __init__(self, site_url, username, app_password):
        self.base = site_url.rstrip("/")
        self.api = f"{self.base}/wp-json"
        self.auth = (username, app_password)

    # ── Plugins ─────────────────────────────────────────────────

    def get_plugins(self):
        """List installed plugins and flag those needing updates."""
        try:
            r = requests.get(
                f"{self.api}/wp/v2/plugins", auth=self.auth, timeout=15
            )
            if r.status_code == 200:
                plugins = r.json()
                needs_update = [
                    p for p in plugins
                    if isinstance(p, dict) and p.get("update")
                ]
                return {
                    "status": "warning" if needs_update else "success",
                    "summary": (
                        f"{len(plugins)} plugins — "
                        f"{len(needs_update)} need updates"
                    ),
                    "data": {
                        "total": len(plugins),
                        "updates_available": len(needs_update),
                        "plugins": [
                            {
                                "name": p.get("name", "?"),
                                "version": p.get("version"),
                                "status": p.get("status"),
                                "update": (
                                    p["update"].get("version")
                                    if isinstance(p.get("update"), dict)
                                    else None
                                ),
                            }
                            for p in plugins
                            if isinstance(p, dict)
                        ],
                    },
                }
            if r.status_code == 401:
                return _auth_fail()
            return _http_fail(r)
        except Exception as exc:
            return _exc(exc)

    def update_plugin(self, plugin_file):
        """Trigger an update for *plugin_file* (e.g. 'akismet/akismet.php')."""
        try:
            r = requests.post(
                f"{self.api}/wp/v2/plugins/{plugin_file}",
                auth=self.auth,
                json={"status": "active"},
                timeout=60,
            )
            if r.status_code == 200:
                return {
                    "status": "success",
                    "summary": f"Updated {plugin_file}",
                    "data": r.json(),
                }
            return _http_fail(r)
        except Exception as exc:
            return _exc(exc)

    def update_all_plugins(self):
        """Update every plugin that has a pending update."""
        info = self.get_plugins()
        if info["status"] == "failure":
            return info
        updated, failed = [], []
        for p in info["data"].get("plugins", []):
            if p.get("update"):
                res = self.update_plugin(p["name"])
                (updated if res["status"] == "success" else failed).append(p["name"])
        return {
            "status": "success" if not failed else "warning",
            "summary": f"Updated {len(updated)}, failed {len(failed)}",
            "data": {"updated": updated, "failed": failed},
        }

    # ── Themes ──────────────────────────────────────────────────

    def get_themes(self):
        """List installed themes."""
        try:
            r = requests.get(
                f"{self.api}/wp/v2/themes", auth=self.auth, timeout=15
            )
            if r.status_code == 200:
                themes = r.json()
                return {
                    "status": "success",
                    "summary": f"{len(themes)} themes installed",
                    "data": {
                        "total": len(themes),
                        "themes": [
                            {
                                "name": (
                                    t.get("name", {}).get("rendered")
                                    if isinstance(t.get("name"), dict)
                                    else t.get("stylesheet", "?")
                                ),
                                "status": t.get("status"),
                            }
                            for t in themes
                            if isinstance(t, dict)
                        ],
                    },
                }
            if r.status_code == 401:
                return _auth_fail()
            return _http_fail(r)
        except Exception as exc:
            return _exc(exc)

    # ── Core update status ──────────────────────────────────────

    def get_core_update_status(self):
        """Check if a core WordPress update is available."""
        try:
            r = requests.get(
                f"{self.api}/", auth=self.auth, timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                name = data.get("name", "")
                desc = data.get("description", "")
                url = data.get("url", "")
                return {
                    "status": "success",
                    "summary": f"WordPress site reachable — {name}",
                    "data": {"name": name, "description": desc, "url": url},
                }
            return _http_fail(r)
        except Exception as exc:
            return _exc(exc)


# ── Private helpers ─────────────────────────────────────────────────

def _auth_fail():
    return {
        "status": "failure",
        "summary": "Authentication failed — check WP credentials",
        "data": {"hint": "Use an Application Password generated in WP Admin"},
    }


def _http_fail(resp):
    return {
        "status": "failure",
        "summary": f"HTTP {resp.status_code}",
        "data": {"status_code": resp.status_code, "body": resp.text[:400]},
    }


def _exc(exc):
    return {
        "status": "failure",
        "summary": f"Error: {str(exc)[:150]}",
        "data": {"error": str(exc)},
    }
