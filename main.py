"""
Main module for quantum simulation package.
Entry point for running simulations with different parameters and web interface.
This module also exposes the necessary functions for the web interface.
"""

import os
import sys
import numpy as np
import datetime
import traceback
import threading
import uuid
import time

# Import custom modules
import config
from utils import ensure_dependencies
from quantum_circuits import get_circuit_generator
from simulation import run_parameter_scan, generate_parameter_grid
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

# Define a custom error handler for 500 errors
@app.errorhandler(500)
def internal_server_error(error):
    """
    Custom error handler for 500 errors to ensure API routes still return JSON.
    """
    # Check if this is an AJAX/API request
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
              request.content_type == 'application/json' or
              request.args.get('format') == 'json' or
              request.path.startswith('/simulation_status/') or
              request.path == '/run_simulation')
    
    if is_ajax:
        # Return JSON for API routes
        return jsonify({
            'status': 'error',
            'error': 'Internal server error occurred. The server may have timed out.'
        }), 500, {'Content-Type': 'application/json'}
    else:
        # For regular HTML routes, rethrow the original error
        return render_template('error.html', error=str(error)), 500

# Define a custom error handler for 404 errors
@app.errorhandler(404)
def page_not_found(error):
    """
    Custom error handler for 404 errors to ensure API routes still return JSON.
    """
    # Check if this is an AJAX/API request
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
              request.content_type == 'application/json' or
              request.args.get('format') == 'json' or
              request.path.startswith('/simulation_status/'))
    
    if is_ajax:
        # Return JSON for API routes
        return jsonify({
            'status': 'error',
            'error': 'Resource not found'
        }), 404, {'Content-Type': 'application/json'}
    else:
        # For regular HTML routes, use the default behavior
        return render_template('error.html', error="Page not found"), 404
        
# Define a custom error handler for general exceptions
@app.errorhandler(Exception)
def handle_exception(error):
    """
    Custom error handler to catch unhandled exceptions and ensure API routes return JSON.
    """
    # Log the error
    app.logger.error(f"Unhandled exception: {str(error)}")
    app.logger.error(traceback.format_exc())
    
    # Check if this is an AJAX/API request
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
              request.content_type == 'application/json' or
              request.args.get('format') == 'json' or
              request.path.startswith('/simulation_status/') or
              request.path == '/run_simulation')
    
    if is_ajax:
        # Always return JSON for API routes
        return jsonify({
            'status': 'error',
            'error': str(error) or "An unexpected error occurred"
        }), 500, {'Content-Type': 'application/json'}
    else:
        # For regular HTML routes, render an error template
        return render_template('error.html', error=str(error)), 500

@app.route('/')
def index():
    """Render the main page."""
    # Get a list of recent simulation results from the database
    latest_result = None
    latest_figures = []
    latest_result_data = {}
    time_crystal_detected = False
    incommensurate_count = 0
    
    try:
        from db_utils import get_recent_simulations, get_simulation_by_name
        # Get the most recent simulation
        db_results = get_recent_simulations(limit=10)
        
        if db_results and len(db_results) > 0:
            latest_db_result = db_results[0]
            latest_result = latest_db_result.result_name
            
            # Get the detailed data for the latest result
            result_name = latest_result
            result_path = f"results/{result_name}"
            
            if os.path.exists(result_path):
                # Look for analysis.json or result_data.json
                analysis_path = os.path.join(result_path, 'analysis.json')
                result_data_path = os.path.join(result_path, 'result_data.json')
                
                if os.path.exists(analysis_path):
                    with open(analysis_path, 'r') as f:
                        analysis = json.load(f)
                    latest_result_data = {
                        'parameters': analysis.get('parameters', {}),
                        'time_crystal_detected': analysis.get('basic_analysis', {}).get('has_subharmonics', False),
                        'incommensurate_count': analysis.get('frequency_crystal_analysis', {}).get('incommensurate_peak_count', 0),
                        'drive_frequency': analysis.get('basic_analysis', {}).get('drive_frequency', 0.0)
                    }
                elif os.path.exists(result_data_path):
                    # Load the saved result data 
                    with open(result_data_path, 'r') as f:
                        latest_result_data = json.load(f)
                
                # Get list of figure files
                figure_files = glob.glob(os.path.join(result_path, 'figures', '*.png'))
                if not figure_files:
                    # As a fallback, check if there are figures directly in the result path
                    figure_files = glob.glob(os.path.join(result_path, '*.png'))
                latest_figures = [os.path.basename(f) for f in figure_files]
                
                # Get data about the time crystal and frequency comb detection
                time_crystal_detected = latest_result_data.get('time_crystal_detected', False)
                incommensurate_count = latest_result_data.get('incommensurate_count', 0)
    
    except Exception as e:
        # Fall back to file system if database fails
        print(f"Warning: Could not fetch latest result details: {e}")
        traceback.print_exc()
    
    # Available circuit types
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"}
    ]
    
    return render_template('index.html', 
                          latest_result=latest_result,
                          latest_figures=latest_figures,
                          latest_result_data=latest_result_data,
                          time_crystal_detected=time_crystal_detected,
                          incommensurate_count=incommensurate_count,
                          circuit_types=circuit_types,
                          default_params=config.DEFAULT_SIMULATION_PARAMS)
                          
