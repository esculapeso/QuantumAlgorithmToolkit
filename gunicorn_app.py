"""
Gunicorn application entry point.
"""
from app import app as application

# This allows gunicorn to find the application
app = application