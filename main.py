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
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
import glob
import json

# Import database models
from models import db, SimulationResult, FrequencyPeak, CombStructure

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "quantum-simulation-secret")

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the database
db.init_app(app)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    """Render the main page."""
    # Get a list of recent simulation results from the database
    try:
        from db_utils import get_recent_simulations
        recent_db_results = get_recent_simulations(limit=10)
        recent_results = [sim.result_name for sim in recent_db_results]
    except Exception as e:
        # Fall back to file system if database fails
        print(f"Warning: Could not fetch from database: {e}")
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

import threading
import uuid
import time
import json

# Dictionary to store background simulation status
BACKGROUND_SIMULATIONS = {}

@app.route('/run_simulation', methods=['POST'])
def run_simulation():
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
        
        # Determine if this is an AJAX request
        is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                  request.content_type == 'application/json' or
                  request.args.get('format') == 'json')
        
        # For simulations with more than 500 time points or more than 5 qubits,
        # run in background to avoid timeouts
        if time_points > 500 or qubits > 5:
            # Generate a unique ID for this simulation
            sim_id = str(uuid.uuid4())
            
            # Create parameter dict for the simulation
            params = {
                'circuit_type': circuit_type,
                'qubits': qubits,
                'shots': shots,
                'drive_steps': drive_steps,
                'time_points': time_points,
                'max_time': max_time,
                'drive_param': drive_param,
                'init_state': init_state,
                'param_set_name': f"web_{circuit_type}_{qubits}q_{sim_id[:6]}",
            }
            
            # Store simulation status
            BACKGROUND_SIMULATIONS[sim_id] = {
                'id': sim_id,
                'params': params,
                'status': 'starting',
                'progress': 0,
                'start_time': time.time(),
                'result_path': None,
                'error': None,
                'message': 'Initializing simulation...',
            }
            
            # Start background thread for simulation
            thread = threading.Thread(
                target=run_background_simulation,
                args=(sim_id, params)
            )
            thread.daemon = True
            thread.start()
            
            if is_ajax:
                # Return JSON response for AJAX requests
                return jsonify({
                    'status': 'pending',
                    'simulation_id': sim_id,
                    'message': 'Simulation started in the background'
                })
            else:
                # Regular form submission - redirect to the simulations page
                flash(f'Long simulation started in background. You can check its progress on the simulations page.')
                return redirect(url_for('view_simulations'))
        
        # For smaller simulations, run synchronously as before
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
        
        if is_ajax:
            # Return JSON response for AJAX requests
            if result_name:
                return jsonify({
                    'status': 'completed',
                    'result_name': result_name,
                    'message': 'Simulation completed successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'error': 'Simulation completed but result path not found'
                })
        else:
            # Regular form submission - redirect to the result view
            if result_name:
                return redirect(url_for('view_result', result_name=result_name))
            else:
                flash('Simulation completed but result path not found.')
                return redirect(url_for('index'))
        
    except Exception as e:
        error_message = f'Error running simulation: {str(e)}'
        print(f"Simulation error: {error_message}")
        
        # Determine if this is an AJAX request
        is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                  request.content_type == 'application/json' or
                  request.args.get('format') == 'json')
        
        if is_ajax:
            return jsonify({
                'status': 'error',
                'error': error_message
            })
        else:
            flash(error_message)
            return redirect(url_for('index'))

def run_background_simulation(sim_id, params):
    """Run a simulation in the background and update its status."""
    try:
        # Update status to running
        BACKGROUND_SIMULATIONS[sim_id]['status'] = 'running'
        
        # Create a progress callback to update progress
        def progress_callback(step, total):
            progress = int((step / total) * 100)
            BACKGROUND_SIMULATIONS[sim_id]['progress'] = progress
        
        # Import run_simulation here to avoid circular imports
        from simulation import run_simulation
        
        # Run the simulation with the progress callback
        result = run_simulation(
            circuit_type=params['circuit_type'],
            qubits=params['qubits'],
            shots=params['shots'],
            drive_steps=params['drive_steps'],
            time_points=params['time_points'],
            max_time=params['max_time'],
            drive_param=params['drive_param'],
            init_state=params['init_state'],
            param_set_name=params['param_set_name'],
            save_results=True,
            show_plots=False,
            plot_circuit=True,
            verbose=True,
            progress_callback=progress_callback
        )
        
        # Update simulation status with the result path
        results_path = result.get('results_path', '')
        result_name = os.path.basename(results_path) if results_path else None
        
        BACKGROUND_SIMULATIONS[sim_id]['status'] = 'completed'
        BACKGROUND_SIMULATIONS[sim_id]['result_path'] = result_name
        BACKGROUND_SIMULATIONS[sim_id]['end_time'] = time.time()
        
    except Exception as e:
        # If an error occurs, store it in the simulation status
        BACKGROUND_SIMULATIONS[sim_id]['status'] = 'error'
        BACKGROUND_SIMULATIONS[sim_id]['error'] = str(e)
        BACKGROUND_SIMULATIONS[sim_id]['end_time'] = time.time()

