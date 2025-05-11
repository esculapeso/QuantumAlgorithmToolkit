"""
Main module for quantum simulation package.
Entry point for running simulations with different parameters and web interface.
This module also exposes the necessary functions for the web interface.
"""

import os
import sys
import numpy as np

# Import custom modules
import config
from utils import ensure_dependencies
from quantum_circuits import get_circuit_generator
from simulation import run_simulation, run_parameter_scan, generate_parameter_grid
from visualization import plot_circuit_diagram

# Import Flask web application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import glob
import json

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "quantum-simulation-secret")

@app.route('/')
def index():
    """Render the main page."""
    # Get a list of recent simulation results
    results_dirs = sorted(glob.glob('results/*'), key=os.path.getmtime, reverse=True)
    recent_results = [os.path.basename(d) for d in results_dirs[:10]]  # Show 10 most recent
    
    # Available circuit types
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"}
    ]
    
    return render_template('index.html', 
                          recent_results=recent_results,
                          circuit_types=circuit_types,
                          default_params=config.DEFAULT_SIMULATION_PARAMS)

@app.route('/run_simulation', methods=['POST'])
def run_sim():
    """Run a simulation with the provided parameters."""
    try:
        # Extract parameters from form
        circuit_type = request.form.get('circuit_type')
        qubits = int(request.form.get('qubits', 3))
        shots = int(request.form.get('shots', 8192))
        drive_steps = int(request.form.get('drive_steps', 5))
        time_points = int(request.form.get('time_points', 100))
        max_time = float(request.form.get('max_time', 10.0))
        drive_param = float(request.form.get('drive_param', 0.9))
        init_state = request.form.get('init_state', 'superposition')
        
        # Run the simulation
        param_set_name = f"web_{circuit_type}_{qubits}q"
        result = run_simulation(
            circuit_type=circuit_type,
            qubits=qubits,
            shots=shots,
            drive_steps=drive_steps,
            time_points=time_points,
            max_time=max_time,
            drive_param=drive_param,
            init_state=init_state,
            param_set_name=param_set_name,
            save_results=True,
            show_plots=False,
            plot_circuit=True,
            verbose=True
        )
        
        # Get the result directory name
        results_path = result.get('results_path', '')
        result_name = os.path.basename(results_path) if results_path else None
        
        # Redirect to the result view
        if result_name:
            return redirect(url_for('view_result', result_name=result_name))
        else:
            flash('Simulation completed but result path not found.')
            return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'Error running simulation: {str(e)}')
        return redirect(url_for('index'))

@app.route('/result/<result_name>')
def view_result(result_name):
    """View a specific simulation result."""
    try:
        # Base path for this result
        result_path = os.path.join('results', result_name)
        
        # Load the saved result data
        with open(os.path.join(result_path, 'result_data.json'), 'r') as f:
            result_data = json.load(f)
        
        # Get list of figure files
        figure_files = glob.glob(os.path.join(result_path, 'figures', '*.png'))
        figures = [os.path.basename(f) for f in figure_files]
        
        # Get data about the time crystal and frequency comb detection
        time_crystal_detected = result_data.get('time_crystal_detected', False)
        incommensurate_count = result_data.get('incommensurate_count', 0)
        
        return render_template('result.html',
                             result_name=result_name,
                             figures=figures,
                             result_data=result_data,
                             time_crystal_detected=time_crystal_detected,
                             incommensurate_count=incommensurate_count)
    
    except Exception as e:
        flash(f'Error viewing result: {str(e)}')
        return redirect(url_for('index'))

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    return redirect(url_for('static', filename=f'../results/{result_name}/figures/{figure_name}'))

