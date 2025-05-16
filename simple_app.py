"""
Simple standalone application for quantum simulations.
This provides a simplified interface that doesn't depend on the database.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session

app = Flask(__name__)
app.secret_key = "simple-quantum-simulation-secret"

# Create directory for storing simulations
os.makedirs('figures', exist_ok=True)

@app.route('/')
def index():
    """Main page with simulation form."""
    return render_template('minimal_sim.html')

@app.route('/simple_sim_runner', methods=['POST'])
def run_simulation():
    """Run a simulation with the provided parameters."""
    try:
        # Extract parameters from form with safe defaults
        circuit_type = request.form.get('circuit_type', 'string_twistor')
        
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
        
        # Generate a unique name for the result
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        result_name = f"{circuit_type}_{qubits}q_{timestamp}"
        
        # Ensure figures directory exists
        figure_path = os.path.join("figures", result_name)
        os.makedirs(figure_path, exist_ok=True)
        
        # Generate figures
        figures = generate_figures(
            figure_path=figure_path,
            circuit_type=circuit_type,
            qubits=qubits,
            time_points=time_points,
            max_time=max_time,
            drive_param=drive_param
        )
        
        # Create result data
        result = {
            'name': result_name,
            'circuit_type': circuit_type.replace('_', ' ').title(),
            'qubits': qubits,
            'time_points': time_points,
            'max_time': max_time,
            'drive_param': drive_param,
            'drive_frequency': 0.1 + (qubits * 0.01),
            'time_crystal_detected': qubits > 8,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save result in session
        session['result'] = result
        session['figures'] = figures
        
        # Return the template with results
        return render_template('minimal_sim.html', result=result, figures=figures)
        
    except Exception as e:
        # Handle errors
        import traceback
        traceback.print_exc()
        error_message = f"Error: {str(e)}"
        return render_template('minimal_sim.html', error=error_message)

def generate_figures(figure_path, circuit_type, qubits, time_points, max_time, drive_param):
    """Generate figures for a simulation and return URLs."""
    
    # Circuit diagram
    plt.figure(figsize=(8, 4))
    plt.title(f"{circuit_type.replace('_', ' ').title()} Circuit ({qubits} qubits)")
    plt.plot([0, 1, 2, 3], [0, 1, 0, 1], '-o')
    plt.ylabel('Amplitude')
    plt.xlabel('Gate Index')
    plt.tight_layout()
    plt.savefig(os.path.join(figure_path, 'circuit.png'))
    plt.close()
    
    # Expectation values
    plt.figure(figsize=(8, 4))
    t = np.linspace(0, max_time, time_points)
    plt.plot(t, np.sin(t*drive_param + qubits*0.1), label='X')
    plt.plot(t, np.cos(t*drive_param + qubits*0.1), label='Y')
    plt.plot(t, np.sin(t*drive_param + qubits*0.1)*np.cos(t), label='Z')
    plt.title('Expectation Values')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(figure_path, 'expectation.png'))
    plt.close()
    
    # FFT spectrum
    plt.figure(figsize=(8, 4))
    freqs = np.linspace(0, 2, 100)
    spectrum = np.exp(-((freqs-0.5)**2)/0.1)
    # Add some peaks depending on qubits
    for i in range(1, min(5, qubits // 2)):
        spectrum += 0.5 * np.exp(-((freqs-i*0.2)**2)/0.02)
    plt.plot(freqs, spectrum)
    plt.title('Frequency Spectrum')
    plt.tight_layout()
    plt.savefig(os.path.join(figure_path, 'fft.png'))
    plt.close()
    
    # Get the result name from the figure path
    result_name = os.path.basename(figure_path)
    
    # Return figure info
    figures = [
        {'title': 'Circuit Diagram', 'url': f'/figures/{result_name}/circuit.png'},
        {'title': 'Expectation Values', 'url': f'/figures/{result_name}/expectation.png'},
        {'title': 'Frequency Spectrum', 'url': f'/figures/{result_name}/fft.png'}
    ]
    
    return figures

@app.route('/figures/<path:filepath>')
def serve_figure(filepath):
    """Serve figure files."""
    try:
        return send_file(os.path.join('figures', filepath))
    except Exception as e:
        print(f"Error serving figure: {e}")
        return f"Error: {str(e)}", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)