"""Weekly tech checklist task definitions."""

WEEKLY_CHECKLIST = {
    "Monday": {
        "label": "Websites & CMS",
        "tasks": [
            "Check all websites are live",
            "Open homepage, login, dashboard, and key pages",
            "Check SSL certificates (no warnings)",
            "Test forms (contact, signup, payments)",
            "Run speed test (mobile + desktop)",
            "Fix broken links (if any)",
            "Update CMS",
            "Update plugins/extensions",
            "Remove unused plugins/themes",
        ],
    },
    "Tuesday": {
        "label": "SEO & Analytics",
        "tasks": [
            "Check Google Search Console for errors",
            "Fix indexing/crawl issues",
            "Confirm sitemap is valid",
            "Review traffic in GA4",
            "Check top-performing pages",
            "Review keyword rankings",
            "Verify tracking pixels (Meta, Google Ads)",
            "Review meta titles/descriptions",
        ],
    },
    "Wednesday": {
        "label": "Email & Deliverability",
        "tasks": [
            "Check email dashboard (SendGrid/Mailgun/etc.)",
            "Review bounce rate",
            "Review spam complaints",
            "Send test email (confirm inbox delivery)",
            "Check spam placement",
            "Verify SPF record",
            "Verify DKIM record",
            "Verify DMARC record",
            "Test OTP, password reset, and alerts",
        ],
    },
    "Thursday": {
        "label": "LIMS & Core Systems",
        "tasks": [
            "Log into LIMS and confirm access",
            "Check recent data entries",
            "Test report generation",
            "Test exports/downloads",
            "Confirm integrations are syncing",
            "Review user permissions",
            "Check audit logs",
            "Confirm no system errors",
        ],
    },
    "Friday": {
        "label": "Systems & Performance",
        "tasks": [
            "Check internal dashboards/admin panels",
            "Confirm data is updating correctly",
            "Test core workflows end-to-end",
            "Review API logs (errors/slow responses)",
            "Check uptime monitoring alerts",
            "Review server usage (CPU, RAM, bandwidth)",
            "Investigate any incidents from the week",
        ],
    },
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
