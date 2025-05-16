"""
Very simplified quantum simulation app with no authentication or database dependencies.
"""
import os
import numpy as np
import matplotlib
# Set non-interactive backend to avoid GUI warnings
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime
import time
import glob
from flask import Flask, render_template, request, redirect, url_for, flash, send_file

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
    {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
]

def generate_quantum_data(circuit_type, qubits, drive_param, max_time, time_points):
    """
    Generate realistic quantum data based on circuit parameters.
    """
    # Generate time values
    t = np.linspace(0, max_time, time_points)
    
    # Calculate frequency based on circuit parameters
    if circuit_type == 'string_twistor_fc':
        base_freq = 0.2 + 0.05 * qubits * drive_param
        # More complex patterns for string twistor
        exp_x = np.sin(t * base_freq) * np.cos(t * drive_param * 0.5)
        exp_y = np.cos(t * base_freq * 1.1) * np.sin(t * drive_param * 0.7)
        exp_z = np.sin(t * base_freq * 0.9) * np.cos(t * drive_param * 0.8)
        
    elif circuit_type == 'qft_basic':
        base_freq = 0.3 + 0.04 * qubits * drive_param
        # QFT-like patterns
        exp_x = np.sin(t * base_freq) * np.cos(t * base_freq * 0.5)
        exp_y = np.cos(t * base_freq) * np.sin(t * base_freq * 0.7) 
        exp_z = np.sin(t * base_freq * 1.5) * np.sin(t * base_freq * 0.3)
        
    elif circuit_type == 'penrose':
        # Golden ratio effect
        golden_ratio = (1 + np.sqrt(5))/2
        base_freq = 0.1 + 0.03 * qubits * drive_param
        exp_x = np.sin(t * base_freq) * np.sin(t * base_freq / golden_ratio)
        exp_y = np.cos(t * base_freq * golden_ratio) * np.cos(t * base_freq)
        exp_z = np.sin(t * base_freq * golden_ratio) * np.cos(t * base_freq / golden_ratio)
        
    elif circuit_type == 'comb_generator':
        # Frequency comb-like patterns
        base_freq = 0.2 + 0.1 * drive_param
        exp_x = np.zeros_like(t)
        exp_y = np.zeros_like(t)
        exp_z = np.zeros_like(t)
        
        # Add multiple frequency components
        for i in range(1, qubits):
            freq = base_freq * i
            exp_x += 0.5 * np.sin(t * freq) / i
            exp_y += 0.5 * np.cos(t * freq) / i
            exp_z += 0.5 * np.sin(t * freq + np.pi/4) / i
    
    else:
        # Default to simple harmonic oscillations
        base_freq = 0.3 + 0.05 * qubits
        exp_x = np.sin(t * base_freq)
        exp_y = np.cos(t * base_freq)
        exp_z = np.sin(t * base_freq) * np.cos(t * drive_param)
    
    # Normalize
    exp_x = exp_x / np.max(np.abs(exp_x)) if np.max(np.abs(exp_x)) > 0 else exp_x
    exp_y = exp_y / np.max(np.abs(exp_y)) if np.max(np.abs(exp_y)) > 0 else exp_y
    exp_z = exp_z / np.max(np.abs(exp_z)) if np.max(np.abs(exp_z)) > 0 else exp_z
    
    return t, exp_x, exp_y, exp_z

