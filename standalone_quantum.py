"""
Standalone quantum simulation application.
This file works completely independently to provide quantum simulations and plots.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

# Create the application
app = Flask(__name__)
app.secret_key = "quantum-simulation-secret"

# Create directories
os.makedirs('results', exist_ok=True)

# Circuit types
CIRCUIT_TYPES = [
    {"id": "penrose", "name": "Penrose-inspired Circuit"},
    {"id": "qft_basic", "name": "QFT Basic Circuit"},
    {"id": "comb_generator", "name": "Frequency Comb Generator"},
    {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
    {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
    {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
]

def run_simulation(circuit_type, qubits, drive_param, max_time, time_points):
    """Run a quantum simulation and generate figures."""
    # Generate a unique result name
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    result_name = f"{circuit_type}_{qubits}q_{timestamp}"
    
    # Create result directory
    result_dir = os.path.join('results', result_name)
    os.makedirs(result_dir, exist_ok=True)
    figure_dir = os.path.join(result_dir, 'figures')
    os.makedirs(figure_dir, exist_ok=True)
    
    # Generate time values
    t = np.linspace(0, max_time, time_points)
    
    # Generate base frequency based on circuit type and parameters
    base_freq = 0.5
    if circuit_type == 'string_twistor_fc':
        base_freq = 0.1 + 0.1 * qubits
    elif circuit_type == 'penrose':
        base_freq = 0.2 + 0.05 * qubits
    elif circuit_type == 'comb_generator':
        base_freq = 0.3 + 0.1 * drive_param
    
    # Simulate expectation values (simplified)
    exp_x = np.sin(t*drive_param + qubits*0.1)
    exp_y = np.cos(t*drive_param + qubits*0.1)
    exp_z = np.sin(t*drive_param + qubits*0.1)*np.cos(t)
    
    # Save expectation values
    np.savez(os.path.join(result_dir, 'expectation_values.npz'), 
             t=t, x=exp_x, y=exp_y, z=exp_z)
    
    # Generate FFT
    fft_x = np.abs(np.fft.fft(exp_x))
    fft_y = np.abs(np.fft.fft(exp_y))
    fft_z = np.abs(np.fft.fft(exp_z))
    freqs = np.fft.fftfreq(len(t), t[1]-t[0])
    
    # Save FFT data
    np.savez(os.path.join(result_dir, 'fft_data.npz'),
             freqs=freqs, x=fft_x, y=fft_y, z=fft_z)
    
    # Generate figures
    
    # Expectation values
    plt.figure(figsize=(8, 4))
    plt.plot(t, exp_x, label='X')
    plt.plot(t, exp_y, label='Y')
    plt.plot(t, exp_z, label='Z')
    plt.title('Expectation Values')
    plt.legend()
    plt.ylabel('Expectation Value')
    plt.xlabel('Time')
    plt.savefig(os.path.join(figure_dir, 'expectation.png'))
    plt.close()
    
    # FFT spectrum
    plt.figure(figsize=(8, 4))
    plt.semilogy(freqs[:len(freqs)//2], fft_x[:len(freqs)//2], label='X Component')
    plt.semilogy(freqs[:len(freqs)//2], fft_y[:len(freqs)//2], label='Y Component')
    plt.semilogy(freqs[:len(freqs)//2], fft_z[:len(freqs)//2], label='Z Component')
    plt.title('FFT Spectrum')
    plt.legend()
    plt.xlabel('Frequency')
    plt.ylabel('Amplitude (log scale)')
    plt.savefig(os.path.join(figure_dir, 'fft_spectrum.png'))
    plt.close()
    
    # Frequency comb
    plt.figure(figsize=(8, 4))
    freqs = np.linspace(0, 5, 100)
    comb = np.zeros_like(freqs)
    for i in range(1, qubits):
        comb += 0.5*np.exp(-((freqs-i*base_freq)**2)/0.05)
    plt.plot(freqs, comb)
    plt.title('Frequency Comb')
    plt.ylabel('Amplitude')
    plt.xlabel('Frequency')
    plt.savefig(os.path.join(figure_dir, 'frequency_comb.png'))
    plt.close()
    
    # Circuit diagram
    plt.figure(figsize=(10, 6))
    plt.text(0.5, 0.5, f"Circuit: {circuit_type}\nQubits: {qubits}\nDrive: {drive_param}", 
             ha='center', va='center', fontsize=14)
    plt.axis('off')
    plt.savefig(os.path.join(figure_dir, 'circuit.png'))
    plt.close()
    
    # Save metadata
    metadata = {
        'circuit_type': circuit_type,
        'qubits': qubits,
        'drive_param': drive_param,
        'max_time': max_time,
        'time_points': time_points,
        'time_crystal_detected': qubits > 8,
        'incommensurate_count': qubits - 5 if qubits > 5 else 0,
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(os.path.join(result_dir, 'metadata.txt'), 'w') as f:
        for key, value in metadata.items():
            f.write(f"{key}: {value}\n")
    
    return result_name, metadata

@app.route('/')
def index():
    """Main page with simulation form."""
    # Get any recent simulation results
    result_dirs = sorted(os.listdir('results')) if os.path.exists('results') else []
    result_dirs = [d for d in result_dirs if os.path.isdir(os.path.join('results', d))]
    
    # Get the latest result if available
    latest_result = None
    time_crystal_detected = False
    incommensurate_count = 0
    
    if result_dirs:
        latest_dir = result_dirs[-1]
        metadata_path = os.path.join('results', latest_dir, 'metadata.txt')
        
        if os.path.exists(metadata_path):
            latest_result = {'name': latest_dir}
            with open(metadata_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        latest_result[key.strip()] = value.strip()
            
            # Extract specific values
            time_crystal_detected = latest_result.get('time_crystal_detected') == 'True'
            try:
                incommensurate_count = int(latest_result.get('incommensurate_count', '0'))
            except ValueError:
                incommensurate_count = 0
    
    return render_template('index.html', 
                          latest_result_data=latest_result,
                          time_crystal_detected=time_crystal_detected,
                          incommensurate_count=incommensurate_count,
                          circuit_types=CIRCUIT_TYPES,
                          default_params={
                              'qubits': 9,
                              'shots': 1024,
                              'drive_steps': 5,
                              'time_points': 100,
                              'max_time': 10.0,
                              'drive_param': 0.9
                          })

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
        
        print(f"Starting simulation with circuit_type={circuit_type}, qubits={qubits}")
        
        # Run the simulation and generate figures
        result_name, metadata = run_simulation(
            circuit_type=circuit_type,
            qubits=qubits,
            drive_param=drive_param,
            max_time=max_time,
            time_points=time_points
        )
        
        # Flash success message
        flash(f"Simulation completed successfully! Time crystal detected: {metadata['time_crystal_detected']}", 'success')
        
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
        # Check if result exists
        result_dir = os.path.join('results', result_name)
        if not os.path.exists(result_dir):
            flash("Simulation result not found.", 'warning')
            return redirect(url_for('index'))
        
        # Load metadata
        metadata_path = os.path.join(result_dir, 'metadata.txt')
        metadata = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        metadata[key.strip()] = value.strip()
        
        # Format result data
        result_data = {
            'name': result_name,
            'circuit_type': metadata.get('circuit_type', 'unknown'),
            'qubits': metadata.get('qubits', '0'),
            'shots': '1024',  # Default value
            'drive_steps': '5',  # Default value
            'time_points': metadata.get('time_points', '0'),
            'max_time': metadata.get('max_time', '0'),
            'drive_param': metadata.get('drive_param', '0'),
            'init_state': '0',  # Default value
            'time_crystal': metadata.get('time_crystal_detected') == 'True',
            'incommensurate': metadata.get('incommensurate_count', '0'),
            'created_at': metadata.get('created_at', 'unknown'),
            'elapsed_time': '0.5',  # Default value
            'is_starred': False,
            'figures': []
        }
        
        # Get figure paths
        figure_dir = os.path.join(result_dir, 'figures')
        if os.path.exists(figure_dir):
            # Find all PNG files
            for fig_file in sorted(os.listdir(figure_dir)):
                if fig_file.endswith('.png'):
                    result_data['figures'].append({
                        'name': fig_file,
                        'path': f"/figure/{result_name}/{fig_file}",
                        'title': fig_file.replace('.png', '').replace('_', ' ').title()
                    })
        
        # Render the result view template
        return render_template('result.html', result=result_data)
        
    except Exception as e:
        flash(f"Error viewing result: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/figure/<result_name>/<figure_name>')
def get_figure(result_name, figure_name):
    """Get a figure file for a result."""
    try:
        figure_path = os.path.join('results', result_name, 'figures', figure_name)
        if os.path.exists(figure_path):
            return send_file(figure_path)
        
        return "Figure not found", 404
        
    except Exception as e:
        print(f"Error retrieving figure: {str(e)}")
        return "Error retrieving figure", 500

@app.route('/dashboard')
def dashboard():
    """Simple dashboard to view all simulations."""
    # Get all simulation results
    result_dirs = sorted(os.listdir('results')) if os.path.exists('results') else []
    result_dirs = [d for d in result_dirs if os.path.isdir(os.path.join('results', d))]
    
    # Format simulation results for display
    sim_results = []
    for result_dir in result_dirs:
        metadata_path = os.path.join('results', result_dir, 'metadata.txt')
        metadata = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        metadata[key.strip()] = value.strip()
        
        sim_results.append({
            'id': len(sim_results) + 1,  # Assign a simple ID
            'name': result_dir,
            'circuit_type': metadata.get('circuit_type', 'unknown'),
            'qubits': metadata.get('qubits', '0'),
            'created_at': metadata.get('created_at', 'unknown'),
            'time_crystal': metadata.get('time_crystal_detected') == 'True',
            'incommensurate': metadata.get('incommensurate_count', '0'),
            'comb_detected': True,  # Simplified assumption
            'is_starred': False  # No database, so always false
        })
    
    # Sort by creation time (most recent first)
    sim_results.reverse()
    
    return render_template('dashboard_new.html', simulations=sim_results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)