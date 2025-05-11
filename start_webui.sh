#!/bin/bash
# This script starts the web UI for the quantum simulation package

# Make sure the script is executable with: chmod +x start_webui.sh

# Start the Flask application
FLASK_APP=app FLASK_DEBUG=1 python -m flask run --host=0.0.0.0 --port=5000