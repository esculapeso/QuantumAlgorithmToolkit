"""
Entry point to our simplified quantum simulation app.
"""
from noauth_app import app

# This allows gunicorn to find the application
application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)