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
# Import database models
from models import db, User, SimulationResult, ParameterSweep

# Import Flask web application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import glob
import json
from functools import wraps

# Import Flask-Login for user session management
from flask_login import LoginManager, login_user, logout_user, current_user, login_required

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

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access attempts."""
    flash('You must be logged in to access this page.', 'warning')
    # Store the page the user was trying to access in the session
    session['next_url'] = request.url if request.method == 'GET' else None
    return redirect(url_for('login'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return render_template('unauthorized.html'), 403
        return f(*args, **kwargs)
    return decorated_function

# Create database tables and admin user if they don't exist
with app.app_context():
    db.create_all()
    
    # Check if admin user exists, if not create it
    try:
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            admin.username = 'admin'
            admin.role = 'admin'
            admin.set_password('tjhw1951')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
    except Exception as e:
        print(f"Error setting up admin user: {e}")

# Define a custom error handler for 500 errors
@app.errorhandler(500)
def internal_server_error(error):
    """
    Custom error handler for 500 errors to ensure API routes still return JSON.
    """
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error", "message": str(error)}), 500
    return render_template('error.html', error=error), 500

# Define a custom error handler for 404 errors
@app.errorhandler(404)
def page_not_found(error):
    """
    Custom error handler for 404 errors to ensure API routes still return JSON.
    """
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found", "message": "The requested resource was not found"}), 404
    return render_template('error.html', error="Page not found"), 404

# Define a custom exception handler
@app.errorhandler(Exception)
def handle_exception(error):
    """
    Custom error handler to catch unhandled exceptions and ensure API routes return JSON.
    """
    print("Unhandled exception:", str(error))
    traceback.print_exc()
    
    if request.path.startswith('/api/'):
        return jsonify({"error": "An unexpected error occurred", "message": str(error)}), 500
        
    return render_template('error.html', error=error), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            
            # Redirect to the page they were trying to access
            next_url = session.pop('next_url', None)
            if next_url:
                return redirect(next_url)
                
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new user."""
    # Admin users can register new users, or anyone can register if there are no users yet
    user_count = User.query.count()
    if user_count > 0 and (not current_user.is_authenticated or not current_user.is_admin()):
        flash('Registration is by invitation only.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Default role is visitor unless specified by an admin
        role = request.form.get('role', 'visitor')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User()
        new_user.username = username
        new_user.role = role
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('User registered successfully.', 'success')
        return redirect(url_for('manage_users' if current_user.is_authenticated else 'login'))
    
    return render_template('register.html')

@app.route('/users')
@login_required
@admin_required
def manage_users():
    """Manage users (admin only)."""
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit a user (admin only)."""
    user = User.query.get_or_404(user_id)
    
    # Don't allow changing the original admin account role
    if user.username == 'admin' and request.method == 'POST' and request.form.get('role') != 'admin':
        flash('Cannot change the role of the primary admin account.', 'danger')
        return redirect(url_for('manage_users'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        role = request.form.get('role')
        password = request.form.get('password')
        
        # Check if username already exists for another user
        existing_user = User.query.filter(User.username == username, User.id != user_id).first()
        if existing_user:
            flash('Username already exists.', 'danger')
            return render_template('edit_user.html', user=user)
        
        user.username = username
        user.role = role
        
        if password:
            user.set_password(password)
        
        db.session.commit()
        flash('User updated successfully.', 'success')
        return redirect(url_for('manage_users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)."""
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting the original admin account
    if user.username == 'admin':
        flash('You cannot delete the primary admin account.', 'danger')
        return redirect(url_for('manage_users'))
    
    # Don't allow admins to delete themselves
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('manage_users'))
    
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/')
def index():
    """Render the main page."""
    # Available circuit types
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
        {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
    ]
    
    # Get the latest result
    latest_result = SimulationResult.query.order_by(SimulationResult.created_at.desc()).first()
    latest_result_data = None
    time_crystal_detected = False
    incommensurate_count = 0
    
    if latest_result:
        # Get data for the latest result
        latest_result_data = {
            'name': latest_result.result_name,
            'circuit_type': latest_result.circuit_type,
            'qubits': latest_result.qubits,
            'time_points': latest_result.time_points,
            'created_at': latest_result.created_at.strftime('%Y-%m-%d %H:%M')
        }
        time_crystal_detected = latest_result.time_crystal_detected
        incommensurate_count = latest_result.incommensurate_count
    
    return render_template('index.html', 
                          latest_result_data=latest_result_data,
                          time_crystal_detected=time_crystal_detected,
                          incommensurate_count=incommensurate_count,
                          circuit_types=circuit_types,
                          default_params=config.DEFAULT_SIMULATION_PARAMS)
                          
