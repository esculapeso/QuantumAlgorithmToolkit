"""
Simple gunicorn entry point for the working quantum simulation application.
"""
from working_app import app as application

# This allows gunicorn to find the application
app = application