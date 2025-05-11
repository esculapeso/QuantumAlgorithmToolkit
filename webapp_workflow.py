"""
Script to start the quantum simulation web application.
"""

from subprocess import run

if __name__ == "__main__":
    # Start the web application with gunicorn
    run(["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "app:app"], check=True)