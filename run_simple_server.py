"""
Run script for the simplified quantum simulation app with no authentication or database.
"""
from noauth_app import app

if __name__ == "__main__":
    # Create the results directory if it doesn't exist
    import os
    os.makedirs('results', exist_ok=True)
    
    # Run the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)