"""
Simple gunicorn entry point for our public quantum simulation app.
"""
from app_public import app as application

# This allows gunicorn to find the application
app = application