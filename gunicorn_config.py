"""
Gunicorn configuration for the quantum simulation application.
"""

# Bind to all network interfaces (0.0.0.0) on port 5000
bind = "0.0.0.0:5000"

# Set worker timeout to 3 minutes (180 seconds) to allow longer-running simulations
timeout = 180

# Enable auto-reloading for development
reload = True

# Use a single worker for this application
workers = 1

# Other settings
worker_class = "sync"
loglevel = "info"