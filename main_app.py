"""
Entry point for the web application.
This file starts the Flask application.
"""
from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)