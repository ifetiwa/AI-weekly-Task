"""API client dispatcher — routes integration types to the correct client."""


def dispatch(integration_type, task_name, *, site=None, configs=None):
    """Run the appropriate check and return a result dict.

    Every result dict has the shape::

        {"status": "success"|"failure"|"warning"|"skipped",
         "summary": "human-readable line",
         "data": { ... }}
    """
    configs = configs or []

    if integration_type == "manual":
        return _skipped("Manual task — requires human action")

    # ── Website & SSL ───────────────────────────────────────────
    if integration_type == "website_health":
        if not site:
            return _skipped("No site configured")
        from .website import WebsiteClient
        return WebsiteClient.check_health(site.url)

    if integration_type == "ssl_check":
        if not site:
            return _skipped("No site configured")
        from .website import WebsiteClient
        return WebsiteClient.check_ssl(site.url)

    if integration_type == "link_check":
        if not site:
            return _skipped("No site configured")
        from .website import WebsiteClient
        return WebsiteClient.check_links(site.url)

    # ── PageSpeed ───────────────────────────────────────────────
    if integration_type == "pagespeed":
        if not site:
            return _skipped("No site configured")
        api_key = _find_config(configs, "pagespeed", "api_key")
        from .seo import SEOClient
        return SEOClient.pagespeed(site.url, api_key=api_key)

    # ── WordPress ───────────────────────────────────────────────
    if integration_type == "wordpress":
        if not site:
            return _skipped("No site configured")
        creds = site.get_credentials()
        if not creds.get("username") or not creds.get("app_password"):
            return _skipped("WordPress credentials not configured for this site")
        from .wordpress import WordPressClient
        wp = WordPressClient(site.url, creds["username"], creds["app_password"])
        if "plugin" in task_name.lower():
            return wp.get_plugins()
        if "theme" in task_name.lower():
            return wp.get_themes()
        if "cms" in task_name.lower() or "update" in task_name.lower():
            return wp.get_core_update_status()
        return wp.get_plugins()

    # ── DNS checks ──────────────────────────────────────────────
    if integration_type == "dns_check":
        if not site:
            return _skipped("No site configured — need a domain for DNS lookup")
        from .dns_checker import DNSClient
        from urllib.parse import urlparse
        domain = urlparse(site.url).hostname or site.url
        if "spf" in task_name.lower():
            return DNSClient.check_spf(domain)
        if "dkim" in task_name.lower():
            return DNSClient.check_dkim(domain)
        if "dmarc" in task_name.lower():
            return DNSClient.check_dmarc(domain)
        return DNSClient.check_all(domain)

    # ── Email service ───────────────────────────────────────────
    if integration_type == "email_service":
        cfg = _find_integration(configs, "sendgrid") or _find_integration(configs, "mailgun")
        if not cfg:
            return _skipped("No email service (SendGrid/Mailgun) configured")
        config_data = cfg.get_config()
        from .email_service import EmailClient
        if cfg.service_type == "sendgrid":
            if "bounce" in task_name.lower():
                return EmailClient.sendgrid_bounces(config_data.get("api_key", ""))
            if "spam" in task_name.lower():
                return EmailClient.sendgrid_spam_reports(config_data.get("api_key", ""))
            if "test" in task_name.lower() or "send" in task_name.lower():
                return EmailClient.sendgrid_send_test(
                    config_data.get("api_key", ""),
                    config_data.get("from_email", "test@example.com"),
                )
            return EmailClient.sendgrid_stats(config_data.get("api_key", ""))
        # mailgun
        return EmailClient.mailgun_stats(
            config_data.get("api_key", ""), config_data.get("domain", "")
        )

    # ── SEO / Search Console ────────────────────────────────────
    if integration_type == "search_console":
        cfg = _find_integration(configs, "google_search_console")
        if not cfg:
            return _skipped("Google Search Console not configured")
        config_data = cfg.get_config()
        from .seo import SEOClient
        return SEOClient.search_console_check(config_data)

    if integration_type == "sitemap_check":
        if not site:
            return _skipped("No site configured")
        from .seo import SEOClient
        return SEOClient.validate_sitemap(site.url)

    if integration_type == "meta_check":
        if not site:
            return _skipped("No site configured")
        from .seo import SEOClient
        return SEOClient.check_meta_tags(site.url)

    # ── Analytics ───────────────────────────────────────────────
    if integration_type == "analytics":
        cfg = _find_integration(configs, "google_analytics")
        if not cfg:
            return _skipped("Google Analytics not configured")
        config_data = cfg.get_config()
        from .seo import SEOClient
        return SEOClient.analytics_check(config_data)

    # ── API health ─────────────────────────────────────────────
    if integration_type == "api_health":
        if not site:
            return _skipped("No site configured")
        from .monitoring import MonitoringClient
        return MonitoringClient.check_api_health(site.url)

    # ── Uptime ──────────────────────────────────────────────────
    if integration_type == "uptime":
        cfg = _find_integration(configs, "uptimerobot")
        if cfg:
            config_data = cfg.get_config()
            from .monitoring import MonitoringClient
            return MonitoringClient.uptimerobot_status(config_data.get("api_key", ""))
        if site:
            from .monitoring import MonitoringClient
            return MonitoringClient.check_api_health(site.url)
        return _skipped("No uptime monitor or site configured")

    # ── Server monitor ──────────────────────────────────────────
    if integration_type == "server_monitor":
        if not site:
            return _skipped("No site configured")
        from .monitoring import MonitoringClient
        return MonitoringClient.check_api_health(site.url)

    return _skipped(f"Unknown integration type: {integration_type}")


# ── Helpers ─────────────────────────────────────────────────────────

def _skipped(msg):
    return {"status": "skipped", "summary": msg, "data": {}}


def _find_integration(configs, service_type):
    for c in configs:
        if c.service_type == service_type and c.is_active:
            return c
    return None


def _find_config(configs, service_type, key):
    cfg = _find_integration(configs, service_type)
    if cfg:
        return cfg.get_config().get(key)
    return None