@app.route('/simulations')
def view_simulations():
    """View the status of all simulations."""
    # Get filter parameters
    circuit_type = request.args.get('circuit_type')
    min_qubits = request.args.get('min_qubits', type=int)
    max_qubits = request.args.get('max_qubits', type=int)
    time_crystal = request.args.get('time_crystal') == 'true'
    comb_detected = request.args.get('comb_detected') == 'true'
    
    # Only apply filters if they're provided
    filters = {}
    if circuit_type:
        filters['circuit_type'] = circuit_type
    if min_qubits is not None:
        filters['min_qubits'] = min_qubits
    if max_qubits is not None:
        filters['max_qubits'] = max_qubits
    if request.args.get('time_crystal'):
        filters['time_crystal_detected'] = time_crystal
    if request.args.get('comb_detected'):
        filters['comb_detected'] = comb_detected
    
    # Get background jobs (in-progress simulations)
    background_jobs = []
    for sim_id, sim_data in BACKGROUND_SIMULATIONS.items():
        background_jobs.append({
            'id': sim_id,
            'circuit_type': sim_data['params']['circuit_type'],
            'qubits': sim_data['params']['qubits'],
            'time_points': sim_data['params']['time_points'],
            'status': sim_data['status'],
            'progress': sim_data['progress'],
            'is_background_job': True
        })
    
    # Get database results
    try:
        from db_utils import search_simulations, get_recent_simulations
        
        # Get simulation results
        if filters:
            db_simulations = search_simulations(**filters)
        else:
            db_simulations = get_recent_simulations(limit=50)
            
        # Combine background jobs with database results
        return render_template('simulations.html',
                            simulations=db_simulations,
                            background_jobs=background_jobs)
    except Exception as e:
        # Fall back to file system if database fails
        print(f"Warning: Could not fetch from database: {e}")
        results_dirs = sorted(glob.glob('results/*'), key=os.path.getmtime, reverse=True)
        recent_results = [os.path.basename(d) for d in results_dirs[:10]]
        
        return render_template('simulations.html',
                            simulations=[],
                            background_jobs=background_jobs,
                            recent_results=recent_results,
                            db_error=str(e))

@app.route('/simulation_status/<sim_id>')
def simulation_status(sim_id):
    """Get the status of a specific simulation."""
    if sim_id in BACKGROUND_SIMULATIONS:
        return jsonify(BACKGROUND_SIMULATIONS[sim_id])
    else:
        return jsonify({'error': 'Simulation not found'}), 404