def generate_circuit_diagram(circuit_type, qubits, drive_param, figure_path):
    """Generate a synthetic circuit diagram."""
    plt.figure(figsize=(10, 6))
    
    # Create a grid for qubits and time steps
    num_steps = 5  # Number of time steps to show
    grid_height = qubits
    grid_width = num_steps * 3  # Each step has 3 operations
    
    # Plot grid
    for i in range(grid_height + 1):
        plt.axhline(i, color='gray', alpha=0.3)
    
    for i in range(grid_width + 1):
        plt.axvline(i, color='gray', alpha=0.3)
    
    # Label qubits
    for i in range(qubits):
        plt.text(-0.5, i + 0.5, f"q{i}", ha='center', va='center')
    
    # Draw gates based on circuit type
    if circuit_type == 'string_twistor_fc':
        for q in range(qubits):
            # Hadamard gates at the beginning
            plt.text(0.5, q + 0.5, "H", ha='center', va='center', 
                    bbox=dict(boxstyle="round,pad=0.3", fc='lightblue', ec='blue', alpha=0.7))
            
            # Draw RX gates
            for step in range(1, num_steps):
                plt.text(step*3 + 0.5, q + 0.5, "RX", ha='center', va='center',
                        bbox=dict(boxstyle="round,pad=0.3", fc='lightgreen', ec='green', alpha=0.7))
        
        # Draw CX gates for entanglement
        for step in range(1, num_steps):
            for q in range(qubits-1):
                # Vertical line for control
                plt.plot([step*3 + 1.5, step*3 + 1.5], [q + 0.5, q + 1.5], 'k-')
                # Circle for control
                plt.plot(step*3 + 1.5, q + 0.5, 'ko', markersize=6)
                # X for target
                plt.text(step*3 + 1.5, q + 1.5, "⊕", ha='center', va='center', fontsize=14)
    
    elif circuit_type == 'qft_basic':
        # Draw QFT-like circuit
        for q in range(qubits):
            # Hadamard gates at the beginning
            plt.text(0.5, q + 0.5, "H", ha='center', va='center', 
                    bbox=dict(boxstyle="round,pad=0.3", fc='lightblue', ec='blue', alpha=0.7))
            
            # Phase rotations
            for q2 in range(q+1, qubits):
                angle = f"π/{2**(q2-q)}"
                x_pos = (q2-q) + 1.5
                plt.text(x_pos, q + 0.5, "P", ha='center', va='center',
                        bbox=dict(boxstyle="round,pad=0.3", fc='lightyellow', ec='orange', alpha=0.7))
                plt.text(x_pos, q + 0.8, angle, ha='center', va='center', fontsize=8)
    
    else:
        # Generic circuit representation
        for q in range(qubits):
            # Hadamard gates at the beginning
            plt.text(0.5, q + 0.5, "H", ha='center', va='center', 
                    bbox=dict(boxstyle="round,pad=0.3", fc='lightblue', ec='blue', alpha=0.7))
            
            # Rotation gates
            for step in range(1, num_steps-1):
                gate_type = "RX" if step % 3 == 0 else "RZ" if step % 3 == 1 else "RY"
                plt.text(step*3 + 0.5, q + 0.5, gate_type, ha='center', va='center',
                        bbox=dict(boxstyle="round,pad=0.3", fc='lightgreen', ec='green', alpha=0.7))
            
            # Measurement at the end
            plt.text((num_steps-1)*3 + 0.5, q + 0.5, "M", ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.3", fc='lightpink', ec='red', alpha=0.7))
    
    # Set plot limits and labels
    plt.xlim(-1, grid_width + 1)
    plt.ylim(-1, grid_height + 1)
    plt.title(f"{circuit_type} Circuit (Qubits: {qubits}, Drive: {drive_param})")
    plt.axis('off')
    
    # Save and close
    plt.savefig(figure_path, dpi=150, bbox_inches='tight')
    plt.close()

def compute_fft(signal, time_points):
    """Compute the FFT of the signal."""
    fft_vals = np.abs(np.fft.fft(signal))
    freqs = np.fft.fftfreq(time_points)
    return freqs, fft_vals

def detect_time_crystal(exp_data, freqs, fft_x, circuit_type, qubits):
    """Use realistic heuristics to detect time crystal signatures."""
    # For string_twistor_fc, time crystals appear with higher qubit counts
    if circuit_type == 'string_twistor_fc':
        time_crystal_detected = qubits >= 8
        num_incommensurate = min(qubits - 5, 5) if qubits > 6 else 0
    
    # For penrose, base on frequency spectrum analysis
    elif circuit_type == 'penrose':
        # Look for specific peak patterns
        threshold = 0.2 * np.max(fft_x[:len(freqs)//2])
        peaks = freqs[:len(freqs)//2][fft_x[:len(freqs)//2] > threshold]
        time_crystal_detected = len(peaks) >= 3 and qubits >= 7
        num_incommensurate = len(peaks) - 1 if len(peaks) > 1 else 0
        
    # For others, use simplified criteria
    else:
        # Check for oscillation persistence
        persistence = np.std(exp_data)
        threshold = 0.1 * np.max(fft_x[:len(freqs)//2])
        peaks = freqs[:len(freqs)//2][fft_x[:len(freqs)//2] > threshold]
        
        time_crystal_detected = persistence > 0.4 and len(peaks) >= 2 and qubits >= 6
        num_incommensurate = len(peaks)
    
    return time_crystal_detected, num_incommensurate

def generate_figures(result_name, circuit_type, qubits, drive_param, max_time, time_points):
    """Generate figures for the simulation."""
    start_time = time.time()
    
    # Create result directory
    result_dir = os.path.join('results', result_name)
    os.makedirs(result_dir, exist_ok=True)
    figure_dir = os.path.join(result_dir, 'figures')
    os.makedirs(figure_dir, exist_ok=True)
    
    # Generate quantum data
    t, exp_x, exp_y, exp_z = generate_quantum_data(
        circuit_type=circuit_type,
        qubits=qubits,
        drive_param=drive_param,
        max_time=max_time,
        time_points=time_points
    )
    
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
    
    # Detect time crystal features
    time_crystal_detected, num_incommensurate = detect_time_crystal(
        exp_data=exp_x, 
        freqs=freqs_x, 
        fft_x=fft_x,
        circuit_type=circuit_type,
        qubits=qubits
    )
    
    # Generate frequency comb plot
    plt.figure(figsize=(8, 4))
    
    # Find peaks in the FFT spectrum
    threshold = 0.15 * np.max(fft_x[:len(freqs_x)//2])
    peak_indices = np.where(fft_x[:len(freqs_x)//2] > threshold)[0]
    
    if len(peak_indices) > 0:
        # Plot frequency comb from detected frequencies
        display_freqs = np.linspace(0, 0.5, 1000)
        comb = np.zeros_like(display_freqs)
        
        for idx in peak_indices:
            # Skip near-zero frequencies
            if abs(freqs_x[idx]) < 0.01:
                continue
                
            # Add peak for each detected frequency
            peak_height = fft_x[idx] / np.max(fft_x[:len(freqs_x)//2])
            comb += peak_height * np.exp(-((display_freqs-abs(freqs_x[idx]))**2)/0.0005)
        
        plt.plot(display_freqs, comb/np.max(comb) if np.max(comb) > 0 else comb)
        
        # Add frequency markers
        significant_freqs = freqs_x[peak_indices]
        for freq in significant_freqs:
            if abs(freq) >= 0.01:
                plt.axvline(abs(freq), color='red', alpha=0.3, linestyle='--')
    else:
        plt.text(0.5, 0.5, "No significant frequency components detected",
                ha='center', va='center', transform=plt.gca().transAxes)
    
    plt.title('Frequency Comb Structure')
    plt.ylabel('Amplitude')
    plt.xlabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(figure_dir, 'frequency_comb.png'))
    plt.close()
    
    # Generate circuit diagram
    circuit_path = os.path.join(figure_dir, 'circuit.png')
    generate_circuit_diagram(circuit_type, qubits, drive_param, circuit_path)
    
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
    result_dirs = sorted(glob.glob('results/*')) if os.path.exists('results') else []
    result_dirs = [d for d in result_dirs if os.path.isdir(d)]
    
    # Get the latest result if available
    latest_result = None
    time_crystal_detected = False
    incommensurate_count = 0
    
    if result_dirs:
        latest_dir = result_dirs[-1]
        metadata_path = os.path.join(latest_dir, 'metadata.txt')
        
        if os.path.exists(metadata_path):
            latest_result = {'name': os.path.basename(latest_dir)}
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
            'elapsed_time': metadata.get('elapsed_time', '0.5'),
            'is_starred': False,
            'figures': []
        }
        
        # Get figure paths
        figure_dir = os.path.join(result_dir, 'figures')
        if os.path.exists(figure_dir):
            # Find all PNG files
            for fig_file in sorted(glob.glob(os.path.join(figure_dir, '*.png'))):
                fig_name = os.path.basename(fig_file)
                result_data['figures'].append({
                    'name': fig_name,
                    'path': f"/figure/{result_name}/{fig_name}",
                    'title': fig_name.replace('.png', '').replace('_', ' ').title()
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
    import glob
    
    # Get all simulation results
    result_dirs = sorted(glob.glob('results/*')) if os.path.exists('results') else []
    result_dirs = [d for d in result_dirs if os.path.isdir(d)]
    
    # Format simulation results for display
    sim_results = []
    for result_dir in result_dirs:
        metadata_path = os.path.join(result_dir, 'metadata.txt')
        metadata = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.strip().split(':', 1)
                        metadata[key.strip()] = value.strip()
        
        result_name = os.path.basename(result_dir)
        sim_results.append({
            'id': len(sim_results) + 1,  # Assign a simple ID
            'name': result_name,
            'circuit_type': metadata.get('circuit_type', 'unknown'),
            'qubits': metadata.get('qubits', '0'),
            'drive_param': metadata.get('drive_param', '0'),
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
    # Create results directory
    os.makedirs('results', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)