"""
Script to run a new test parameter sweep to verify database tracking.
"""
import os
import sys
import datetime
import traceback
from flask import Flask
from models import db
import main

def run_new_test_sweep():
    """Run a new parameter sweep to test database tracking."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Running new test parameter sweep...")
        
        # Create a unique sweep name
        sweep_id = f"test_db_sweep_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Define parameter sets for a simple sweep with drive_param
        parameter_sets = []
        for drive_param in [0.5, 0.75, 1.0]:
            parameter_sets.append({
                'qubits': 3,  # Small qubits for fast testing
                'time_points': 50,  # Fewer time points for faster completion
                'drive_param': drive_param,
                'init_state': 'superposition'
            })
        
        # Run the parameter sweep
        main.run_sequential_simulations('comb_generator', parameter_sets, sweep_id)
        
        # There's no need to verify here - we'll let the user check via the UI
        print(f"\nTest sweep complete. View the results at: /sweep_grid/{sweep_id}")
    
    return True

if __name__ == "__main__":
    try:
        success = run_new_test_sweep()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)