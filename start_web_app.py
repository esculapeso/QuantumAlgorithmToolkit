"""
Start the Flask web application for the quantum simulation interface.

Usage:
    python start_web_app.py
"""

import flask
from app import app

if __name__ == "__main__":
    print("Starting Quantum Simulation Web Interface")
    print(f"Flask version: {flask.__version__}")
    app.run(host='0.0.0.0', port=5000, debug=True)