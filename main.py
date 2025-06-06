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

# We've simplified the code to not track background simulations explicitly.
# Each simulation now just appears in the "Completed Simulations" list when it's done.

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
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
        {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
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
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
        {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
    ]
    
    # Current timestamp for default scan name
    now = datetime.datetime.now()
    
    # Check if we have an active sweep
    active_sweep = request.args.get('active_sweep')
    active_sweep_info = None
    
    if active_sweep:
        # Get count of completed simulations for this sweep
        completed_count = SimulationResult.query.filter_by(sweep_session=active_sweep).count()
        
        # Check if we have any information about the total expected simulations
        # Note: In a production app, you might store this in a separate table or cache
        total_expected = 0
        try:
            # Get the first simulation to find the parameter info
            first_sim = SimulationResult.query.filter_by(sweep_session=active_sweep).first()
            if first_sim:
                # Try to extract circuit type and other info
                circuit_type = first_sim.circuit_type
                param1 = first_sim.sweep_param1
                param2 = first_sim.sweep_param2
                
                # Estimate the total number of simulations based on the parameter values
                param1_values = db.session.query(db.func.count(db.distinct(SimulationResult.sweep_value1))).filter(
                    SimulationResult.sweep_session == active_sweep
                ).scalar() or 1
                
                param2_values = 1
                if param2:
                    param2_values = db.session.query(db.func.count(db.distinct(SimulationResult.sweep_value2))).filter(
                        SimulationResult.sweep_session == active_sweep
                    ).scalar() or 1
                
                total_expected = param1_values * param2_values
                
                # Build active sweep info
                active_sweep_info = {
                    'session_id': active_sweep,
                    'circuit_type': circuit_type,
                    'param1': param1.replace('_', ' ').title() if param1 else None,
                    'param2': param2.replace('_', ' ').title() if param2 else None,
                    'completed': completed_count,
                    'total': total_expected,
                    'progress': int((completed_count / total_expected * 100) if total_expected > 0 else 0)
                }
        except Exception as e:
            print(f"Error getting active sweep info: {str(e)}")
            traceback.print_exc()
    
    # Check if this is a JSON request for active sweep status
    if request.args.get('format') == 'json' and active_sweep:
        return jsonify({
            'active_sweep': active_sweep_info
        })
        
    return render_template('parameter_sweep.html',
                          circuit_types=circuit_types,
                          now=now,
                          default_params=config.DEFAULT_SIMULATION_PARAMS,
                          active_sweep=active_sweep_info)
                          
@app.route('/run_parameter_sweep', methods=['POST'])
def run_parameter_sweep():
    """Run a parameter sweep with the provided parameters."""
    # Extract base configuration
    circuit_types = request.form.getlist('circuit_types[]')
    # Always create a unique scan name with timestamp to prevent overwriting existing sweeps
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_name = request.form.get('scan_name', f'param_sweep_{timestamp}')
    # Ensure uniqueness by appending timestamp if scan_name was provided by user
    if scan_name == request.form.get('scan_name'):
        scan_name = f"{scan_name}_{timestamp}"
    init_state = request.form.get('init_state', 'superposition')
    
    # If no circuit types selected, default to first circuit type
    if not circuit_types:
        flash("No circuit types selected. Please select at least one circuit type.", "warning")
        return redirect(url_for('parameter_sweep'))
    
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
    
    # If we have multiple simulations, run them sequentially
    if large_simulation:
        # Track all sessions for the response
        all_sessions = []
        
        # Create separate sessions for each circuit type
        for circuit_type in circuit_types:
            # Create a unique session name for each circuit type
            circuit_scan_name = f"{circuit_type}_{scan_name}" if len(circuit_types) > 1 else scan_name
            all_sessions.append(circuit_scan_name)
            
            # Start a background thread to run simulations for this circuit type
            sweep_thread = threading.Thread(
                target=run_sequential_simulations,
                args=(circuit_type, parameter_sets, circuit_scan_name)
            )
            sweep_thread.daemon = True
            sweep_thread.start()
        
        # Use the main scan_name as the primary session ID for the response
        sweep_session_id = scan_name
        
        # Inform the user that simulations are running
        flash(f"Started running {total_combinations} simulations sequentially. Progress will be shown on this page.", "info")
        
        # Stay on the parameter sweep page
        return redirect(url_for('parameter_sweep', active_sweep=sweep_session_id))
    else:
        # For a single parameter set, run it directly for each selected circuit type
        try:
            # Import the simulation function
            from simulation import run_simulation
            
            # Get the first (and only) parameter set
            param_set = parameter_sets[0]
            
            results = []
            # Run a simulation for each selected circuit type
            for idx, circuit_type in enumerate(circuit_types):
                # Create a unique session name for each circuit type
                circuit_scan_name = f"{circuit_type}_{scan_name}" if len(circuit_types) > 1 else scan_name
                
                # Run the simulation for this circuit type
                result = run_simulation(
                    circuit_type=circuit_type,
                    qubits=param_set.get('qubits', 3),
                    shots=param_set.get('shots', 8192),
                    drive_steps=param_set.get('drive_steps', 5),
                    time_points=param_set.get('time_points', 100),
                    max_time=param_set.get('max_time', 10.0),
                    drive_param=param_set.get('drive_param', 0.9),
                    init_state=param_set.get('init_state', 'superposition'),
                    param_set_name=circuit_scan_name,
                    save_results=True,
                    show_plots=False,
                    # Add parameter sweep tracking for single simulation
                    sweep_session=circuit_scan_name,
                    sweep_index=0,
                    sweep_param1=None,
                    sweep_value1=None,
                    sweep_param2=None,
                    sweep_value2=None
                )
                results.append(result)
            
            # Handle multiple circuit types
            if len(results) > 1:
                # Format a message with links to all simulation results
                from flask import Markup
                message = "Multiple simulations completed:<br>"
                for i, res in enumerate(results):
                    res_path = res.get('result_path', '').split('/')[-1]
                    circuit = circuit_types[i]
                    message += f"• {circuit}: <a href='/result/{res_path}'>{res_path}</a><br>"
                
                flash(Markup(message), "success")
                return redirect(url_for('parameter_sweep'))
            else:
                # Single circuit type case
                result_path = results[0].get('result_path', '').split('/')[-1]
                return redirect(url_for('view_result', result_name=result_path))
        except Exception as e:
            print(f"Error running simulation: {str(e)}")
            traceback.print_exc()
            flash(f"Error running simulation: {str(e)}", 'error')
            return redirect(url_for('parameter_sweep'))
            
def run_sequential_simulations(circuit_type, parameter_sets, scan_name):
    """Run multiple simulations sequentially, one after another for a specific circuit type."""
    try:
        # Validate circuit type
        if not circuit_type:
            print(f"Error: No circuit type provided for sequential simulations")
            return
            
        # Count of total parameter sets (outside app context is fine)
        total_sets = len(parameter_sets)
        print(f"Starting sequential simulation run with {total_sets} parameter combinations")
        
        # Determine which parameters are being swept
        swept_params = []
        for param_name, values in {
            'qubits': [p.get('qubits') for p in parameter_sets],
            'time_points': [p.get('time_points') for p in parameter_sets],
            'drive_param': [p.get('drive_param') for p in parameter_sets],
            'max_time': [p.get('max_time') for p in parameter_sets],
            'drive_steps': [p.get('drive_steps') for p in parameter_sets],
            'shots': [p.get('shots') for p in parameter_sets]
        }.items():
            # If we have more than one unique value, the parameter is being swept
            unique_values = list(set([v for v in values if v is not None]))
            if len(unique_values) > 1:
                swept_params.append((param_name, unique_values))
        
        # Sort to ensure param1 is always the first parameter being swept
        swept_params.sort(key=lambda x: len(x[1]), reverse=True)
        
        # Limit to at most 2 swept parameters (for grid view)
        swept_params = swept_params[:2]
        
        param1_name = swept_params[0][0] if len(swept_params) > 0 else None
        param2_name = swept_params[1][0] if len(swept_params) > 1 else None
        
        print(f"Sweep parameters: {', '.join([p[0] for p in swept_params])}")
        
        # Create a parameter sweep record in the database - all database operations must be inside app_context
        sweep_session_id = scan_name
        
        # Use app context for all database operations
        with app.app_context():
            try:
                from models import ParameterSweep
                # Check if the sweep already exists
                existing_sweep = ParameterSweep.query.filter_by(session_id=sweep_session_id).first()
                if not existing_sweep:
                    # Create new sweep record
                    new_sweep = ParameterSweep()
                    new_sweep.session_id = sweep_session_id
                    new_sweep.circuit_type = circuit_type
                    new_sweep.param1 = param1_name
                    new_sweep.param2 = param2_name
                    new_sweep.total_simulations = total_sets
                    new_sweep.completed_simulations = 0
                    db.session.add(new_sweep)
                    db.session.commit()
                    print(f"Created parameter sweep record: {sweep_session_id} with {total_sets} simulations")
                else:
                    # Update existing sweep record
                    existing_sweep.total_simulations = max(existing_sweep.total_simulations, total_sets)
                    existing_sweep.circuit_type = circuit_type
                    existing_sweep.param1 = param1_name or existing_sweep.param1
                    existing_sweep.param2 = param2_name or existing_sweep.param2
                    db.session.commit()
                    print(f"Updated parameter sweep record: {sweep_session_id}")
            except Exception as e:
                print(f"Error creating parameter sweep record: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Run each simulation independently
        for i, param_set in enumerate(parameter_sets):
            try:
                # Generate a descriptive name for this parameter set
                qubits = param_set.get('qubits', 3)
                time_points = param_set.get('time_points', 100)
                drive_param = param_set.get('drive_param', 0.9)
                param_suffix = f"{qubits}q_{time_points}tp_d{drive_param:.1f}"
                
                param_set_name = f"{scan_name}_{i+1}_{param_suffix}"
                
                print(f"Running simulation {i+1}/{total_sets} with parameters: " + 
                      f"qubits={qubits}, time_points={time_points}, drive_param={drive_param}")
                
                # Import here to avoid circular imports
                from simulation import run_simulation
                from db_utils import save_simulation_to_db
                
                # Create a Flask application context for this simulation
                with app.app_context():
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
                        param_set_name=param_set_name,
                        save_results=True,
                        show_plots=False,
                        # Add parameter sweep tracking
                        sweep_session=sweep_session_id,
                        sweep_index=i,
                        sweep_param1=param1_name,
                        sweep_value1=param_set.get(param1_name) if param1_name else None,
                        sweep_param2=param2_name,
                        sweep_value2=param_set.get(param2_name) if param2_name else None
                    )
                    
                    # Get the result path for tracking
                    results_path = result.get('results_path', '')
                    result_name = os.path.basename(results_path) if results_path else None
                    
                    # Update database record with sweep information
                    if result.get('db_record'):
                        try:
                            db_record = result.get('db_record')
                            db_record.sweep_session = sweep_session_id
                            db_record.sweep_index = i + 1
                            
                            # Store parameter values being swept
                            if param1_name:
                                db_record.sweep_param1 = param1_name
                                db_record.sweep_value1 = float(param_set.get(param1_name, 0))
                            
                            if param2_name:
                                db_record.sweep_param2 = param2_name
                                db_record.sweep_value2 = float(param_set.get(param2_name, 0))
                            
                            db.session.commit()
                            
                            # Separately update the parameter sweep completion counter
                            try:
                                from models import ParameterSweep
                                sweep_record = ParameterSweep.query.filter_by(session_id=sweep_session_id).first()
                                if sweep_record:
                                    sweep_record.completed_simulations += 1
                                    db.session.commit()
                                    
                                    # Log progress
                                    progress = (sweep_record.completed_simulations / sweep_record.total_simulations) * 100
                                    print(f"Sweep progress: {sweep_record.completed_simulations}/{sweep_record.total_simulations} ({progress:.1f}%)")
                                else:
                                    print(f"Warning: Parameter sweep record not found for session {sweep_session_id}")
                            except Exception as sweep_err:
                                print(f"Error updating sweep completion counter: {str(sweep_err)}")
                                
                        except Exception as db_err:
                            print(f"Error updating sweep metadata in database: {str(db_err)}")
                    
                    print(f"✓ Completed simulation {i+1}/{total_sets}: {result_name}")
                    
                    # Database saving is already handled in the simulation module
                    if result_name and not result.get('db_record'):
                        print(f"Note: Simulation {result_name} may not have been saved to the database automatically.")
                
            except Exception as e:
                print(f"Error running simulation {i+1}/{total_sets}: {str(e)}")
                traceback.print_exc()
                # Continue with next simulation regardless of errors
        
        # Create a relative URL for the sweep grid
        sweep_url = f"/sweep_grid/{scan_name}"
        print(f"✓ Completed all {total_sets} simulations. View results at: {sweep_url}")
        
        # Note: We don't need to flash a message here as it would be lost
        # since this runs in a background thread
        
    except Exception as e:
        print(f"Error in sequential simulation run: {str(e)}")
        traceback.print_exc()



@app.route('/run_simulation', methods=['POST'])
def run_simulation():
    """Run a simulation with the provided parameters."""
    try:
        # Extract parameters from form
        circuit_type = request.form.get('circuit_type')
        qubits = int(request.form.get('qubits', 8))
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
            
            # Start a thread to run the simulation
            thread = threading.Thread(
                target=run_single_simulation,
                args=(params,)
            )
            thread.daemon = True
            thread.start()
            
            if is_ajax:
                # Return JSON response for AJAX requests
                return jsonify({
                    'status': 'running',
                    'message': 'Simulation started. It will appear in the Completed Simulations list when finished.'
                })
            else:
                # Regular form submission - redirect to the simulations page
                flash('Simulation started. It will appear in the Completed Simulations list when finished.', 'info')
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

def run_single_simulation(params):
    """Run a simulation in a separate thread without tracking in a global dictionary."""
    try:
        # Create a progress callback to print progress
        def progress_callback(step, total):
            progress = int((step / total) * 100)
            print(f"Simulation progress: {progress}%")
        
        # Import run_simulation here to avoid circular imports
        from simulation import run_simulation
        from db_utils import save_simulation_to_db
        
        # Generate a unique random seed for this run
        import random
        unique_seed = random.randint(10000, 99999)
        
        # Create an application context for database operations
        with app.app_context():
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
            
            # Log completion
            results_path = result.get('results_path', '')
            result_name = os.path.basename(results_path) if results_path else None
            print(f"Simulation completed successfully: {result_name}")
            
            # Database saving is already handled in the simulation module,
            # and additional attempts could cause duplicate key errors.
            # If the simulation was saved properly, it will have a db_record attribute.
            if result_name and not result.get('db_record'):
                print(f"Note: Simulation {result_name} may not have been saved to the database automatically.")
        
    except Exception as e:
        # If an error occurs, log it
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Simulation error: {str(e)}")
        print(error_traceback)  # Print full traceback for debugging

@app.route('/api/simulation/<result_name>')
@app.route('/get_simulation_preview/<result_name>')
def get_simulation_preview(result_name):
    """Get a simulation data for AJAX requests in the dashboard."""
    try:
        import glob  # Import here for file searching
        import datetime
        import re
        import traceback
        import os
        from db_utils import get_simulation_by_name
        
        print(f"API request for simulation: {result_name}")
        
        # Debug info
        print("Available routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.endpoint}: {rule.rule}")
        
        # Check if the result exists in the filesystem
        result_path = os.path.join('results', result_name)
        print(f"Checking if result path exists: {result_path}")
        if os.path.exists(result_path):
            print(f"Result directory exists: {result_path}")
        else:
            print(f"Result directory does not exist: {result_path}")
        
        # Get simulation from database
        simulation = get_simulation_by_name(result_name)
        
        # Get list of figure files and result path
        figure_files = []
        
        # Simulation found in database
        if simulation:
            print(f"Simulation found in database: {result_name}")
            result_path = simulation.results_path
            
            # Extract simulation metadata from database
            circuit_type = simulation.circuit_type
            qubits = simulation.qubits
            time_points = simulation.time_points
            time_crystal_detected = simulation.time_crystal_detected
            comb_detected = simulation.linear_combs_detected or simulation.log_combs_detected
            created_at = simulation.created_at.strftime('%Y-%m-%d %H:%M')
            sim_id = simulation.id
            is_starred = simulation.is_starred
            
        # Simulation not in database, try to load from filesystem
        else:
            print(f"Simulation not found in database, checking filesystem: {result_name}")
            
            # Assume the result_name is a directory in the results folder
            result_path = os.path.join('results', result_name)
            
            if not os.path.exists(result_path):
                print(f"Simulation directory not found: {result_path}")
                return jsonify({"error": "Simulation not found"}), 404
                
            # Try to extract information from the result_name
            # Format is typically: circuit_type_...._NNq_timestamp
            parts = result_name.split('_')
            
            # Extract circuit type (first part)
            circuit_type = parts[0]
            
            # Special case: If circuit_type is "graphene", convert to "graphene_fc"
            if circuit_type == "graphene":
                circuit_type = "graphene_fc"
            
            # Try to find qubits (look for pattern with q)
            qubits = 3  # Default if we can't extract it
            for part in parts:
                if part.endswith('q') and part[:-1].isdigit():
                    qubits = int(part[:-1])
                    break
            
            # Get timestamp from the filename as the creation date
            timestamp_str = result_name.split('_')[-1]
            try:
                created_at = datetime.datetime.strptime(timestamp_str, '%Y%m%d-%H%M%S').strftime('%Y-%m-%d %H:%M')
            except ValueError:
                created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            
            # Default values for other metadata
            time_points = 100
            time_crystal_detected = False
            comb_detected = False
            sim_id = 0
            is_starred = False
            
            # Try to parse from files if they exist
            results_json = os.path.join(result_path, 'results.json')
            if os.path.exists(results_json):
                try:
                    import json
                    with open(results_json, 'r') as f:
                        data = json.load(f)
                        
                    # Extract data if available
                    params = data.get('parameters', {})
                    analysis = data.get('analysis', {})
                    
                    time_points = params.get('time_points', 100)
                    time_crystal_detected = analysis.get('has_subharmonics', False)
                    
                    # Extract comb detection if available
                    fc_analysis = data.get('fc_analysis', {})
                    comb_analysis = data.get('comb_analysis', {})
                    log_comb_analysis = data.get('log_comb_analysis', {})
                    
                    comb_detected = (
                        comb_analysis.get('mx_comb_found', False) or 
                        comb_analysis.get('mz_comb_found', False) or
                        log_comb_analysis.get('mx_log_comb_found', False) or 
                        log_comb_analysis.get('mz_log_comb_found', False)
                    )
                except Exception as e:
                    print(f"Error parsing results.json: {e}")
        
        print(f"Looking for figures in: {result_path}")
        
        # Check figures folder first
        figure_path = os.path.join(result_path, 'figures')
        if os.path.exists(figure_path):
            png_files = sorted(glob.glob(os.path.join(figure_path, '*.png')))
            figure_files = [os.path.basename(f) for f in png_files]
            print(f"Found {len(png_files)} PNG files in figures folder")
        
        # No figures in figures folder? Check main folder
        if not figure_files and os.path.exists(result_path):
            png_files = sorted(glob.glob(os.path.join(result_path, '*.png')))
            figure_files = [os.path.basename(f) for f in png_files]
            print(f"Found {len(png_files)} PNG files in main folder")
            
        # For the dashboard we want all figures
        preview_figures = figure_files if figure_files else []
        
        print(f"Preview for {result_name}: Found {len(preview_figures)} figures")
            
        # Return simulation data with all figures and parameters
        response_data = {
            "id": sim_id,
            "result_name": result_name,
            "circuit_type": circuit_type, 
            "qubits": qubits,
            "time_points": time_points,
            "time_crystal_detected": time_crystal_detected,
            "comb_detected": comb_detected,
            "created_at": created_at,
            "is_starred": is_starred,
            "figures": preview_figures
        }
        
        # Add all extra parameters if available from database
        if simulation:
            # Add all database fields to the response
            for column in simulation.__table__.columns:
                col_name = column.name
                if col_name not in response_data and hasattr(simulation, col_name):
                    value = getattr(simulation, col_name)
                    # Convert datetime objects to strings
                    if isinstance(value, datetime.datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    response_data[col_name] = value
            
            # Load extra data JSON if available
            if hasattr(simulation, 'get_extra_data') and callable(simulation.get_extra_data):
                extra_data = simulation.get_extra_data()
                if extra_data and isinstance(extra_data, dict):
                    response_data["extra_params"] = extra_data
        
        print(f"Returning data for simulation: {result_name}")
        return jsonify(response_data)
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error getting simulation preview: {str(e)}")
        print(error_traceback)
        
        # Return a more helpful error response with full details
        return jsonify({
            "error": str(e),
            "message": "Failed to load simulation data",
            "result_name": result_name,
            "traceback": error_traceback.split('\n')
        }), 500

@app.route('/simple_dashboard')
def simple_dashboard():
    """Simple dashboard view without JavaScript for troubleshooting."""
    # Import needed modules
    import glob
    import os
    import traceback
    import datetime
    import time
    import json
    
    # Define a class to simulate database models for filesystem results
    class FilesystemSimulation:
        def __init__(self, result_name, circuit_type="unknown", qubits=3, time_points=100, 
                     created_at=None, time_crystal_detected=False, comb_detected=False):
            self.id = 0
            self.result_name = result_name
            self.circuit_type = circuit_type
            self.qubits = qubits
            self.time_points = time_points
            self.created_at = created_at or datetime.datetime.now()
            self.time_crystal_detected = time_crystal_detected
            self.linear_combs_detected = comb_detected
            self.log_combs_detected = False
            self.results_path = os.path.join('results', result_name)
    
    simulations = []
    
    # Get results from filesystem
    result_dirs = glob.glob('results/*')
    result_dirs = sorted(result_dirs, key=os.path.getmtime, reverse=True)
    
    for result_dir in result_dirs[:20]:  # Limit to most recent 20
        result_name = os.path.basename(result_dir)
        
        # Parse metadata from filename and directory
        parts = result_name.split('_')
        circuit_type = parts[0] if parts else "unknown"
        
        # Try to find qubits (look for pattern with q)
        qubits = 3  # Default
        for part in parts:
            if part.endswith('q') and part[:-1].isdigit():
                qubits = int(part[:-1])
                break
        
        # Get creation time from directory
        try:
            mtime = os.path.getmtime(result_dir)
            created_at = datetime.datetime.fromtimestamp(mtime)
        except:
            created_at = datetime.datetime.now()
        
        # Try to get more details from results.json if it exists
        time_points = 100
        time_crystal = False
        comb_detected_flag = False
        
        results_json = os.path.join(result_dir, 'results.json')
        if os.path.exists(results_json):
            try:
                with open(results_json, 'r') as f:
                    data = json.load(f)
                
                params = data.get('parameters', {})
                analysis = data.get('analysis', {})
                
                time_points = params.get('time_points', 100)
                time_crystal = analysis.get('has_subharmonics', False)
                
                # Get comb detection
                fc_analysis = data.get('fc_analysis', {})
                comb_analysis = data.get('comb_analysis', {})
                log_comb_analysis = data.get('log_comb_analysis', {})
                
                comb_detected_flag = (
                    comb_analysis.get('mx_comb_found', False) or 
                    comb_analysis.get('mz_comb_found', False) or
                    log_comb_analysis.get('mx_log_comb_found', False) or 
                    log_comb_analysis.get('mz_log_comb_found', False)
                )
            except:
                pass
        
        # Create a simulation object for this result
        fs_sim = FilesystemSimulation(
            result_name=result_name,
            circuit_type=circuit_type,
            qubits=qubits,
            time_points=time_points,
            created_at=created_at,
            time_crystal_detected=time_crystal,
            comb_detected=comb_detected_flag
        )
        
        # Add to simulations list
        simulations.append(fs_sim)
    
    # Log information about simulations found
    print(f"Simple dashboard loaded {len(simulations)} simulations from filesystem")
    for sim in simulations[:5]:  # Log first 5 for debugging
        print(f"  - {sim.result_name} ({sim.circuit_type}, {sim.qubits} qubits)")
    
    return render_template('simple_dashboard.html', simulations=simulations)

@app.route('/dashboard')
def dashboard():
    """Dashboard view with simulations list and preview panel side by side."""
    # Import needed modules
    import glob
    import os
    import traceback  # Add traceback for error logging
    import datetime
    import time
    import json
    
    # Initialize variables outside the try block to ensure they're always defined
    circuit_type = request.args.get('circuit_type', '')
    min_qubits = request.args.get('min_qubits', type=int)
    max_qubits = request.args.get('max_qubits', type=int)
    time_crystal_detected = request.args.get('time_crystal') == 'true'
    comb_detected = request.args.get('comb_detected') == 'true'
    simulations = []
    db_error = None
    
    # Define a class to simulate database models for filesystem results
    class FilesystemSimulation:
        def __init__(self, result_name, circuit_type="unknown", qubits=3, time_points=100, 
                     created_at=None, time_crystal_detected=False, comb_detected=False):
            self.id = 0
            self.result_name = result_name
            self.circuit_type = circuit_type
            self.qubits = qubits
            self.time_points = time_points
            self.created_at = created_at or datetime.datetime.now()
            self.time_crystal_detected = time_crystal_detected
            self.linear_combs_detected = comb_detected
            self.log_combs_detected = False
            self.results_path = os.path.join('results', result_name)
    
    try:
        from db_utils import search_simulations
        
        # If no filters specified, don't apply them
        if not circuit_type and not min_qubits and not max_qubits and \
           not request.args.get('time_crystal') and not request.args.get('comb_detected'):
            time_crystal_detected = None
            comb_detected = None
        
        # Search simulations using filters
        db_simulations = search_simulations(
            circuit_type=circuit_type if circuit_type else None,
            min_qubits=min_qubits,
            max_qubits=max_qubits,
            time_crystal_detected=time_crystal_detected,
            comb_detected=comb_detected
        )
        
        # Start with database simulations
        simulations = db_simulations
        
    except Exception as e:
        traceback.print_exc()
        simulations = []
        db_error = str(e)
    
    # Always check filesystem for recent results, especially those not in the database
    result_dirs = glob.glob('results/*')
    result_dirs = sorted(result_dirs, key=os.path.getmtime, reverse=True)
    
    # Get existing result names from database to avoid duplicates
    db_result_names = {sim.result_name for sim in simulations}
    
    # Process filesystem results and add them if not already in the database
    for result_dir in result_dirs[:20]:  # Limit to most recent 20
        result_name = os.path.basename(result_dir)
        
        # Skip if already in database results
        if result_name in db_result_names:
            continue
        
        # Parse metadata from filename and directory
        parts = result_name.split('_')
        circuit_type = parts[0] if parts else "unknown"
        
        # Try to find qubits (look for pattern with q)
        qubits = 3  # Default
        for part in parts:
            if part.endswith('q') and part[:-1].isdigit():
                qubits = int(part[:-1])
                break
        
        # Get creation time from directory
        try:
            mtime = os.path.getmtime(result_dir)
            created_at = datetime.datetime.fromtimestamp(mtime)
        except:
            created_at = datetime.datetime.now()
        
        # Try to get more details from results.json if it exists
        time_points = 100
        time_crystal = False
        comb_detected_flag = False
        
        results_json = os.path.join(result_dir, 'results.json')
        if os.path.exists(results_json):
            try:
                with open(results_json, 'r') as f:
                    data = json.load(f)
                
                params = data.get('parameters', {})
                analysis = data.get('analysis', {})
                
                time_points = params.get('time_points', 100)
                time_crystal = analysis.get('has_subharmonics', False)
                
                # Get comb detection
                fc_analysis = data.get('fc_analysis', {})
                comb_analysis = data.get('comb_analysis', {})
                log_comb_analysis = data.get('log_comb_analysis', {})
                
                comb_detected_flag = (
                    comb_analysis.get('mx_comb_found', False) or 
                    comb_analysis.get('mz_comb_found', False) or
                    log_comb_analysis.get('mx_log_comb_found', False) or 
                    log_comb_analysis.get('mz_log_comb_found', False)
                )
            except:
                pass
        
        # Apply filters if needed
        if circuit_type and circuit_type != circuit_type:
            continue
        if min_qubits is not None and qubits < min_qubits:
            continue
        if max_qubits is not None and qubits > max_qubits:
            continue
        if time_crystal_detected is not None and time_crystal != time_crystal_detected:
            continue
        if comb_detected is not None and comb_detected_flag != comb_detected:
            continue
        
        # Create a simulation object for this result
        fs_sim = FilesystemSimulation(
            result_name=result_name,
            circuit_type=circuit_type,
            qubits=qubits,
            time_points=time_points,
            created_at=created_at,
            time_crystal_detected=time_crystal,
            comb_detected=comb_detected_flag
        )
        
        # Add to simulations list
        simulations.append(fs_sim)
    
    # Sort all simulations by creation date (newest first)
    simulations = sorted(simulations, key=lambda x: x.created_at, reverse=True)
    
    # Get list of circuit types for filter dropdown
    circuit_types = [
        {"id": "penrose", "name": "Penrose"},
        {"id": "qft_basic", "name": "QFT Basic"},
        {"id": "comb_generator", "name": "Comb Generator"},
        {"id": "comb_twistor", "name": "Comb Twistor"},
        {"id": "graphene_fc", "name": "Graphene FC"},
    ]
    
    # Keep recent_results for legacy code support
    recent_results = [os.path.basename(d) for d in result_dirs[:10]]
    
    # Log information about simulations found
    print(f"Dashboard loaded {len(simulations)} simulations")
    for sim in simulations[:5]:  # Log first 5 for debugging
        print(f"  - {sim.result_name} ({sim.circuit_type}, {sim.qubits} qubits)")
    
    # These variables are already defined at the start of the function
    
    return render_template(
        'dashboard_new.html',
        simulations=simulations,
        db_error=db_error,
        recent_results=recent_results,
        circuit_types=circuit_types,
        # Pass filter values back to template
        filter_circuit_type=circuit_type,
        filter_min_qubits=min_qubits,
        filter_max_qubits=max_qubits,
        filter_time_crystal=time_crystal_detected,
        filter_comb_detected=comb_detected,
        filter_is_starred=request.args.get('is_starred') == 'true'
    )

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
    
    # We no longer track background jobs - all simulations appear directly in the database
    # This simplifies the UI and makes it clearer what's happening
    
    # Get database results
    try:
        from db_utils import search_simulations, get_recent_simulations
        
        # Get simulation results
        if filters:
            db_simulations = search_simulations(**filters)
        else:
            db_simulations = get_recent_simulations(limit=50)
            
        # Show database results
        return render_template('simulations.html',
                            simulations=db_simulations)
    except Exception as e:
        # Fall back to file system if database fails
        print(f"Warning: Could not fetch from database: {e}")
        results_dirs = sorted(glob.glob('results/*'), key=os.path.getmtime, reverse=True)
        recent_results = [os.path.basename(d) for d in results_dirs[:10]]
        
        return render_template('simulations.html',
                            simulations=[],
                            recent_results=recent_results,
                            db_error=str(e))

# The simulation_status route has been removed as we no longer track individual
# simulation status through BACKGROUND_SIMULATIONS dictionary

@app.route('/api/simulation/<result_name>/toggle_star', methods=['POST'])
def toggle_simulation_star(result_name):
    """Toggle the starred status of a simulation."""
    try:
        from db_utils import get_simulation_by_name
        from models import db
        
        # Get the simulation
        simulation = get_simulation_by_name(result_name)
        
        if not simulation:
            return jsonify({
                'status': 'error',
                'message': f'Simulation {result_name} not found'
            }), 404
        
        # Toggle the is_starred flag
        simulation.is_starred = not simulation.is_starred
        
        # Save to database
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'result_name': result_name,
            'is_starred': simulation.is_starred
        })
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error toggling star status: {str(e)}")
        print(error_traceback)
        
        return jsonify({
            'status': 'error',
            'message': f'Error toggling star status: {str(e)}'
        }), 500

