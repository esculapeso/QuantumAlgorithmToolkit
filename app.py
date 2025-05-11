"""
Flask web application to run quantum simulations and view results.
"""

import os
import io
import json
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Import simulation modules
from simulation import run_simulation
from utils import ensure_dependencies
import quantum_circuits

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "quantum-secret-key")

# Ensure required packages are available
ensure_dependencies()

@app.route('/')
def index():
    """Render the main page."""
    # Get available circuit types
    circuit_types = [
        'penrose',
        'qft_basic',
        'comb_generator',
        'comb_twistor',
        'graphene_fc'
    ]
    
    # Find the most recent simulation results
    results_dir = "results"
    recent_results = []
    
    if os.path.exists(results_dir):
        # List all result directories
        result_dirs = sorted([d for d in os.listdir(results_dir) 
                              if os.path.isdir(os.path.join(results_dir, d))],
                             key=lambda x: os.path.getmtime(os.path.join(results_dir, x)),
                             reverse=True)
        
        # Get the 5 most recent
        for rd in result_dirs[:5]:
            result_path = os.path.join(results_dir, rd)
            analysis_file = os.path.join(result_path, 'analysis_results.json')
            
            if os.path.exists(analysis_file):
                with open(analysis_file, 'r') as f:
                    analysis = json.load(f)
                
                # Extract basic info
                recent_results.append({
                    'name': rd,
                    'date': datetime.fromtimestamp(os.path.getmtime(result_path)).strftime('%Y-%m-%d %H:%M:%S'),
                    'circuit_type': analysis.get('parameters', {}).get('circuit_type', 'unknown'),
                    'qubits': analysis.get('parameters', {}).get('qubits', 0),
                    'has_figures': any(f.endswith('.png') for f in os.listdir(result_path)) if os.path.exists(result_path) else False
                })
    
    return render_template('index.html', circuit_types=circuit_types, recent_results=recent_results)

@app.route('/run_simulation', methods=['POST'])
def run_sim():
    """Run a simulation with the provided parameters."""
    # Extract parameters from form
    circuit_type = request.form.get('circuit_type', 'penrose')
    qubits = int(request.form.get('qubits', 3))
    drive_steps = int(request.form.get('drive_steps', 5))
    time_points = int(request.form.get('time_points', 100))
    max_time = float(request.form.get('max_time', 10.0))
    drive_param = float(request.form.get('drive_param', 0.9))
    init_state = request.form.get('init_state', 'superposition')
    
    # Generate a unique name for this run
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    param_set_name = f"web_run_{qubits}q_{timestamp}"
    
    # Run the simulation
    result = run_simulation(
        circuit_type=circuit_type,
        qubits=qubits,
        shots=8192,  # Fixed for now
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
    
    # Redirect to the results page
    return redirect(url_for('view_result', result_name=f"{circuit_type}_{param_set_name}"))

@app.route('/results/<result_name>')
def view_result(result_name):
    """View a specific simulation result."""
    results_dir = "results"
    result_path = os.path.join(results_dir, result_name)
    
    if not os.path.exists(result_path):
        return "Result not found", 404
    
    # Load analysis results
    analysis_file = os.path.join(result_path, 'analysis_results.json')
    analysis = {}
    
    if os.path.exists(analysis_file):
        with open(analysis_file, 'r') as f:
            analysis = json.load(f)
    
    # Get list of image files
    image_files = [f for f in os.listdir(result_path) if f.endswith('.png')]
    images = []
    
    for img_file in image_files:
        img_path = os.path.join(result_path, img_file)
        with open(img_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
            images.append({
                'name': img_file,
                'data': img_data
            })
    
    return render_template('result.html', 
                          result_name=result_name, 
                          analysis=analysis, 
                          images=images)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)