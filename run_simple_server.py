"""
Run a standalone server for quantum simulations.
"""

from simple_app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)