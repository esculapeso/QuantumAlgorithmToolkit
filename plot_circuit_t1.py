#!/usr/bin/env python3
"""
Script to plot a quantum circuit at a specific time point (t=1.0).
This script generates a circuit using one of the available circuit types,
binds the time parameter to t=1.0, and saves the resulting circuit diagram.
"""

import os
import argparse
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Import custom modules
from quantum_circuits import (
    create_penrose_circuit,
    create_qft_basic_circuit,
    create_comb_generator_circuit,
    create_comb_twistor_circuit,
    create_graphene_fc_circuit,
    get_circuit_generator
)
from visualization import plot_circuit_diagram

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Plot quantum circuit at t=1.0')
    parser.add_argument('--circuit', '-c', type=str, default='penrose',
                      choices=['penrose', 'qft_basic', 'comb_generator', 'comb_twistor', 'graphene_fc'],
                      help='Type of quantum circuit to generate')
    parser.add_argument('--qubits', '-q', type=int, default=8,
                      help='Number of qubits in the circuit')
    parser.add_argument('--drive-steps', '-d', type=int, default=5,
                      help='Number of drive sequence repetitions')
    parser.add_argument('--drive-param', '-p', type=float, default=0.9,
                      help='Parameter controlling the drive strength')
    parser.add_argument('--init-state', '-i', type=str, default='superposition',
                      choices=['superposition', 'zero', 'one', 'plus', 'minus'],
                      help='Initial state specification')
    parser.add_argument('--output', '-o', type=str, default=None,
                      help='Output file path (default: auto-generated)')
    args = parser.parse_args()
    
    # Print parameters
    print(f"Generating {args.circuit} circuit with {args.qubits} qubits")
    print(f"Time point: t=1.0")
    
    # Get the appropriate circuit generator
    circuit_generator = get_circuit_generator(args.circuit)
    
    if not circuit_generator:
        print(f"Error: Unknown circuit type '{args.circuit}'")
        return
    
    # Generate the circuit with time parameter
    try:
        circuit, t = circuit_generator(
            args.qubits, 
            shots=1024, 
            drive_steps=args.drive_steps,
            init_state=args.init_state,
            drive_param=args.drive_param
        )
        print(f"Circuit generated with depth: {circuit.depth()}")
    except Exception as e:
        print(f"Error generating circuit: {e}")
        return
    
    # Bind the time parameter to t=1.0
    from qiskit.circuit import ParameterVector
    try:
        # Create parameter dictionary
        param_dict = {t: 1.0}
        # Bind the parameter
        bound_circuit = circuit.assign_parameters(param_dict)
        print(f"Successfully bound time parameter to t=1.0")
    except Exception as e:
        print(f"Error binding parameter: {e}")
        # Fall back to the original circuit if binding fails
        bound_circuit = circuit
        print("Using original parameterized circuit")
    
    # Create output directory if needed
    output_dir = 'figures'
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output file name if not provided
    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        # Create a custom file name for the t=1.0 circuit
        file_name = f"{args.circuit}_circuit_t1_{args.qubits}q_{timestamp}.png"
        output_path = os.path.join(output_dir, file_name)
    else:
        output_path = args.output
        # Get just the directory part
        if os.path.isfile(output_path):
            output_dir = os.path.dirname(output_path)
        else:
            output_dir = output_path
    
    # Plot and save the circuit diagram
    try:
        # Call the plot_circuit_diagram function with time_value=1.0
        # Note: The visualization function expects a directory as save_path
        # The plot_circuit_diagram function returns the filename if save_path is provided
        saved_file = plot_circuit_diagram(
            bound_circuit, 
            time_value=1.0,
            circuit_type=f"{args.circuit}_t1",  # Custom circuit type for the filename
            qubit_count=args.qubits, 
            save_path=output_dir
        )
        
        if saved_file and os.path.exists(saved_file):
            print(f"Circuit diagram saved to: {saved_file}")
        else:
            print(f"Circuit diagram may not have been saved correctly. Check {output_dir} directory.")
    except Exception as e:
        print(f"Error plotting circuit: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()