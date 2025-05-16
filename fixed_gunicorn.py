"""
Fixed gunicorn application entry point.
"""
from fixed_app import app as application

# For gunicorn
app = application