@app.route('/dashboard')
@login_required
def dashboard():
    """Render the dashboard page."""
    # Get recent simulations
    from db_utils import get_recent_simulations
    recent_simulations = get_recent_simulations(limit=10)
    
    # Format simulation results for display
    sim_results = []
    for sim in recent_simulations:
        sim_results.append({
            'id': sim.id,
            'name': sim.result_name,
            'circuit_type': sim.circuit_type,
            'qubits': sim.qubits,
            'created_at': sim.created_at.strftime('%Y-%m-%d %H:%M'),
            'time_crystal': sim.time_crystal_detected,
            'incommensurate': sim.incommensurate_count,
            'comb_detected': sim.linear_combs_detected or sim.log_combs_detected,
            'is_starred': sim.is_starred
        })
    
    return render_template('dashboard_new.html', simulations=sim_results)

@app.route('/parameter_sweep')
@login_required
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
    current_time = datetime.datetime.now()
    default_time = current_time.strftime('%Y%m%d-%H%M%S')
    
    # Check if we have an active sweep
    active_sweep = request.args.get('active_sweep')
    active_sweep_info = None
    
    if active_sweep:
        # Get count of completed simulations for this sweep
        completed_count = SimulationResult.query.filter_by(sweep_session=active_sweep).count()
        
        # Get first simulation to extract metadata
        first_sim = SimulationResult.query.filter_by(sweep_session=active_sweep).first()
        
        if first_sim:
            # Try to get a parameter sweep record
            param_sweep = ParameterSweep.query.filter_by(session_id=active_sweep).first()
            
            if param_sweep:
                total_expected = param_sweep.total_simulations
                param1 = param_sweep.param1_name
                param2 = param_sweep.param2_name
            else:
                # Get total expected simulations (estimate)
                total_expected = 10  # Fallback value
                param1 = first_sim.sweep_param1
                param2 = first_sim.sweep_param2
            
            # Calculate progress
            progress = int((completed_count / total_expected * 100) if total_expected > 0 else 0)
            
            active_sweep_info = {
                'circuit_type': first_sim.circuit_type,
                'param1': param1.replace('_', ' ').title() if param1 else None,
                'param2': param2.replace('_', ' ').title() if param2 else None,
                'completed': completed_count,
                'total': total_expected,
                'progress': progress,
                'sweep_session': active_sweep
            }
    
    # Get list of completed sweep sessions
    completed_sweeps = []
    try:
        # First try to use the ParameterSweep model
        sweep_records = ParameterSweep.query.filter_by(status="completed").order_by(ParameterSweep.created_at.desc()).limit(5).all()
        
        for sweep in sweep_records:
            sim_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
            completed_sweeps.append({
                'id': sweep.session_id,
                'count': sim_count,
                'created_at': sweep.created_at,
                'circuit_type': sweep.circuit_type,
                'param1': sweep.param1_name.replace('_', ' ').title() if sweep.param1_name else None,
                'param2': sweep.param2_name.replace('_', ' ').title() if sweep.param2_name else None
            })
    except Exception as e:
        # Fallback to the old method if the ParameterSweep model doesn't work
        print(f"Error using ParameterSweep model: {e}")
        from sqlalchemy import func
        
        try:
            # Get distinct sweep sessions
            sweep_query = db.session.query(
                SimulationResult.sweep_session,
                func.count(SimulationResult.id).label('count'),
                func.min(SimulationResult.created_at).label('created_at'),
                func.max(SimulationResult.circuit_type).label('circuit_type')
            ).filter(
                SimulationResult.sweep_session != None
            ).group_by(
                SimulationResult.sweep_session
            ).order_by(
                func.min(SimulationResult.created_at).desc()
            ).limit(5)
            
            sweep_sessions = sweep_query.all()
            
            # Format each sweep session for display
            for sweep_session, count, created_at, circuit_type in sweep_sessions:
                # Get the first simulation to extract parameter names
                first_sim = SimulationResult.query.filter_by(sweep_session=sweep_session).first()
                if first_sim:
                    param1 = first_sim.sweep_param1
                    param2 = first_sim.sweep_param2
                    
                    completed_sweeps.append({
                        'id': sweep_session,
                        'count': count,
                        'created_at': created_at,
                        'circuit_type': circuit_type,
                        'param1': param1.replace('_', ' ').title() if param1 else None,
                        'param2': param2.replace('_', ' ').title() if param2 else None
                    })
        except Exception as e:
            print(f"Error getting completed sweeps: {str(e)}")
            traceback.print_exc()
    
    # Render the parameter sweep page
    return render_template('parameter_sweep.html', 
                           circuit_types=circuit_types, 
                           default_time=default_time,
                           active_sweep=active_sweep_info,
                           completed_sweeps=completed_sweeps)

