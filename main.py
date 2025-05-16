"""
Main module for quantum simulation package.
Entry point for running simulations with different parameters and web interface.
"""

import os
import sys
import numpy as np
import datetime
import traceback
import threading
import uuid
import time
import matplotlib.pyplot as plt

# Import custom modules
import config
from utils import ensure_dependencies
from quantum_circuits import get_circuit_generator
from simulation import run_simulation, run_parameter_scan, generate_parameter_grid
from visualization import plot_circuit_diagram
# Import database models
from models import db, User, SimulationResult, ParameterSweep

# Import Flask web application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import glob
import json
from functools import wraps

# Import Flask-Login for user management
from flask_login import LoginManager, login_user, logout_user, current_user, login_required

# Import Flask app
from app import app

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
    # Check if admin user exists, if not create it
    try:
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            admin.username = 'admin'
            admin.role = 'admin'
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
    except Exception as e:
        print(f"Error setting up admin user: {e}")

# Error handlers
@app.errorhandler(500)
def internal_server_error(error):
    """Custom error handler for 500 errors to ensure API routes still return JSON."""
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal server error", "message": str(error)}), 500
    return render_template('error.html', error=error), 500

@app.errorhandler(404)
def page_not_found(error):
    """Custom error handler for 404 errors to ensure API routes still return JSON."""
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found", "message": "The requested resource was not found"}), 404
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(Exception)
def handle_exception(error):
    """Custom error handler to catch unhandled exceptions and ensure API routes return JSON."""
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

@app.route('/run_sim', methods=['POST'])
def run_sim():
    """Run a simulation with the provided parameters."""
    try:
        # Extract parameters from form with safe defaults
        circuit_type = request.form.get('circuit_type', 'string_twistor_fc')
        
        # Handle form parameters with defaults
        try:
            qubits = int(request.form.get('qubits', 9))
        except (TypeError, ValueError):
            qubits = 9
            
        try:
            shots = int(request.form.get('shots', 1024))
        except (TypeError, ValueError):
            shots = 1024
            
        try:
            drive_steps = int(request.form.get('drive_steps', 5))
        except (TypeError, ValueError):
            drive_steps = 5
            
        try:
            time_points = int(request.form.get('time_points', 100))
        except (TypeError, ValueError):
            time_points = 100
            
        try:
            max_time = float(request.form.get('max_time', 10.0))
        except (TypeError, ValueError):
            max_time = 10.0
            
        try:
            drive_param = float(request.form.get('drive_param', 0.9))
        except (TypeError, ValueError):
            drive_param = 0.9
            
        init_state = request.form.get('init_state', '0')
        
        # Generate a unique result name based on timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        result_name = f"{circuit_type}_{qubits}q_{timestamp}"
        
        print(f"Starting simulation with circuit_type={circuit_type}, qubits={qubits}")
        
        # Import simulation directly here to avoid circular imports
        from simulation import run_simulation
        
        # Run the simulation
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
        
        # Check for errors
        if result and 'error' in result:
            flash(f"Simulation error: {result['error']}", 'danger')
            return redirect(url_for('index'))
        
        # Save the result to the database
        from db_utils import save_simulation_to_db
        db_record = save_simulation_to_db(result, result_name)
        
        # Redirect to the result page
        return redirect(url_for('view_result', result_name=result_name))
    
    except Exception as e:
        # Handle any errors
        flash(f"Error running simulation: {str(e)}", 'danger')
        import traceback
        traceback.print_exc()
        return redirect(url_for('index'))

