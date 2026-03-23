"""Vercel serverless entry point — exposes the Flask app as a WSGI handler."""

from app import create_app

app = create_app()
