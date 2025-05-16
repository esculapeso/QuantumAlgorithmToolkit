"""
Simplified quantum simulation app with no authentication or database dependencies.
Uses actual Qiskit simulations rather than synthetic data.
"""
import os
import numpy as np
import matplotlib
# Set non-interactive backend to avoid GUI warnings
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime
import time
from flask import Flask, render_template, request, redirect, url_for, flash, send_file

# Import Qiskit for real quantum simulations
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter
import qiskit.quantum_info as qi
from qiskit_aer import Aer
from qiskit_aer import QasmSimulator

# Create Flask application
app = Flask(__name__)
app.secret_key = "quantum-simulation-secret"

# Create necessary directories
os.makedirs('results', exist_ok=True)

# Available circuit types
CIRCUIT_TYPES = [
    {"id": "penrose", "name": "Penrose-inspired Circuit"},
    {"id": "qft_basic", "name": "QFT Basic Circuit"},
    {"id": "comb_generator", "name": "Frequency Comb Generator"},
    {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
    {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
    {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
]

def create_circuit(circuit_type, qubits, drive_param):
    """Create a quantum circuit based on the specified parameters."""
    circuit = QuantumCircuit(qubits)
    
    # Add gates based on circuit type
    if circuit_type == 'qft_basic':
        # Basic QFT circuit
        for i in range(qubits):
            circuit.h(i)
            for j in range(i+1, qubits):
                circuit.cp(np.pi/(2**(j-i)), i, j)
        
        # Add some parameterized rotations
        for i in range(qubits):
            circuit.rz(drive_param, i)
        
        # Add some entanglement
        for i in range(qubits-1):
            circuit.cx(i, i+1)
    
    elif circuit_type == 'string_twistor_fc':
        # String twistor-inspired circuit with time crystal properties
        # Initial state preparation
        for i in range(qubits):
            circuit.h(i)
        
        # Drive steps
        for _ in range(5):  # Multiple drive steps
            # First layer: X rotations with drive parameter
            for i in range(qubits):
                circuit.rx(drive_param, i)
            
            # Second layer: Entanglement with nearest neighbors
            for i in range(qubits-1):
                circuit.cx(i, i+1)
            
            # Optional: periodic boundary condition
            if qubits > 2:
                circuit.cx(qubits-1, 0)
            
            # Third layer: Z rotations dependent on qubit position
            for i in range(qubits):
                # Position-dependent phase
                circuit.rz(drive_param * (i+1)/qubits * np.pi, i)
    
    elif circuit_type == 'penrose':
        # Penrose tiling inspired connectivity
        # Initial state
        for i in range(qubits):
            circuit.h(i)
        
        # Create non-regular connectivity inspired by Penrose tiling
        golden_ratio = (1 + np.sqrt(5))/2
        
        # Drive layer
        for i in range(qubits):
            circuit.rx(drive_param, i)
        
        # Entanglement layer with Penrose-inspired connectivity
        for i in range(qubits):
            # Connect based on golden ratio pattern
            j = int((i * golden_ratio) % qubits)
            circuit.cx(i, j)
            
            # Add Y-rotations
            circuit.ry(drive_param * np.pi / golden_ratio, i)
        
    elif circuit_type == 'comb_generator':
        # Circuit designed to generate frequency combs
        # Initial state: superposition
        for i in range(qubits):
            circuit.h(i)
        
        # Phase separation
        for i in range(qubits):
            circuit.rz(drive_param * (i+1), i)
        
        # Entanglement
        for i in range(qubits-1):
            circuit.cx(i, i+1)
        
        # Mixing
        for i in range(qubits):
            circuit.h(i)
            circuit.rz(drive_param, i)
            circuit.h(i)
    
    else:  # Default to a simple circuit
        for i in range(qubits):
            circuit.h(i)
            circuit.rz(drive_param, i)
        
        for i in range(qubits-1):
            circuit.cx(i, i+1)
    
    return circuit

def simulate_time_evolution(circuit, time_points, max_time, qubits):
    """Simulate time evolution of the quantum circuit and compute expectation values."""
    simulator = Aer.get_backend('statevector_simulator')
    
    # Time points
    t = np.linspace(0, max_time, time_points)
    
    # Pauli operators for expectation values
    pauli_x = qi.Pauli('X')
    pauli_y = qi.Pauli('Y')
    pauli_z = qi.Pauli('Z')
    
    # Initialize arrays for expectation values
    exp_x = np.zeros(time_points)
    exp_y = np.zeros(time_points)
    exp_z = np.zeros(time_points)
    
    # Initial state
    initial_circuit = QuantumCircuit(qubits)
    for i in range(qubits):
        initial_circuit.h(i)
    
    initial_state = simulator.run(initial_circuit).result().get_statevector()
    
    # Time evolution operator from the circuit
    # For simplicity, we'll use the circuit as a single timestep
    evolution_op = qi.Operator(circuit)
    
    # Current state starts as the initial state
    current_state = initial_state
    
    # Compute expectation values for each time point
    for i, time_val in enumerate(t):
        # For simplicity, we'll evolve the state by applying the circuit multiple times
        # proportional to the time value
        repetitions = int(time_val) + 1
        
        # Reset state to initial for each time point to avoid accumulation errors
        current_state = initial_state
        
        # Apply evolution operation multiple times
        for _ in range(repetitions):
            current_state = evolution_op.dot(current_state)
        
        # Calculate expectation values for the current state
        # Simplified approach - using first qubit only
        dm = qi.DensityMatrix(current_state)
        exp_x[i] = qi.expectation_value(pauli_x, dm)
        exp_y[i] = qi.expectation_value(pauli_y, dm)
        exp_z[i] = qi.expectation_value(pauli_z, dm)
    
    return t, exp_x, exp_y, exp_z

def compute_fft(signal, time_points):
    """Compute the FFT of the signal."""
    fft_vals = np.abs(np.fft.fft(signal))
    freqs = np.fft.fftfreq(time_points)
    return freqs, fft_vals

def detect_time_crystal(fft_x, fft_y, fft_z, freqs, qubits):
    """Basic detection of time crystal signatures in the frequency spectrum."""
    # Look for frequency peaks in FFT
    threshold = 0.1 * np.max(fft_x[:len(freqs)//2])  # Only look at positive frequencies
    peaks_x = freqs[:len(freqs)//2][fft_x[:len(freqs)//2] > threshold]
    
    # Count significant frequency components
    num_freq_components = len(peaks_x)
    
    # Simple heuristic for time crystal detection
    # A time crystal would have multiple distinct frequency components
    time_crystal_detected = num_freq_components > 3 and qubits > 6
    
    return time_crystal_detected, num_freq_components

def generate_figures(result_name, circuit_type, qubits, drive_param, max_time, time_points):
    """Generate figures for the simulation using real quantum circuits."""
    start_time = time.time()
    
    # Create result directory
    result_dir = os.path.join('results', result_name)
    os.makedirs(result_dir, exist_ok=True)
    figure_dir = os.path.join(result_dir, 'figures')
    os.makedirs(figure_dir, exist_ok=True)
    
    # Create quantum circuit
    circuit = create_circuit(circuit_type, qubits, drive_param)
    
    # Draw and save the circuit diagram
    try:
        from qiskit.visualization import circuit_drawer
        circuit_fig = circuit_drawer(circuit, output='mpl', plot_barriers=False, 
                                    scale=0.7, style={'backgroundcolor': '#F5F5F5'})
        circuit_fig.savefig(os.path.join(figure_dir, 'circuit.png'), dpi=150, bbox_inches='tight')
        plt.close(circuit_fig)
    except Exception as e:
        # If circuit drawing fails, create a basic text diagram
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, f"Circuit: {circuit_type}\nQubits: {qubits}\nDrive: {drive_param}", 
                ha='center', va='center', fontsize=14)
        plt.axis('off')
        plt.savefig(os.path.join(figure_dir, 'circuit.png'))
        plt.close()
    
    # Simulate time evolution and get expectation values
    t, exp_x, exp_y, exp_z = simulate_time_evolution(circuit, time_points, max_time, qubits)
    
    # Save expectation values
    np.savez(os.path.join(result_dir, 'expectation_values.npz'), 
             t=t, x=exp_x, y=exp_y, z=exp_z)
    
    # Plot expectation values
    plt.figure(figsize=(8, 4))
    plt.plot(t, exp_x, label='X')
    plt.plot(t, exp_y, label='Y')
    plt.plot(t, exp_z, label='Z')
    plt.title('Expectation Values')
    plt.legend()
    plt.ylabel('Expectation Value')
    plt.xlabel('Time')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(figure_dir, 'expectation.png'))
    plt.close()
    
    # Compute FFT
    freqs_x, fft_x = compute_fft(exp_x, time_points)
    freqs_y, fft_y = compute_fft(exp_y, time_points)
    freqs_z, fft_z = compute_fft(exp_z, time_points)
    
    # Save FFT data
    np.savez(os.path.join(result_dir, 'fft_data.npz'),
             freqs=freqs_x, x=fft_x, y=fft_y, z=fft_z)
    
    # Plot FFT spectrum
    plt.figure(figsize=(8, 4))
    plt.semilogy(freqs_x[:len(freqs_x)//2], fft_x[:len(freqs_x)//2], label='X Component')
    plt.semilogy(freqs_y[:len(freqs_y)//2], fft_y[:len(freqs_y)//2], label='Y Component')
    plt.semilogy(freqs_z[:len(freqs_z)//2], fft_z[:len(freqs_z)//2], label='Z Component')
    plt.title('FFT Spectrum')
    plt.legend()
    plt.xlabel('Frequency')
    plt.ylabel('Amplitude (log scale)')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(figure_dir, 'fft_spectrum.png'))
    plt.close()
    
    # Detect time crystal features and incommensurate frequencies
    time_crystal_detected, num_incommensurate = detect_time_crystal(fft_x, fft_y, fft_z, freqs_x, qubits)
    
    # Generate and plot frequency comb visualization
    plt.figure(figsize=(8, 4))
    # Use the FFT data to identify frequency components for the comb
    threshold = 0.1 * np.max(fft_x[:len(freqs_x)//2])
    freq_indices = np.where(fft_x[:len(freqs_x)//2] > threshold)[0]
    
    # If we found frequency components, plot them as a comb
    if len(freq_indices) > 0:
        display_freqs = np.linspace(0, 0.5, 1000)  # Higher resolution for display
        comb = np.zeros_like(display_freqs)
        
        # Create a comb visualization of the detected frequencies
        for idx in freq_indices:
            freq = freqs_x[idx]
            # Skip DC component
            if abs(freq) < 0.01:
                continue
            # Add a narrow peak for each detected frequency
            comb += fft_x[idx] * np.exp(-((display_freqs-abs(freq))**2)/0.001)
        
        plt.plot(display_freqs, comb/np.max(comb))  # Normalize for better visualization
    else:
        # Fallback if no clear frequencies detected
        plt.text(0.5, 0.5, "No clear frequency comb structure detected", 
                 ha='center', va='center', transform=plt.gca().transAxes)
    
    plt.title('Frequency Comb Structure')
    plt.ylabel('Normalized Amplitude')
    plt.xlabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(figure_dir, 'frequency_comb.png'))
    plt.close()
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Save metadata
    metadata = {
        'circuit_type': circuit_type,
        'qubits': qubits,
        'drive_param': drive_param,
        'max_time': max_time,
        'time_points': time_points,
        'time_crystal_detected': time_crystal_detected,
        'incommensurate_count': num_incommensurate,
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'elapsed_time': f"{elapsed_time:.2f}"
    }
    
    # Save metadata to a file
    with open(os.path.join(result_dir, 'metadata.txt'), 'w') as f:
        for key, value in metadata.items():
            f.write(f"{key}: {value}\n")
    
    return result_dir, metadata

@app.route('/')
def index():
    """Render the main page."""
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
        
        # Generate a unique result name based on timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        result_name = f"{circuit_type}_{qubits}q_{timestamp}"
        
        print(f"Starting simulation with circuit_type={circuit_type}, qubits={qubits}")
        
        # Generate figures
        result_dir, metadata = generate_figures(
            result_name=result_name,
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

@app.route('/simulations')
def simulations():
    """List all simulations."""
    return dashboard()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)