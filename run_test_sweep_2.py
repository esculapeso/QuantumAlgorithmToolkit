"""
Script to test the parameter sweep functionality with proper database tracking.
This will verify the parameter sweep sessions are being tracked correctly.
"""
import os
import sys
import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app, db, run_parameter_sweep
from models import ParameterSweep

def test_parameter_sweep():
    """
    Run a test parameter sweep with 2 parameter dimensions.
    This will verify that the parameter sweep tracking is working correctly.
    """
    with app.app_context():
        # Check if we have any parameter sweeps already
        existing_sweeps = ParameterSweep.query.all()
        print(f"Found {len(existing_sweeps)} existing parameter sweeps")
        for sweep in existing_sweeps:
            print(f"  - {sweep.session_id}: {sweep.completed_simulations}/{sweep.total_simulations} simulations")
        
        # Create a test sweep with small parameter grid
        # Format: test_sweep_{circuit_type}_{timestamp}
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sweep_name = f"test_sweep_string_twistor_{timestamp}"
        
        print(f"\nCreating new test sweep: {sweep_name}")
        
        # Define the parameter grid (2x2 grid = 4 simulations)
        params = {
            "circuit_type": "string_twistor_fc",
            "qubits": [3, 4],
            "drive_param": [0.7, 0.8],
            "scan_name": sweep_name,
            "time_points": 50  # Use fewer time points for faster testing
        }
        
        # Run the parameter sweep
        run_parameter_sweep(**params)
        
        # Check that the sweep was created and tracked properly
        sweep = ParameterSweep.query.filter_by(session_id=sweep_name).first()
        if sweep:
            print(f"\nSweep created successfully: {sweep.session_id}")
            print(f"  - Circuit type: {sweep.circuit_type}")
            print(f"  - Parameters: {sweep.param1}, {sweep.param2}")
            print(f"  - Completion: {sweep.completed_simulations}/{sweep.total_simulations}")
        else:
            print("\nERROR: Sweep was not created in the database!")
            
        print("\nDone.")

if __name__ == "__main__":
    test_parameter_sweep()