@app.route('/view/<result_name>')
def view_result(result_name):
    """View a specific simulation result."""
    try:
        # Get simulation result from database
        from db_utils import get_simulation_by_name
        simulation = get_simulation_by_name(result_name)
        
        # If simulation exists in database, get its data
        if simulation:
            # Format simulation data for display
            result_data = {
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
                'created_at': simulation.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'elapsed_time': simulation.elapsed_time,
                'time_crystal': simulation.time_crystal_detected,
                'incommensurate': simulation.incommensurate_count,
                'comb_detected': simulation.linear_combs_detected or simulation.log_combs_detected,
                'is_starred': simulation.is_starred,
                'figures': []
            }
            
            # Check if result directory exists
            results_path = simulation.results_path
            if not os.path.exists(results_path):
                results_path = os.path.join('results', result_name)
            
            # Get figure paths for display
            figure_path = os.path.join(results_path, 'figures')
            if os.path.exists(figure_path):
                # Find all PNG files
                figure_files = sorted(glob.glob(os.path.join(figure_path, '*.png')))
                
                # Add figure information
                for fig_file in figure_files:
                    fig_name = os.path.basename(fig_file)
                    result_data['figures'].append({
                        'name': fig_name,
                        'path': f"/figure/{result_name}/{fig_name}",
                        'title': fig_name.replace('.png', '').replace('_', ' ').title()
                    })
            
            # Render the result view template
            return render_template('result.html', result=result_data)
            
        else:
            # Simulation not found
            flash("Simulation result not found.", 'warning')
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f"Error viewing result: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    try:
        # Get simulation result from database
        from db_utils import get_simulation_by_name
        simulation = get_simulation_by_name(result_name)
        
        if simulation:
            # Use the path from the database record
            results_path = simulation.results_path
            figure_path = os.path.join(results_path, 'figures', figure_name)
            
            # Check if figure exists at the expected path
            if os.path.exists(figure_path):
                return send_file(figure_path)
            
            # If not found, try the standardized path
            figure_path = os.path.join('results', result_name, 'figures', figure_name)
            if os.path.exists(figure_path):
                return send_file(figure_path)
        
        # If figure not found after all attempts
        return "Figure not found", 404
        
    except Exception as e:
        print(f"Error retrieving figure: {str(e)}")
        return "Error retrieving figure", 500

@app.route('/toggle_star/<int:sim_id>', methods=['POST'])
@login_required
def toggle_star(sim_id):
    """Toggle the starred status of a simulation."""
    try:
        sim = SimulationResult.query.get(sim_id)
        if not sim:
            return jsonify({"error": "Simulation not found"}), 404
            
        # Toggle the starred status
        sim.is_starred = not sim.is_starred
        db.session.commit()
        
        return jsonify({"success": True, "is_starred": sim.is_starred})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/simulations')
@login_required
def simulations():
    """Show a list of all simulations with filter options."""
    # Get filter parameters from query string
    circuit_type = request.args.get('circuit_type')
    min_qubits = request.args.get('min_qubits')
    max_qubits = request.args.get('max_qubits')
    time_crystal = request.args.get('time_crystal')
    comb_detected = request.args.get('comb_detected')
    is_starred = request.args.get('is_starred')
    
    # Convert string parameters to appropriate types
    if min_qubits:
        try:
            min_qubits = int(min_qubits)
        except ValueError:
            min_qubits = None
    
    if max_qubits:
        try:
            max_qubits = int(max_qubits)
        except ValueError:
            max_qubits = None
    
    if time_crystal:
        time_crystal = time_crystal.lower() == 'true'
    else:
        time_crystal = None
    
    if comb_detected:
        comb_detected = comb_detected.lower() == 'true'
    else:
        comb_detected = None
    
    if is_starred:
        is_starred = is_starred.lower() == 'true'
    else:
        is_starred = None
    
    # Search simulations with filters
    from db_utils import search_simulations
    simulations = search_simulations(
        circuit_type=circuit_type,
        min_qubits=min_qubits,
        max_qubits=max_qubits,
        time_crystal_detected=time_crystal,
        comb_detected=comb_detected,
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
            'drive_param': sim.drive_param,
            'created_at': sim.created_at.strftime('%Y-%m-%d %H:%M'),
            'time_crystal': sim.time_crystal_detected,
            'incommensurate': sim.incommensurate_count,
            'comb_detected': sim.linear_combs_detected or sim.log_combs_detected,
            'is_starred': sim.is_starred
        })
    
    # Get unique circuit types for filter dropdown
    circuit_types = db.session.query(SimulationResult.circuit_type).distinct().all()
    circuit_types = [ct[0] for ct in circuit_types]
    
    return render_template('simulations.html', 
                          simulations=sim_results,
                          circuit_types=circuit_types,
                          filters={
                              'circuit_type': circuit_type,
                              'min_qubits': min_qubits,
                              'max_qubits': max_qubits,
                              'time_crystal': time_crystal,
                              'comb_detected': comb_detected,
                              'is_starred': is_starred
                          })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)