def main():
    """Main function to run simulations."""
    # Check required dependencies
    ensure_dependencies()
    print("\n===== Quantum Simulation Package =====")
    print("Note: Some features may be limited based on available packages")
    
    # Default parameters
    circuit_type = 'graphene_fc'  # Options: 'penrose', 'qft_basic', 'comb_generator', 'comb_twistor', 'graphene_fc'
    qubits = 3
    shots = 8192
    drive_steps = 5
    time_points = 100
    max_time = 10.0
    drive_param = 0.9
    init_state = 'superposition'
    
    # Check if user provided command-line arguments
    if len(sys.argv) > 1:
        # Simple command-line argument processing
        for i in range(1, len(sys.argv)):
            arg = sys.argv[i]
            if arg.startswith('--'):
                param = arg[2:]
                if param == 'circuit' and i+1 < len(sys.argv):
                    circuit_type = sys.argv[i+1]
                elif param == 'qubits' and i+1 < len(sys.argv):
                    qubits = int(sys.argv[i+1])
                elif param == 'drive_steps' and i+1 < len(sys.argv):
                    drive_steps = int(sys.argv[i+1])
                elif param == 'max_time' and i+1 < len(sys.argv):
                    max_time = float(sys.argv[i+1])
                elif param == 'time_points' and i+1 < len(sys.argv):
                    time_points = int(sys.argv[i+1])
                elif param == 'param_scan':
                    # Run a parameter scan instead of a single simulation
                    run_example_parameter_scan()
                    return
                elif param == 'web':
                    # Run the web interface
                    app.run(host='0.0.0.0', port=5000, debug=True)
                    return
    
    print(f"Running {circuit_type} simulation with {qubits} qubits...")
    
    # Run a single simulation with the specified parameters
    result = run_simulation(
        circuit_type=circuit_type,
        qubits=qubits,
        shots=shots,
        drive_steps=drive_steps,
        time_points=time_points,
        max_time=max_time,
        drive_param=drive_param,
        init_state=init_state,
        param_set_name=f"cli_run_{qubits}q",
        save_results=True,
        show_plots=True,
        plot_circuit=True,
        verbose=True
    )
    
    # Print key results
    if 'error' in result:
        print(f"Simulation error: {result['error']}")
    else:
        print("\nSimulation completed successfully!")
        print(f"Drive frequency: {result['analysis'].get('drive_frequency', 0):.4f}")
        print(f"Time crystal detected: {result['analysis'].get('has_subharmonics', False)}")
        print(f"Incommensurate frequencies detected: {result['fc_analysis'].get('incommensurate_peak_count', 0)}")
        
        # Check for frequency combs
        mx_comb = result['comb_analysis'].get('mx_comb_found', False)
        mz_comb = result['comb_analysis'].get('mz_comb_found', False)
        if mx_comb or mz_comb:
            print("\nFrequency comb structures detected:")
            if mx_comb:
                print(f"  X component: Omega={result['comb_analysis'].get('mx_best_omega', 0):.4f}, "
                      f"Teeth={result['comb_analysis'].get('mx_num_teeth', 0)}")
            if mz_comb:
                print(f"  Z component: Omega={result['comb_analysis'].get('mz_best_omega', 0):.4f}, "
                      f"Teeth={result['comb_analysis'].get('mz_num_teeth', 0)}")
        
        # Check for logarithmic combs
        mx_log_comb = result['log_comb_analysis'].get('mx_log_comb_found', False)
        mz_log_comb = result['log_comb_analysis'].get('mz_log_comb_found', False)
        if mx_log_comb or mz_log_comb:
            print("\nLogarithmic frequency comb structures detected:")
            if mx_log_comb:
                print(f"  X component: R={result['log_comb_analysis'].get('mx_best_r', 0):.4f}, "
                      f"Base={result['log_comb_analysis'].get('mx_base_freq', 0):.4f}, "
                      f"Teeth={result['log_comb_analysis'].get('mx_log_num_teeth', 0)}")
            if mz_log_comb:
                print(f"  Z component: R={result['log_comb_analysis'].get('mz_best_r', 0):.4f}, "
                      f"Base={result['log_comb_analysis'].get('mz_base_freq', 0):.4f}, "
                      f"Teeth={result['log_comb_analysis'].get('mz_log_num_teeth', 0)}")

def run_example_parameter_scan():
    """Run an example parameter scan with a grid of parameters."""
    print("Running parameter scan...")
    
    # Define parameter ranges to scan
    param_ranges = {
        'qubits': [2, 3, 4],
        'drive_steps': [4, 6],
        'drive_param': [0.7, 0.9, 1.1]
    }
    
    # Generate the parameter grid
    param_sets = generate_parameter_grid(**param_ranges)
    
    # Set constant parameters
    for params in param_sets:
        params.update({
            'time_points': 100,
            'max_time': 10.0,
            'init_state': 'superposition',
            'shots': 8192
        })
    
    # Run the parameter scan
    circuit_type = 'comb_generator'  # Use a circuit designed for frequency combs
    results = run_parameter_scan(
        circuit_type=circuit_type,
        parameter_sets=param_sets,
        scan_name="example_grid_scan",
        save_results=True,
        show_plots=False,
        verbose=True
    )
    
    print(f"Parameter scan completed. Processed {len(results)} parameter sets.")

if __name__ == "__main__":
    main()