@app.route('/parameter_sweep')
def parameter_sweep():
    """Render the parameter sweep page."""
    # Available circuit types
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"}
    ]
    
    # Current timestamp for default scan name
    now = datetime.datetime.now()
    
    return render_template('parameter_sweep.html',
                          circuit_types=circuit_types,
                          now=now,
                          default_params=config.DEFAULT_SIMULATION_PARAMS)
                          
@app.route('/run_parameter_sweep', methods=['POST'])
def run_parameter_sweep():
    """Run a parameter sweep with the provided parameters."""
    # Extract base configuration
    circuit_type = request.form.get('circuit_type')
    scan_name = request.form.get('scan_name', f'param_sweep_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}')
    init_state = request.form.get('init_state', 'superposition')
    
    # Parameter ranges and steps
    param_ranges = {}
    
    # Process each parameter that could be swept
    params = [
        {'name': 'qubits', 'type': int, 'min': 1, 'max': 10},
        {'name': 'shots', 'type': int, 'min': 1, 'max': 20000},
        {'name': 'drive_steps', 'type': int, 'min': 1, 'max': 20},
        {'name': 'drive_param', 'type': float, 'min': 0.1, 'max': 2.0},
        {'name': 'time_points', 'type': int, 'min': 10, 'max': 10000},
        {'name': 'max_time', 'type': float, 'min': 1.0, 'max': 50.0}
    ]
    
    # For each parameter, check if it's being swept
    for param in params:
        name = param['name']
        param_type = param['type']
        
        if request.form.get(f'sweep_{name}') == 'on':
            # Parameter is being swept, get min, max, and steps
            min_val = param_type(float(request.form.get(f'{name}_min', param['min'])))
            max_val = param_type(float(request.form.get(f'{name}_max', param['max'])))
            steps = int(request.form.get(f'{name}_steps', 3))
            
            # Generate the range values
            if param_type == int:
                # For integers, ensure we get the right number of steps
                if steps <= 1:
                    # Only one value in range
                    values = [min_val]
                else:
                    # Generate evenly spaced integer values
                    step_size = (max_val - min_val) / (steps - 1)
                    values = [int(min_val + i * step_size) for i in range(steps)]
                    # Ensure unique values
                    values = sorted(list(set(values)))
            else:
                # For floats, use numpy linspace
                values = np.linspace(min_val, max_val, steps).tolist()
            
            param_ranges[name] = values
        else:
            # Parameter is fixed, use the single value
            fixed_val = param_type(float(request.form.get(name, param['min'])))
            param_ranges[name] = [fixed_val]
    
    # Generate all parameter combinations
    parameter_sets = generate_parameter_grid(**param_ranges)
    
    # Add init_state to each parameter set
    for param_set in parameter_sets:
        param_set['init_state'] = init_state
    
    # Calculate if this will run in background
    large_simulation = False
    total_combinations = len(parameter_sets)
    
    if total_combinations > 1:
        large_simulation = True
    
    # If this is going to be a large simulation, run in background
    if large_simulation:
        # Generate a unique ID for this background job
        scan_id = str(uuid.uuid4())
        
        # Create a record of the background job FIRST before starting the thread
        BACKGROUND_SIMULATIONS[scan_id] = {
            'status': 'starting',
            'params': {
                'circuit_type': circuit_type,
                'parameter_sets': f"{total_combinations} parameter combinations",
                'scan_name': scan_name
            },
            'progress': 0,
            'start_time': time.time(),
            'message': f'Starting parameter sweep with {total_combinations} combinations'
        }
        
        # Now start the background thread after the dictionary entry is ready
        sweep_thread = threading.Thread(
            target=run_background_parameter_sweep,
            args=(scan_id, circuit_type, parameter_sets, scan_name)
        )
        sweep_thread.daemon = True
        sweep_thread.start()
        
        # Redirect to simulations page to monitor progress
        return redirect(url_for('view_simulations'))
    else:
        # For a single parameter set, just run it directly
        try:
            # Run the simulation with the provided parameters
            from simulation import run_simulation
            
            # Get the first (and only) parameter set
            param_set = parameter_sets[0]
            
            # Run the simulation
            result = run_simulation(
                circuit_type=circuit_type,
                qubits=param_set.get('qubits', 3),
                shots=param_set.get('shots', 8192),
                drive_steps=param_set.get('drive_steps', 5),
                time_points=param_set.get('time_points', 100),
                max_time=param_set.get('max_time', 10.0),
                drive_param=param_set.get('drive_param', 0.9),
                init_state=param_set.get('init_state', 'superposition'),
                param_set_name=scan_name,
                save_results=True,
                show_plots=False
            )
            
            # Get the result path to redirect to
            result_path = result.get('result_path', '').split('/')[-1]
            
            # Redirect to the result page
            return redirect(url_for('view_result', result_name=result_path))
        except Exception as e:
            print(f"Error running simulation: {str(e)}")
            traceback.print_exc()
            flash(f"Error running simulation: {str(e)}", 'error')
            return redirect(url_for('parameter_sweep'))
            
