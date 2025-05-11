"""
Script to start the quantum simulation web application.
"""
import os
from app import app

if __name__ == "__main__":
    print("Starting Quantum Simulation Web Interface")
    app.run(host='0.0.0.0', port=5000, debug=True)