@app.route('/api/simulations/starred', methods=['GET'])
def get_starred_simulations():
    """Get all starred simulations."""
    try:
        from models import SimulationResult
        
        # Query all starred simulations
        starred_simulations = SimulationResult.query.filter_by(is_starred=True).order_by(
            SimulationResult.created_at.desc()
        ).all()
        
        # Format the response
        results = []
        for sim in starred_simulations:
            results.append({
                'id': sim.id,
                'result_name': sim.result_name,
                'circuit_type': sim.circuit_type,
                'qubits': sim.qubits,
                'time_points': sim.time_points,
                'created_at': sim.created_at.strftime('%Y-%m-%d %H:%M'),
                'time_crystal_detected': sim.time_crystal_detected,
                'comb_detected': sim.linear_combs_detected or sim.log_combs_detected,
                'is_starred': sim.is_starred
            })
        
        return jsonify({
            'status': 'success',
            'starred_simulations': results
        })
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error getting starred simulations: {str(e)}")
        print(error_traceback)
        
        return jsonify({
            'status': 'error',
            'message': f'Error getting starred simulations: {str(e)}'
        }), 500

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

@app.route('/circuit-t1/<circuit_type>/<int:qubits>')
def get_circuit_at_t1(circuit_type, qubits):
    """
    Generate and display a circuit diagram at t=1.0.
    This route generates a circuit of the specified type with the given number of qubits,
    binds the time parameter to t=1.0, and returns the diagram as a PNG image.
    """
    from quantum_circuits import get_circuit_generator
    from visualization import plot_circuit_diagram
    import os
    import io
    
    print(f"DEBUG: Generating circuit at t=1 for {circuit_type} with {qubits} qubits")
    
    try:
        # Handle the case where the circuit type name is just "graphene"
        if circuit_type == "graphene":
            circuit_type = "graphene_fc"
            
        # Get the appropriate circuit generator
        circuit_generator = get_circuit_generator(circuit_type)
        
        if not circuit_generator:
            return f"Unknown circuit type: {circuit_type}", 400
        
        # Default parameters
        shots = 1024
        drive_steps = 1  # Use only 1 drive step for the t=1 view to avoid repeating patterns
        drive_param = 0.9
        init_state = 'superposition'
        
        print(f"DEBUG: Using drive_steps={drive_steps}")
        
        # Generate the circuit with time parameter
        circuit, t = circuit_generator(
            qubits, 
            shots=shots, 
            drive_steps=drive_steps,
            init_state=init_state,
            drive_param=drive_param
        )
        
        print(f"DEBUG: Generated circuit with depth {circuit.depth()}")
        
        # Bind the time parameter to t=1.0
        from qiskit.circuit import ParameterVector
        param_dict = {t: 1.0}
        bound_circuit = circuit.assign_parameters(param_dict)
        
        print(f"DEBUG: Bound circuit with t=1.0, depth: {bound_circuit.depth()}")
        
        # Create temporary directory if needed
        temp_dir = os.path.join('figures', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate a unique filename
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        filename = f"circuit_{circuit_type}_t1_{qubits}q_{unique_id}.png"
        
        # Plot the circuit diagram
        print(f"DEBUG: About to plot circuit diagram with time_value=1.0, circuit_type={circuit_type}_t1")
        fig_path = plot_circuit_diagram(
            bound_circuit, 
            time_value=1.0,
            circuit_type=f"{circuit_type}_t1",
            qubit_count=qubits, 
            save_path=temp_dir
        )
        
        # Return the image
        if fig_path and isinstance(fig_path, str) and os.path.exists(fig_path):
            return send_file(fig_path, mimetype='image/png')
        else:
            return "Failed to generate circuit diagram", 500
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error generating circuit at t=1: {str(e)}")
        print(error_traceback)
        return f"Error generating circuit: {str(e)}", 500

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    print(f"Request for figure: {result_name}/{figure_name}")
    
    # List of paths to try, in order of preference
    paths_to_try = []
    
    # First check if result is in database
    try:
        from db_utils import get_simulation_by_name
        db_result = get_simulation_by_name(result_name)
        
        if db_result and db_result.results_path:
            result_path = db_result.results_path
            print(f"Simulation found in database with path: {result_path}")
            
            # Add database paths to try
            paths_to_try.append(os.path.join(result_path, 'figures', figure_name))
            paths_to_try.append(os.path.join(result_path, figure_name))
        else:
            print(f"Simulation not found in database: {result_name}")
    except Exception as e:
        print(f"Error retrieving figure from database: {e}")
    
    # Add default filesystem paths
    paths_to_try.append(os.path.join('results', result_name, 'figures', figure_name))
    paths_to_try.append(os.path.join('results', result_name, figure_name))
    
    # Try each path in order
    for path in paths_to_try:
        print(f"Trying path: {path}")
        if os.path.exists(path):
            print(f"Found figure at: {path}")
            try:
                # Get MIME type based on extension
                mime_type = None
                if path.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif path.lower().endswith('.jpg') or path.lower().endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif path.lower().endswith('.svg'):
                    mime_type = 'image/svg+xml'
                
                response = send_file(
                    path,
                    mimetype=mime_type,
                    as_attachment=False,
                    download_name=figure_name,
                    max_age=0  # Don't cache
                )
                # Add headers to prevent caching issues
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
            except Exception as e:
                print(f"Error sending file {path}: {e}")
    
    # If we get here, the figure wasn't found
    print(f"Figure not found: {result_name}/{figure_name}")
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

@app.route('/sweep_preview/<sweep_session>')
def sweep_preview(sweep_session):
    """View a minimalist preview of frequency spectra for all simulations in a parameter sweep."""
    # Get the parameter sweep record
    from models import ParameterSweep, SimulationResult
    sweep = ParameterSweep.query.filter_by(session_id=sweep_session).first_or_404()
    
    # Get all simulations for this sweep
    simulations = SimulationResult.query.filter_by(sweep_session=sweep_session).order_by(SimulationResult.sweep_index).all()
    
    return render_template('sweep_preview.html', sweep=sweep, simulations=simulations)

@app.route('/sweep_grid/<sweep_session>')
def view_sweep_grid(sweep_session):
    """View parameter sweep results in a grid format."""
    try:
        # First, check if the sweep session exists in the database
        from models import ParameterSweep
        sweep_record = ParameterSweep.query.filter_by(session_id=sweep_session).first()
        
        if not sweep_record:
            flash(f"Parameter sweep session not found: {sweep_session}", "warning")
            return redirect(url_for('parameter_sweep'))
        
        # Get all simulations for this sweep session
        simulations = SimulationResult.query.filter_by(sweep_session=sweep_session).order_by(SimulationResult.sweep_index).all()
        
        if not simulations:
            # This sweep exists but has no simulations yet, probably in progress
            # Return a template with "in progress" or "waiting for results" message
            progress = (sweep_record.completed_simulations / sweep_record.total_simulations) * 100 if sweep_record.total_simulations > 0 else 0
            
            circuit_type_name = sweep_record.circuit_type
            sweep_session_title = f"Parameter Sweep: {circuit_type_name}"
            
            if sweep_record.param1:
                param1_name = sweep_record.param1.replace('_', ' ').title()
                sweep_session_title += f" - {param1_name} Sweep"
                
                if sweep_record.param2:
                    param2_name = sweep_record.param2.replace('_', ' ').title()
                    sweep_session_title += f" & {param2_name} Sweep"
            
            return render_template('sweep_matrix_new.html',
                                  sweep_session=sweep_session,
                                  sweep_session_title=sweep_session_title,
                                  simulations=[],
                                  display_mode='pending',
                                  param1=sweep_record.param1,
                                  param2=sweep_record.param2,
                                  param1_values=[],
                                  param2_values=[],
                                  grid_lookup={},
                                  created_at=sweep_record.created_at.strftime('%Y-%m-%d %H:%M') if sweep_record.created_at else '',
                                  sweep_record=sweep_record,
                                  progress=progress)
        
        # Extract sweep parameters
        param1 = simulations[0].sweep_param1
        param2 = simulations[0].sweep_param2
        
        # Get unique values for parameters
        param1_values = sorted(list(set([sim.sweep_value1 for sim in simulations if sim.sweep_value1 is not None])))
        param2_values = sorted(list(set([sim.sweep_value2 for sim in simulations if sim.sweep_param2 == param2 and sim.sweep_value2 is not None])))
        
        # Create lookup grid
        grid_lookup = {}
        for sim in simulations:
            if param2 and sim.sweep_value2 is not None:
                # Two parameter sweep
                grid_lookup[(sim.sweep_value1, sim.sweep_value2)] = sim
            else:
                # Single parameter sweep
                grid_lookup[sim.sweep_value1] = sim
        
        # Determine display mode
        display_mode = 'two_params' if param2 and len(param2_values) > 0 else 'single_param'
        
        # Create a nice title
        # Get circuit type name
        circuit_type_name = simulations[0].circuit_type
        sweep_session_title = f"Parameter Sweep: {circuit_type_name}"
        
        if param1:
            param1_name = param1.replace('_', ' ').title()
            sweep_session_title += f" - {param1_name} Sweep"
            
            if param2:
                param2_name = param2.replace('_', ' ').title()
                sweep_session_title += f" & {param2_name} Sweep"
        
        created_at = simulations[0].created_at.strftime('%Y-%m-%d %H:%M') if simulations[0].created_at else ''
        
        return render_template('sweep_matrix_new.html',
                              sweep_session=sweep_session,
                              sweep_session_title=sweep_session_title,
                              simulations=simulations,
                              param1=param1.replace('_', ' ').title() if param1 else None,
                              param2=param2.replace('_', ' ').title() if param2 else None,
                              param1_values=param1_values,
                              param2_values=param2_values,
                              display_mode=display_mode,
                              grid_lookup=grid_lookup,
                              circuit_type=circuit_type_name,
                              created_at=created_at)
    
    except Exception as e:
        print(f"Error viewing sweep grid: {str(e)}")
        traceback.print_exc()
        flash(f"Error viewing sweep grid: {str(e)}", "danger")
        return redirect(url_for('dashboard'))
        
@app.route('/api/sweep_sessions')
def list_sweep_sessions():
    """List all parameter sweep sessions."""
    try:
        # Use the ParameterSweep model directly
        from models import ParameterSweep
        
        # Get all parameter sweep sessions
        sweep_sessions = ParameterSweep.query.order_by(ParameterSweep.created_at.desc()).all()
        
        sessions_data = []
        for sweep in sweep_sessions:
            # Format parameter names for display
            param1 = sweep.param1.replace('_', ' ').title() if sweep.param1 else ""
            param2 = sweep.param2.replace('_', ' ').title() if sweep.param2 else ""
            
            # Add to results list
            sessions_data.append({
                'session_id': sweep.session_id,
                'circuit_type': sweep.circuit_type,
                'created_at': sweep.created_at.strftime('%Y-%m-%d %H:%M') if sweep.created_at else '',
                'simulation_count': sweep.completed_simulations,
                'total_simulations': sweep.total_simulations,
                'progress': int((sweep.completed_simulations / sweep.total_simulations * 100) if sweep.total_simulations > 0 else 0),
                'param1': param1,
                'param2': param2
            })
        
        return jsonify(sessions_data)
    except Exception as e:
        print(f"Error listing sweep sessions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/export/<result_name>')
def export_simulation_data(result_name):
    """
    Export simulation frequency data as a CSV file.
    
    Args:
        result_name: The name of the simulation result to export
        
    Returns:
        A CSV file containing the simulation's frequency data
    """
    try:
        # Get simulation data from the database
        from db_utils import get_simulation_by_name
        simulation = get_simulation_by_name(result_name)
        
        if not simulation:
            # Look for results in the filesystem
            results_path = os.path.join('results', result_name)
            if not os.path.exists(results_path):
                flash(f"Could not find simulation data for {result_name}", "error")
                return redirect(url_for('dashboard'))
            
            # Try to load the results data from JSON
            data_file = os.path.join(results_path, 'result_data.json')
            if not os.path.exists(data_file):
                flash(f"Could not find result data file for {result_name}", "error")
                return redirect(url_for('dashboard'))
            
            with open(data_file, 'r') as f:
                result_data = json.load(f)
        else:
            # Load the results from the simulation record
            results_path = simulation.results_path
            data_file = os.path.join(results_path, 'result_data.json')
            
            if not os.path.exists(data_file):
                flash(f"Could not find result data file for {result_name}", "error")
                return redirect(url_for('dashboard'))
            
            with open(data_file, 'r') as f:
                result_data = json.load(f)
        
        # Load analysis data
        analysis_file = os.path.join(results_path, 'analysis_results.json')
        if os.path.exists(analysis_file):
            with open(analysis_file, 'r') as f:
                analysis_data = json.load(f)
        else:
            analysis_data = {}
        
        # Create CSV file
        import csv
        import io
        
        # Create a StringIO object to hold the CSV data
        csv_data = io.StringIO()
        writer = csv.writer(csv_data)
        
        # Add metadata header and values
        writer.writerow(['# SIMULATION METADATA'])
        writer.writerow(['# This file contains frequency spectrum data from the quantum simulation'])
        writer.writerow(['# Generated on', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([''])
        writer.writerow(['# PARAMETERS'])
        
        # Extract parameters either from result_data or analysis_data
        params = result_data.get('parameters', {})
        if not params and 'parameters' in analysis_data:
            params = analysis_data.get('parameters', {})
        
        # Write parameter data
        for key, value in params.items():
            writer.writerow([f'# {key}', value])
        
        # Add simulation results
        writer.writerow([''])
        writer.writerow(['# SIMULATION RESULTS'])
        writer.writerow([f'# Time Crystal Detected', result_data.get('time_crystal_detected', False)])
        writer.writerow([f'# Incommensurate Frequencies', result_data.get('incommensurate_count', 0)])
        writer.writerow([f'# Linear Combs Detected', result_data.get('linear_combs_detected', False)])
        writer.writerow([f'# Log Combs Detected', result_data.get('log_combs_detected', False)])
        writer.writerow([f'# Drive Frequency', result_data.get('drive_frequency', 0.0)])
        writer.writerow([''])
        
        # Write data header
        writer.writerow(['Component', 'Frequency', 'Amplitude', 'Phase', 
                        'Is Harmonic', 'Is Incommensurate', 'Is Comb Tooth'])
        
        # Look for analysis in the proper location
        basic_analysis = {}
        fc_analysis = {}
        comb_analysis = {}
        if 'basic_analysis' in analysis_data:
            basic_analysis = analysis_data.get('basic_analysis', {})
            fc_analysis = analysis_data.get('frequency_crystal_analysis', {})
            comb_analysis = analysis_data.get('linear_comb_analysis', {})
        
        # Attempt to find FFT data
        # First check for fft_data.json if it exists
        fft_data_path = os.path.join(results_path, 'numeric_data', 'fft_data.json')
        fft_data = None
        
        if os.path.exists(fft_data_path):
            with open(fft_data_path, 'r') as f:
                fft_data = json.load(f)
        
        # If we have FFT data directly available
        if fft_data and 'positive_frequencies' in fft_data:
            frequencies = fft_data.get('positive_frequencies', [])
            mx_amp = fft_data.get('mx_fft_pos', [])
            my_amp = fft_data.get('my_fft_pos', [])
            mz_amp = fft_data.get('mz_fft_pos', [])
            
            if frequencies and len(frequencies) > 0:
                # This is a simplified approach since phase data might not be available
                for i in range(len(frequencies)):
                    if i < len(mx_amp):
                        writer.writerow(['X', frequencies[i], mx_amp[i], 0.0, False, False, False])
                    if i < len(my_amp):
                        writer.writerow(['Y', frequencies[i], my_amp[i], 0.0, False, False, False])
                    if i < len(mz_amp):
                        writer.writerow(['Z', frequencies[i], mz_amp[i], 0.0, False, False, False])
        
        # If we have peaks data
        if 'frequency_crystal_analysis' in analysis_data and 'mx_peaks' in analysis_data.get('frequency_crystal_analysis', {}):
            fc_data = analysis_data['frequency_crystal_analysis']
            
            # Add X component data
            if 'mx_peaks' in fc_data and isinstance(fc_data['mx_peaks'], list):
                for peak in fc_data['mx_peaks']:
                    if isinstance(peak, dict) and 'frequency' in peak and 'amplitude' in peak:
                        writer.writerow(['X', peak.get('frequency'), peak.get('amplitude'), 
                                        peak.get('phase', 0.0), peak.get('is_harmonic', False),
                                        peak.get('is_incommensurate', False), peak.get('is_comb_tooth', False)])
            
            # Add Z component data
            if 'mz_peaks' in fc_data and isinstance(fc_data['mz_peaks'], list):
                for peak in fc_data['mz_peaks']:
                    if isinstance(peak, dict) and 'frequency' in peak and 'amplitude' in peak:
                        writer.writerow(['Z', peak.get('frequency'), peak.get('amplitude'), 
                                        peak.get('phase', 0.0), peak.get('is_harmonic', False),
                                        peak.get('is_incommensurate', False), peak.get('is_comb_tooth', False)])
        
        # Move the cursor to the beginning of the StringIO object
        csv_data.seek(0)
        
        # Create a response with the CSV data
        filename = f"{result_name}_frequency_data.csv"
        return send_file(
            csv_data,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        app.logger.error(f"Error exporting data for {result_name}: {str(e)}")
        import traceback as tb
        app.logger.error(tb.format_exc())
        flash(f"Error exporting data: {str(e)}", "error")
        return redirect(url_for('dashboard'))

if __name__ == "__main__":
    main()