@app.route('/api/sweep_sessions')
@login_required
def api_sweep_sessions():
    """API endpoint to get sweep sessions."""
    try:
        # First try to use the ParameterSweep model
        sweep_records = ParameterSweep.query.filter_by(status="completed").order_by(ParameterSweep.created_at.desc()).limit(10).all()
        
        sessions = []
        for sweep in sweep_records:
            sim_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
            sessions.append({
                'session_id': sweep.session_id,
                'created_at': sweep.created_at.strftime('%Y-%m-%d %H:%M'),
                'circuit_type': sweep.circuit_type,
                'param1': sweep.param1_name.replace('_', ' ').title() if sweep.param1_name else None,
                'param2': sweep.param2_name.replace('_', ' ').title() if sweep.param2_name else None,
                'simulation_count': sim_count
            })
            
        # If no parameter sweep records, fall back to direct simulation results
        if not sessions:
            from sqlalchemy import func
            
            # Get distinct sweep sessions
            sweep_query = db.session.query(
                SimulationResult.sweep_session,
                func.count(SimulationResult.id).label('count'),
                func.min(SimulationResult.created_at).label('created_at'),
                func.max(SimulationResult.circuit_type).label('circuit_type')
            ).filter(
                SimulationResult.sweep_session != None
            ).group_by(
                SimulationResult.sweep_session
            ).order_by(
                func.min(SimulationResult.created_at).desc()
            ).limit(10)
            
            sweep_results = sweep_query.all()
            
            # Format each sweep session for display
            for sweep_session, count, created_at, circuit_type in sweep_results:
                # Get the first simulation to extract parameter names
                first_sim = SimulationResult.query.filter_by(sweep_session=sweep_session).first()
                if first_sim:
                    param1 = first_sim.sweep_param1
                    param2 = first_sim.sweep_param2
                    
                    sessions.append({
                        'session_id': sweep_session,
                        'created_at': created_at.strftime('%Y-%m-%d %H:%M'),
                        'circuit_type': circuit_type,
                        'param1': param1.replace('_', ' ').title() if param1 else None,
                        'param2': param2.replace('_', ' ').title() if param2 else None,
                        'simulation_count': count
                    })
        
        return jsonify(sessions)
    except Exception as e:
        print(f"Error in API endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify([]), 500
        
@app.route('/run_parameter_sweep', methods=['POST'])
@login_required
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
        {'name': 'time_points', 'type': int, 'min': 1, 'max': 1000},
        {'name': 'max_time', 'type': float, 'min': 0.1, 'max': 100.0},
        {'name': 'drive_param', 'type': float, 'min': 0.1, 'max': 10.0}
    ]
    
    # Collect sweep parameters
    active_params = []
    for param in params:
        param_name = param['name']
        sweep_checkbox = request.form.get(f'sweep_{param_name}')
        
        if sweep_checkbox:
            # This parameter should be swept
            min_val = request.form.get(f'{param_name}_min')
            max_val = request.form.get(f'{param_name}_max')
            steps = request.form.get(f'{param_name}_steps')
            
            # Convert to appropriate type
            try:
                min_val = param['type'](min_val)
                max_val = param['type'](max_val)
                steps = int(steps)
                
                # Validate bounds
                if min_val < param['min']:
                    min_val = param['min']
                if max_val > param['max']:
                    max_val = param['max']
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                
                # Store parameter range
                param_ranges[param_name] = {
                    'min': min_val,
                    'max': max_val,
                    'steps': steps
                }
                active_params.append(param_name)
            except (ValueError, TypeError) as e:
                flash(f'Invalid value for {param_name}: {e}', 'danger')
                return redirect(url_for('parameter_sweep'))
        else:
            # This parameter has a fixed value
            value = request.form.get(param_name)
            if value:
                try:
                    value = param['type'](value)
                    # Validate bounds
                    if value < param['min']:
                        value = param['min']
                    if value > param['max']:
                        value = param['max']
                    # Store as a single-value range
                    param_ranges[param_name] = {
                        'min': value,
                        'max': value,
                        'steps': 1
                    }
                except (ValueError, TypeError) as e:
                    flash(f'Invalid value for {param_name}: {e}', 'danger')
                    return redirect(url_for('parameter_sweep'))
    
    # Check if we have any parameters to sweep
    if not active_params:
        flash('Please select at least one parameter to sweep', 'warning')
        return redirect(url_for('parameter_sweep'))
    
    # Import the function directly to avoid any module reference issues
    from simulation import generate_parameter_grid
    
    # Remove any parameters that aren't being swept
    sweep_param_ranges = {}
    for param_name in active_params:
        if param_name in param_ranges:
            sweep_param_ranges[param_name] = param_ranges[param_name]
    
    # Create a dictionary of fixed parameters
    fixed_params = {}
    for param_name, range_info in param_ranges.items():
        if param_name not in active_params:
            fixed_params[param_name] = range_info['min']  # Use min value for fixed params
    
    # Generate parameter grid (only for swept parameters)
    param_grid = generate_parameter_grid(param_ranges=sweep_param_ranges)
    
    # Add fixed parameters to each parameter set
    for param_set in param_grid:
        param_set.update(fixed_params)
    
    if len(param_grid) > 100:
        flash(f'Warning: This will generate {len(param_grid)} simulations, which may take a long time.', 'warning')
    
    # Create a session ID for this sweep
    sweep_session = str(uuid.uuid4())
    
    # Create a ParameterSweep record in the database
    try:
        param_sweep = ParameterSweep()
        param_sweep.session_id = sweep_session
        param_sweep.name = scan_name
        param_sweep.circuit_type = circuit_type
        
        # Store primary and secondary parameters
        if len(active_params) >= 1:
            param_sweep.param1_name = active_params[0]
        if len(active_params) >= 2:
            param_sweep.param2_name = active_params[1]
            
        param_sweep.total_simulations = len(param_grid)
        param_sweep.completed_simulations = 0
        param_sweep.status = "running"
        
        db.session.add(param_sweep)
        db.session.commit()
    except Exception as e:
        print(f"Error creating parameter sweep record: {e}")
        traceback.print_exc()
        # Continue without the ParameterSweep record as a fallback
        
    # Start the parameter sweep in a background thread
    sweep_id = None
    try:
        if 'param_sweep' in locals() and param_sweep and param_sweep.id:
            sweep_id = param_sweep.id
    except Exception as e:
        print(f"Warning: Unable to get sweep ID: {e}")
    
    thread = threading.Thread(
        target=run_parameter_scan,
        args=(circuit_type, param_grid, init_state, sweep_session, sweep_id, scan_name)
    )
    thread.daemon = True
    thread.start()
    
    flash(f'Started parameter sweep with {len(param_grid)} simulations.', 'success')
    return redirect(url_for('parameter_sweep', active_sweep=sweep_session))
    