def run_background_parameter_sweep(sweep_id, circuit_type, parameter_sets, scan_name):
    """Run a parameter sweep in the background and update its status."""
    try:
        # Verify the sweep_id exists in BACKGROUND_SIMULATIONS
        if sweep_id not in BACKGROUND_SIMULATIONS:
            print(f"Error: sweep_id {sweep_id} not found in BACKGROUND_SIMULATIONS")
            # Create the entry if it doesn't exist
            BACKGROUND_SIMULATIONS[sweep_id] = {
                'status': 'starting',
                'params': {
                    'circuit_type': circuit_type,
                    'parameter_sets': f"{len(parameter_sets)} parameter combinations",
                    'scan_name': scan_name
                },
                'progress': 0,
                'start_time': time.time(),
                'message': f'Starting parameter sweep with {len(parameter_sets)} combinations'
            }
            
        # Update status to running
        BACKGROUND_SIMULATIONS[sweep_id]['status'] = 'running'
        BACKGROUND_SIMULATIONS[sweep_id]['message'] = 'Parameter sweep in progress'
        
        # Count of total parameter sets
        total_sets = len(parameter_sets)
        
        # Run the parameter scan
        results = []
        for i, param_set in enumerate(parameter_sets):
            # Update progress
            progress = int((i / total_sets) * 100)
            BACKGROUND_SIMULATIONS[sweep_id]['progress'] = progress
            BACKGROUND_SIMULATIONS[sweep_id]['message'] = f'Processing combination {i+1}/{total_sets} ({progress}%)'
            
            # Generate a unique name for this parameter set
            # Include some key parameter values in the name
            qubits = param_set.get('qubits', 3)
            time_points = param_set.get('time_points', 100)
            drive_param = param_set.get('drive_param', 0.9)
            param_suffix = f"{qubits}q_{time_points}tp_d{drive_param:.1f}"
            
            param_set_name = f"{scan_name}_{i+1}_{param_suffix}"
            
            try:
                # Run the simulation
                from simulation import run_simulation
                result = run_simulation(
                    circuit_type=circuit_type,
                    qubits=param_set.get('qubits', 3),
                    shots=param_set.get('shots', 8192),
                    drive_steps=param_set.get('drive_steps', 5),
                    time_points=param_set.get('time_points', 100),
                    max_time=param_set.get('max_time', 10.0),
                    drive_param=param_set.get('drive_param', 0.9),
                    init_state=param_set.get('init_state', 'superposition'),
                    param_set_name=param_set_name,
                    save_results=True,
                    show_plots=False
                )
                results.append(result)
            except Exception as e:
                print(f"Error running parameter set {i+1}/{total_sets}: {str(e)}")
                traceback.print_exc()
                # Continue with next parameter set
        
        # Update status to completed
        BACKGROUND_SIMULATIONS[sweep_id]['status'] = 'complete'
        BACKGROUND_SIMULATIONS[sweep_id]['progress'] = 100
        BACKGROUND_SIMULATIONS[sweep_id]['message'] = f'Parameter sweep completed with {len(results)} successful simulations'
        BACKGROUND_SIMULATIONS[sweep_id]['end_time'] = time.time()
        BACKGROUND_SIMULATIONS[sweep_id]['result_count'] = len(results)
        
    except Exception as e:
        # If an error occurs, store it in the simulation status
        error_traceback = traceback.format_exc()
        print(f"Background parameter sweep error: {str(e)}")
        print(error_traceback)  # Print full traceback for debugging
        
        # Ensure the simulation entry exists before trying to update it
        if sweep_id not in BACKGROUND_SIMULATIONS:
            BACKGROUND_SIMULATIONS[sweep_id] = {
                'status': 'error',
                'params': {
                    'circuit_type': circuit_type,
                    'parameter_sets': f"{len(parameter_sets)} parameter combinations",
                    'scan_name': scan_name
                },
                'progress': 0,
                'start_time': time.time(),
                'error': str(e),
                'message': 'Error occurred during parameter sweep',
                'end_time': time.time()
            }
        else:
            BACKGROUND_SIMULATIONS[sweep_id]['status'] = 'error'
            BACKGROUND_SIMULATIONS[sweep_id]['error'] = str(e)
            BACKGROUND_SIMULATIONS[sweep_id]['message'] = 'Error occurred during parameter sweep'
            BACKGROUND_SIMULATIONS[sweep_id]['end_time'] = time.time()



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
        
        # For simulations with more than 100 time points or more than 3 qubits,
        # run in background to avoid timeouts
        if time_points > 100 or qubits > 3:
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
        
        # Import here to avoid circular imports
        from simulation import run_simulation
        
        # Generate a unique random seed for this run
        import random
        unique_seed = random.randint(10000, 99999)
        
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
            verbose=True,
            seed=unique_seed
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
        # Print traceback for debugging
        print(traceback.format_exc())
        
        # Always return JSON for this endpoint - frontend expects it
        # Make sure there's no HTML in the response
        return jsonify({
            'status': 'error',
            'error': error_message
        }), 500, {'Content-Type': 'application/json'}

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
        
        # Generate a unique random seed for this run
        import random
        unique_seed = random.randint(10000, 99999)
        
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
            progress_callback=progress_callback,
            seed=unique_seed
        )
        
        # Update simulation status with the result path
        results_path = result.get('results_path', '')
        result_name = os.path.basename(results_path) if results_path else None
        
        # Ensure progress is set to 100% when completed
        BACKGROUND_SIMULATIONS[sim_id]['progress'] = 100
        BACKGROUND_SIMULATIONS[sim_id]['status'] = 'completed'
        BACKGROUND_SIMULATIONS[sim_id]['result_path'] = result_name
        BACKGROUND_SIMULATIONS[sim_id]['end_time'] = time.time()
        BACKGROUND_SIMULATIONS[sim_id]['message'] = 'Simulation completed successfully'
        
        # Log completion
        print(f"Background simulation {sim_id} completed successfully")
        
    except Exception as e:
        # If an error occurs, store it in the simulation status
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Background simulation error: {str(e)}")
        print(error_traceback)  # Print full traceback for debugging
        
        BACKGROUND_SIMULATIONS[sim_id]['status'] = 'error'
        BACKGROUND_SIMULATIONS[sim_id]['error'] = str(e)
        BACKGROUND_SIMULATIONS[sim_id]['message'] = 'Error occurred during simulation'
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
        try:
            params = sim_data.get('params', {})
            job_info = {
                'id': sim_id,
                'circuit_type': params.get('circuit_type', 'unknown'),
                'status': sim_data.get('status', 'unknown'),
                'progress': sim_data.get('progress', 0),
                'is_background_job': True
            }
            
            # Parameter sweep might store info differently
            if 'parameter_sets' in params:
                job_info['qubits'] = 'multiple'
                job_info['time_points'] = 'multiple'
                job_info['circuit_type'] = f"{params.get('circuit_type', 'unknown')} (sweep)"
            else:
                job_info['qubits'] = params.get('qubits', 'unknown')
                job_info['time_points'] = params.get('time_points', 'unknown')
                
            background_jobs.append(job_info)
        except Exception as e:
            print(f"Error processing background job {sim_id}: {str(e)}")
    
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
    try:
        if sim_id in BACKGROUND_SIMULATIONS:
            return jsonify(BACKGROUND_SIMULATIONS[sim_id]), 200, {'Content-Type': 'application/json'}
        else:
            return jsonify({'error': 'Simulation not found', 'status': 'error'}), 404, {'Content-Type': 'application/json'}
    except Exception as e:
        # Print traceback for debugging
        error_traceback = traceback.format_exc()
        print(f"Status check error: {str(e)}")
        print(error_traceback)
        
        # Ensure we always return valid JSON even on unexpected errors
        return jsonify({
            'error': f'Error checking simulation status: {str(e)}',
            'status': 'error'
        }), 500, {'Content-Type': 'application/json'}

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
    
    # Import here to avoid circular imports
    from simulation import run_simulation
    
    # Generate a unique random seed for this run
    import random
    unique_seed = random.randint(10000, 99999)
    
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
        verbose=True,
        seed=unique_seed
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
