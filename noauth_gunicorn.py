"""
Simple gunicorn entry point for the no-auth quantum simulation app.
"""
from noauth_app import app as application

# This allows gunicorn to find the application
app = application