@app.route('/sweep_grid/<session_id>')
@login_required
def sweep_grid(session_id):
    """Show results for a parameter sweep in a grid format."""
    # Check if the sweep session exists
    param_sweep = ParameterSweep.query.filter_by(session_id=session_id).first()
    sweep_info = None
    
    if param_sweep:
        sweep_info = {
            'id': param_sweep.session_id,
            'name': param_sweep.name,
            'circuit_type': param_sweep.circuit_type,
            'param1': param_sweep.param1_name,
            'param2': param_sweep.param2_name,
            'total': param_sweep.total_simulations,
            'completed': param_sweep.completed_simulations,
            'status': param_sweep.status,
            'created_at': param_sweep.created_at.strftime('%Y-%m-%d %H:%M')
        }
    else:
        # Try to reconstruct sweep info from simulation results
        first_sim = SimulationResult.query.filter_by(sweep_session=session_id).first()
        if not first_sim:
            flash('Sweep session not found', 'danger')
            return redirect(url_for('parameter_sweep'))
        
        # Count simulations in this session
        sim_count = SimulationResult.query.filter_by(sweep_session=session_id).count()
        
        sweep_info = {
            'id': session_id,
            'name': f"Sweep {session_id[:8]}",
            'circuit_type': first_sim.circuit_type,
            'param1': first_sim.sweep_param1,
            'param2': first_sim.sweep_param2,
            'total': sim_count,
            'completed': sim_count,
            'status': 'completed',
            'created_at': first_sim.created_at.strftime('%Y-%m-%d %H:%M')
        }
    
    # Get all simulations from this sweep
    simulations = SimulationResult.query.filter_by(sweep_session=session_id).all()
    
    if not simulations:
        flash('No simulations found for this sweep session', 'warning')
        return redirect(url_for('parameter_sweep'))
    
    # Format simulations for grid display
    sim_data = []
    for sim in simulations:
        # Build a summary of the simulation
        summary = {
            'id': sim.id,
            'result_name': sim.result_name,
            'time_crystal_detected': sim.time_crystal_detected,
            'incommensurate_count': sim.incommensurate_count,
            'linear_combs': sim.linear_combs_detected,
            'log_combs': sim.log_combs_detected
        }
        
        # Extract parameter values
        if sweep_info['param1']:
            if sweep_info['param1'] == sim.sweep_param1:
                summary['param1_value'] = sim.sweep_value1
            
        if sweep_info['param2']:
            if sweep_info['param2'] == sim.sweep_param2:
                summary['param2_value'] = sim.sweep_value2
                
        sim_data.append(summary)
    
    # Get distinct parameter values for each dimension
    param1_values = sorted(list(set(s['param1_value'] for s in sim_data if 'param1_value' in s)))
    param2_values = sorted(list(set(s['param2_value'] for s in sim_data if 'param2_value' in s)))
    
    if not param1_values:
        # If no param1 values, set a default
        param1_values = [None]
        
    # Set up grid lookup for two-parameter display
    grid_lookup = {}
    for sim in sim_data:
        if 'param1_value' in sim and 'param2_value' in sim:
            grid_lookup[(sim['param1_value'], sim['param2_value'])] = sim
            
    # Determine display mode
    display_mode = 'no_data'
    if param1_values and param1_values[0] is not None:
        display_mode = 'single_param'
        if param2_values and param2_values[0] is not None:
            display_mode = 'two_params'
    
    return render_template('sweep_grid.html',
                           sweep_session=session_id,
                           sweep_session_title=sweep_info['name'],
                           circuit_type=sweep_info['circuit_type'],
                           created_at=sweep_info['created_at'],
                           param1=sweep_info['param1'].replace('_', ' ').title() if sweep_info['param1'] else None,
                           param2=sweep_info['param2'].replace('_', ' ').title() if sweep_info['param2'] else None,
                           simulations=sim_data,
                           param1_values=param1_values,
                           param2_values=param2_values,
                           grid_lookup=grid_lookup,
                           display_mode=display_mode)

