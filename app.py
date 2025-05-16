"""
Flask web application to run quantum simulations and view results.
"""
import os
import glob
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import simulation
import utils
import visualization
import config

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
        result = simulation.run_simulation(
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

if __name__ == '__main__':
    # Check dependencies
    utils.ensure_dependencies()
    app.run(host='0.0.0.0', port=5000, debug=True)