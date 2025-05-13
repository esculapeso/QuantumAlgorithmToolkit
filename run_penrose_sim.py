"""
Script to run a Penrose circuit simulation with 4 qubits.
This script will test our modified circuit diagram generation code.
"""

from simulation import run_simulation

if __name__ == "__main__":
    print("===== Penrose Quantum Simulation =====")
    print("Running penrose simulation with 4 qubits...")
    
    result = run_simulation(
        "penrose", 
        qubits=4,
        shots=1024,
        time_points=100,
        init_state="superposition",
        save_results=True,
        show_plots=False,
        verbose=True
    )
    
    print("Simulation complete! Check the generated circuit diagram to verify it uses 1 drive step.")