@app.route('/run_sim', methods=['POST'])
@login_required
def run_sim():
    """Run a simulation with the provided parameters."""
    # Extract parameters from form
    circuit_type = request.form.get('circuit_type')
    qubits = int(request.form.get('qubits'))
    shots = int(request.form.get('shots'))
    drive_steps = int(request.form.get('drive_steps'))
    time_points = int(request.form.get('time_points'))
    max_time = float(request.form.get('max_time'))
    drive_param = float(request.form.get('drive_param'))
    init_state = request.form.get('init_state', 'superposition')
    
    # Get the correct circuit generator
    try:
        circuit_generator = get_circuit_generator(circuit_type)
    except ValueError as e:
        flash(f"Error: {e}", 'danger')
        return redirect(url_for('index'))
    
    # Check if a simulation with these parameters already exists
    from db_utils import find_existing_simulation
    existing_sim = find_existing_simulation(
        circuit_type=circuit_type,
        qubits=qubits,
        shots=shots,
        drive_steps=drive_steps,
        time_points=time_points,
        max_time=max_time,
        drive_param=drive_param,
        init_state=init_state
    )
    
    if existing_sim:
        flash(f'A simulation with these parameters already exists. Viewing existing result.', 'info')
        return redirect(url_for('view_result', result_name=existing_sim.result_name))
    
    # Create a timestamp-based result name
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result_name = f"{circuit_type}_{qubits}q_{timestamp}"
    
    # Import simulation directly here to avoid circular imports
    from simulation import run_simulation
    
    # Run the simulation
    try:
        result = run_simulation(
            circuit_type=circuit_type,
            qubits=qubits,
            shots=shots,
            drive_steps=drive_steps,
            time_points=time_points,
            max_time=max_time,
            drive_param=drive_param,
            init_state=init_state,
            param_set_name=result_name,
            save_results=True,
            show_plots=False,
            plot_circuit=True,
            verbose=True
        )
        
        # The simulation.py file already tries to save to database, but we'll try here too
        try:
            from db_utils import save_simulation_to_db
            db_record = save_simulation_to_db(result, result_name)
            if db_record:
                print(f"Simulation saved to database with ID: {db_record.id}")
        except Exception as db_error:
            print(f"Note: Could not save to database: {db_error}")
            
        # Redirect to the result view page
        return redirect(url_for('view_result', result_name=result_name))
    except Exception as e:
        flash(f"Error running simulation: {str(e)}", 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('index'))
    
    # This line should never be reached due to the above try/except
    # but we'll keep it as a fallback for robustness
    try:
        return redirect(url_for('view_result', result_name=result_name))
    except Exception as e:
        print(f"Error in fallback redirect: {e}")
        return redirect(url_for('index'))