@app.route('/result/<result_name>')
def view_result(result_name):
    """View a specific simulation result."""
    try:
        # First try to get simulation from database
        try:
            from db_utils import get_simulation_by_name
            db_result = get_simulation_by_name(result_name)
            
            if db_result:
                # Result exists in database, use database data
                result_path = db_result.results_path
                
                # Get list of figure files - check figures folder
                figure_files = glob.glob(os.path.join(result_path, 'figures', '*.png'))
                if not figure_files:
                    # As a fallback, check if there are figures directly in the result path
                    figure_files = glob.glob(os.path.join(result_path, '*.png'))
                figures = [os.path.basename(f) for f in figure_files]
                
                # Build a result data structure from database
                result_data = {
                    'parameters': {
                        'circuit_type': db_result.circuit_type,
                        'qubits': db_result.qubits,
                        'shots': db_result.shots,
                        'drive_steps': db_result.drive_steps,
                        'time_points': db_result.time_points,
                        'max_time': db_result.max_time,
                        'drive_param': db_result.drive_param,
                        'init_state': db_result.init_state
                    },
                    'time_crystal_detected': db_result.time_crystal_detected,
                    'incommensurate_count': db_result.incommensurate_count,
                    'drive_frequency': db_result.drive_frequency,
                    'linear_combs_detected': db_result.linear_combs_detected,
                    'log_combs_detected': db_result.log_combs_detected
                }
                
                # Get extra data if available
                try:
                    extra_data = db_result.get_extra_data()
                    result_data.update(extra_data)
                except:
                    pass
                
                # Render the template with database data
                return render_template('result.html',
                                     result_name=result_name,
                                     figures=figures,
                                     result_data=result_data,
                                     time_crystal_detected=db_result.time_crystal_detected,
                                     incommensurate_count=db_result.incommensurate_count,
                                     from_database=True)
        except Exception as db_error:
            print(f"Could not retrieve from database: {db_error}")
            # Continue to file-based method if database retrieval fails
        
        # Base path for this result if not from database
        result_path = os.path.join('results', result_name)
        
        # Create result_data.json if it doesn't exist (for backward compatibility)
        result_data_path = os.path.join(result_path, 'result_data.json')
        if not os.path.exists(result_data_path):
            # Try to build from analysis results
            analysis_path = os.path.join(result_path, 'data', 'analysis_results.json')
            if os.path.exists(analysis_path):
                with open(analysis_path, 'r') as f:
                    analysis = json.load(f)
                result_data = {
                    'parameters': analysis.get('parameters', {}),
                    'time_crystal_detected': analysis.get('basic_analysis', {}).get('has_subharmonics', False),
                    'incommensurate_count': analysis.get('frequency_crystal_analysis', {}).get('incommensurate_peak_count', 0),
                    'drive_frequency': analysis.get('basic_analysis', {}).get('drive_frequency', 0.0)
                }
            else:
                # Default empty data
                result_data = {'parameters': {}, 'time_crystal_detected': False, 'incommensurate_count': 0}
        else:
            # Load the saved result data 
            with open(result_data_path, 'r') as f:
                result_data = json.load(f)
        
        # Get list of figure files - check figures folder
        figure_files = glob.glob(os.path.join(result_path, 'figures', '*.png'))
        if not figure_files:
            # As a fallback, check if there are figures directly in the result path
            figure_files = glob.glob(os.path.join(result_path, '*.png'))
        figures = [os.path.basename(f) for f in figure_files]
        
        # Get data about the time crystal and frequency comb detection
        time_crystal_detected = result_data.get('time_crystal_detected', False)
        incommensurate_count = result_data.get('incommensurate_count', 0)
        
        return render_template('result.html',
                             result_name=result_name,
                             figures=figures,
                             result_data=result_data,
                             time_crystal_detected=time_crystal_detected,
                             incommensurate_count=incommensurate_count,
                             from_database=False)
    
    except Exception as e:
        flash(f'Error viewing result: {str(e)}')
        return redirect(url_for('index'))

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    # First check if result is in database
    try:
        from db_utils import get_simulation_by_name
        db_result = get_simulation_by_name(result_name)
        
        if db_result and db_result.results_path:
            result_path = db_result.results_path
            
            # Check in figures subfolder first
            figure_path = os.path.join(result_path, 'figures', figure_name)
            if os.path.exists(figure_path):
                return send_file(figure_path)
            
            # Check directly in results path as fallback
            figure_path = os.path.join(result_path, figure_name)
            if os.path.exists(figure_path):
                return send_file(figure_path)
    except Exception as e:
        print(f"Error retrieving figure from database: {e}")
    
    # Fall back to default locations if not found in database
    
    # Try finding in the figures subfolder
    figure_path = os.path.join('results', result_name, 'figures', figure_name)
    if os.path.exists(figure_path):
        return send_file(figure_path)
    
    # Try finding directly in the results folder
    figure_path = os.path.join('results', result_name, figure_name)
    if os.path.exists(figure_path):
        return send_file(figure_path)
    
    # If all fails, return a 404
    return f"Figure {figure_name} not found", 404

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
