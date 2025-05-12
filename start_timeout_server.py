"""
Script to start the Flask server with extended timeouts.
This script configures Gunicorn with a longer worker timeout to allow for
long-running simulations without server timeouts.
"""

import os
import sys
import subprocess

# Define the command to run
command = [
    "gunicorn",
    "--bind", "0.0.0.0:5000",
    "--timeout", "300",  # 5 minutes timeout
    "--workers", "1",
    "--reuse-port",
    "--reload",
    "main:app"
]

# Print the command for debugging
print(f"Starting server with extended timeout: {' '.join(command)}")

# Run the command
try:
    result = subprocess.run(command)
    sys.exit(result.returncode)
except KeyboardInterrupt:
    print("Server stopped by user")
    sys.exit(0)
except Exception as e:
    print(f"Error starting server: {e}")
    sys.exit(1)