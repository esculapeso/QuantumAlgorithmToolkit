"""
Script to run a String Twistor Frequency Crystal circuit simulation.
This tests our new circuit implementation designed to produce frequency crystal patterns
based on concepts from string theory and twistor space.
"""

import os
import time
from simulation import run_simulation

def main():
    """Run a string twistor frequency crystal simulation."""
    print("Starting String Twistor Frequency Crystal simulation...")
    
    # Ensure results directory exists
    if not os.path.exists('results'):
        os.makedirs('results')
    
    # Default parameters
    circuit_type = 'string_twistor_fc'
    qubits = 8  # Use 8 qubits for a more complex system
    shots = 8192
    drive_steps = 5
    time_points = 300  # More time points for better frequency resolution
    max_time = 20.0  # Longer simulation time
    drive_param = 1.5  # Stronger drive parameter
    
    # Run the simulation
    start_time = time.time()
    
    result = run_simulation(
        circuit_type=circuit_type,
        qubits=qubits,
        shots=shots,
        drive_steps=drive_steps,
        time_points=time_points,
        max_time=max_time,
        drive_param=drive_param,
        init_state='superposition',
        save_results=True,
        show_plots=False,
        plot_circuit=True,
        verbose=True
    )
    
    elapsed_time = time.time() - start_time
    print(f"Simulation completed in {elapsed_time:.2f} seconds")
    
    # Print summary of results
    print("\nSimulation Results Summary:")
    print(f"Circuit Type: {circuit_type}")
    print(f"Qubits: {qubits}")
    print(f"Time Points: {time_points}")
    print(f"Drive Parameter: {drive_param}")
    
    # Check for time crystal detection
    if 'time_crystal_detected' in result:
        print(f"Time Crystal Detected: {result['time_crystal_detected']}")
    
    # Check for frequency comb detection
    if 'comb_detected' in result:
        print(f"Frequency Comb Detected: {result['comb_detected']}")
    
    # Print path to results
    if 'result_path' in result:
        print(f"Results saved to: {result['result_path']}")

if __name__ == "__main__":
    main()