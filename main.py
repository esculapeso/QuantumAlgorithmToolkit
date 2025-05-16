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