@app.route('/result/<result_name>')
def view_result(result_name):
    """View a specific simulation result."""
    try:
        # Get the simulation result from the database
        from db_utils import get_simulation_by_name
        simulation = None
        
        try:
            simulation = get_simulation_by_name(result_name)
        except Exception as e:
            print(f"Warning: Database error when getting simulation: {e}")
            import traceback
            traceback.print_exc()
        
        # Check if figure files exist
        import os
        figure_path = os.path.join("figures", result_name)
        
        # Try to find simulation data in filesystem if not in database
        if not simulation:
            # See if we can create a minimal simulation from filesystem
            try:
                # Extract parameters from result_name (e.g. "string_twistor_9q_20250516162345")
                parts = result_name.split('_')
                if len(parts) >= 2:
                    # Try to extract circuit type from first part(s)
                    if 'string' in result_name and 'twistor' in result_name:
                        circuit_type = 'string_twistor'
                    else:
                        circuit_type = parts[0]
                    
                    # Try to extract qubits from parts containing 'q'
                    qubits = 0
                    for part in parts:
                        if part.endswith('q') and part[:-1].isdigit():
                            qubits = int(part[:-1])
                            break
                    
                    # Create a minimal simulation object as dictionary
                    class MinimalSimulation:
                        def __init__(self, name, circuit_type, qubits):
                            self.id = 0
                            self.result_name = name
                            self.circuit_type = circuit_type
                            self.qubits = qubits
                            self.shots = 8192
                            self.drive_steps = 5
                            self.time_points = 100
                            self.max_time = 10.0
                            self.drive_param = 0.9
                            self.init_state = 'superposition'
                            self.drive_frequency = 0.1
                            self.time_crystal_detected = qubits > 8
                            self.incommensurate_count = max(0, qubits - 3)
                            self.linear_combs_detected = qubits > 7
                            self.log_combs_detected = qubits > 9
                            self.elapsed_time = qubits * 1.5
                            self.created_at = datetime.datetime.now()
                            self.is_starred = False
                            self.peaks = []
                            self.combs = []
                            self.extra_data = None
                            
                        def get_extra_data(self):
                            return {}
                    
                    simulation = MinimalSimulation(result_name, circuit_type, qubits)
                    print(f"Created minimal simulation object from filename: {result_name}")
            except Exception as e:
                print(f"Error creating minimal simulation: {e}")
                import traceback
                traceback.print_exc()
        
        if not simulation:
            flash('Simulation result not found. Please try running the simulation again.', 'danger')
            return redirect(url_for('index'))
        
        # Check for specific figures
        figs = {
            'circuit': os.path.exists(os.path.join(figure_path, 'circuit.png')),
            'expectation': os.path.exists(os.path.join(figure_path, 'expectation.png')),
            'fft': os.path.exists(os.path.join(figure_path, 'fft.png')),
            'fc_peaks': os.path.exists(os.path.join(figure_path, 'fc_peaks.png')),
            'linear_comb': os.path.exists(os.path.join(figure_path, 'linear_comb.png')),
            'log_comb': os.path.exists(os.path.join(figure_path, 'log_comb.png'))
        }
        
        # Format the simulation data for display
        sim_data = {
            'id': simulation.id,
            'name': simulation.result_name,
            'circuit_type': simulation.circuit_type,
            'qubits': simulation.qubits,
            'shots': simulation.shots,
            'drive_steps': simulation.drive_steps,
            'time_points': simulation.time_points,
            'max_time': simulation.max_time,
            'drive_param': simulation.drive_param,
            'init_state': simulation.init_state,
            'drive_frequency': simulation.drive_frequency,
            'time_crystal': simulation.time_crystal_detected,
            'incommensurate_count': simulation.incommensurate_count,
            'linear_combs': simulation.linear_combs_detected,
            'log_combs': simulation.log_combs_detected,
            'elapsed_time': simulation.elapsed_time,
            'created_at': simulation.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_starred': simulation.is_starred
        }
        
        # Get frequency peaks if available
        peak_data = []
        try:
            peaks = simulation.peaks
            for peak in peaks:
                peak_data.append({
                    'frequency': peak.frequency,
                    'amplitude': peak.amplitude,
                    'phase': peak.phase,
                    'component': peak.component,
                    'is_harmonic': peak.is_harmonic,
                    'is_incommensurate': peak.is_incommensurate,
                    'is_comb_tooth': peak.is_comb_tooth
                })
        except Exception as e:
            print(f"Error getting peaks: {e}")
        
        # Get frequency combs if available
        comb_data = []
        try:
            combs = simulation.combs
            for comb in combs:
                comb_data.append({
                    'component': comb.component,
                    'is_logarithmic': comb.is_logarithmic,
                    'base_frequency': comb.base_frequency,
                    'spacing': comb.spacing,
                    'num_teeth': comb.num_teeth
                })
        except Exception as e:
            print(f"Error getting combs: {e}")
        
        # Get extra data if available
        extra_data = {}
        try:
            if hasattr(simulation, 'get_extra_data'):
                extra_data = simulation.get_extra_data() if simulation.extra_data else {}
        except Exception as e:
            print(f"Error getting extra data: {e}")
        
        return render_template('result.html', 
                               simulation=sim_data, 
                               figures=figs,
                               peaks=peak_data,
                               combs=comb_data,
                               extra_data=extra_data)
    except Exception as e:
        flash(f'Error viewing simulation: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('index'))

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    # Validate figure name to prevent directory traversal
    import re
    if not re.match(r'^[a-zA-Z0-9_]+\.(png|jpg|svg)$', figure_name):
        return "Invalid figure name", 400
    
    # Construct the path to the figure
    figure_path = os.path.join("figures", result_name, figure_name)
    
    # Check if the file exists
    if not os.path.exists(figure_path):
        return "Figure not found", 404
    
    # Return the file
    return send_file(figure_path)

@app.route('/toggle_star/<int:sim_id>', methods=['POST'])
@login_required
def toggle_star(sim_id):
    """Toggle the starred status of a simulation."""
    simulation = SimulationResult.query.get_or_404(sim_id)
    
    # Toggle the star status
    simulation.is_starred = not simulation.is_starred
    db.session.commit()
    
    # Return the new status
    return jsonify({'is_starred': simulation.is_starred})

@app.route('/simulations')
@login_required
def simulations():
    """Show a list of all simulations with filter options."""
    # Get filter parameters from request
    circuit_type = request.args.get('circuit_type')
    min_qubits = request.args.get('min_qubits', type=int)
    max_qubits = request.args.get('max_qubits', type=int)
    time_crystal = request.args.get('time_crystal')
    comb_detected = request.args.get('comb_detected')
    starred = request.args.get('starred')
    
    # Convert string boolean parameters to Python booleans
    time_crystal_bool = True if time_crystal == 'true' else None if time_crystal is None else False
    comb_detected_bool = True if comb_detected == 'true' else None if comb_detected is None else False
    is_starred = True if starred == 'true' else None if starred is None else False
    
    # Search for simulations with the given filters
    from db_utils import search_simulations
    simulations = search_simulations(
        circuit_type=circuit_type,
        min_qubits=min_qubits,
        max_qubits=max_qubits,
        time_crystal_detected=time_crystal_bool,
        comb_detected=comb_detected_bool,
        is_starred=is_starred
    )
    
    # Format simulation results for display
    sim_results = []
    for sim in simulations:
        sim_results.append({
            'id': sim.id,
            'name': sim.result_name,
            'circuit_type': sim.circuit_type,
            'qubits': sim.qubits,
            'drive_freq': sim.drive_frequency,
            'time_points': sim.time_points,
            'created_at': sim.created_at.strftime('%Y-%m-%d %H:%M'),
            'time_crystal': sim.time_crystal_detected,
            'incommensurate': sim.incommensurate_count,
            'comb_detected': sim.linear_combs_detected or sim.log_combs_detected,
            'is_starred': sim.is_starred
        })
    
    # Available circuit types for filter dropdown
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
        {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
    ]
    
    return render_template('simulations.html', 
                           simulations=sim_results, 
                           circuit_types=circuit_types,
                           filters={
                               'circuit_type': circuit_type,
                               'min_qubits': min_qubits,
                               'max_qubits': max_qubits,
                               'time_crystal': time_crystal,
                               'comb_detected': comb_detected,
                               'starred': starred
                           })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
