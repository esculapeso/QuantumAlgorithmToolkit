"""
Script to run a test parameter sweep using the string_twistor_fc circuit type.
This will generate data that we can use to test the parameter sweep grid view.
"""
import os
import sys
import datetime
import numpy as np

# Add the current directory to sys.path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import generate_parameter_grid, run_sequential_simulations

def run_test_parameter_sweep():
    """Run a test parameter sweep with a 2D grid of parameters."""
    print("Running test parameter sweep...")
    
    # Create a timestamp for the sweep session name
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    sweep_name = f"string_twistor_sweep_{timestamp}"
    
    # Define parameter ranges for a 2D sweep (qubits x drive_param)
    param_ranges = {
        'qubits': [4, 6, 8],
        'drive_param': [0.7, 1.0, 1.3]
    }
    
    # Generate the parameter grid
    param_sets = generate_parameter_grid(**param_ranges)
    
    # Set constant parameters for all simulations
    for param_set in param_sets:
        param_set.update({
            'time_points': 100,
            'max_time': 10.0,
            'init_state': 'superposition',
            'shots': 8192,
            'drive_steps': 5
        })
    
    # Run the parameter sweep
    circuit_type = 'string_twistor_fc'  # Use the string twistor circuit
    run_sequential_simulations(
        circuit_type=circuit_type,
        parameter_sets=param_sets,
        scan_name=sweep_name
    )
    
    print(f"Test parameter sweep completed with name: {sweep_name}")
    print(f"View results at: /sweep_grid/{sweep_name}")

if __name__ == "__main__":
    run_test_parameter_sweep()