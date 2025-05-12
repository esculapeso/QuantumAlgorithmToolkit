"""
Start the Quantum Simulation web server with proper timeout settings.
This script configures Gunicorn to handle longer-running simulations.
"""

import os
import sys
import gunicorn.app.base

class StandaloneApplication(gunicorn.app.base.BaseApplication):
    """Custom Gunicorn application to configure and start the server."""
    
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        """Load the Gunicorn configuration."""
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        """Return the Flask application."""
        return self.application

if __name__ == '__main__':
    from main import app

    # Define server options with longer timeout for the worker
    options = {
        'bind': '0.0.0.0:5000',
        'workers': 1,
        'timeout': 180,  # 3 minutes (increased from default 30 seconds)
        'reload': True,
        'worker_class': 'sync',
        'loglevel': 'info',
        'reuse_port': True
    }

    # Start the server
    print(f"Starting Quantum Simulation server with {options['timeout']}s timeout...")
    StandaloneApplication(app, options).run()