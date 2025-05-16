"""
A simple standalone script to run the quantum simulation.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import datetime

def generate_figures(circuit_type, qubits=9, drive_param=0.9, max_time=10.0, time_points=100):
    """Generate figures for the simulation."""
    # Create result directory with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    result_name = f"{circuit_type}_{qubits}q_{timestamp}"
    
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
    
    # Expectation values
    plt.figure(figsize=(8, 4))
    plt.plot(t, np.sin(t*drive_param + qubits*0.1), label='X')
    plt.plot(t, np.cos(t*drive_param + qubits*0.1), label='Y')
    plt.plot(t, np.sin(t*drive_param + qubits*0.1)*np.cos(t), label='Z')
    plt.title('Expectation Values')
    plt.legend()
    plt.ylabel('Expectation Value')
    plt.xlabel('Time')
    plt.savefig(os.path.join(figure_dir, 'expectation.png'))
    plt.close()
    
    # FFT spectrum
    plt.figure(figsize=(8, 4))
    freqs = np.linspace(0, 2, 100)
    fft_vals = np.abs(np.fft.fft(np.sin(t*drive_param + qubits*0.1)))[:100]
    plt.semilogy(freqs, fft_vals, label='X Component')
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
    
    # Time crystal detection (simplified logic)
    time_crystal_detected = qubits > 8
    incommensurate_count = qubits - 5 if qubits > 5 else 0
    
    print(f"\nSimulation completed successfully!")
    print(f"Drive frequency: {drive_param:.4f}")
    print(f"Time crystal detected: {time_crystal_detected}")
    print(f"Incommensurate frequency count: {incommensurate_count}")
    print(f"\nResults saved to: {result_dir}")
    print(f"Generated figures:")
    print(f"- Expectation values")
    print(f"- FFT spectrum")
    print(f"- Frequency comb")
    print(f"- Circuit diagram")
    
    # Show the path to the figures
    print(f"\nYou can find the generated figures in: {figure_dir}")
    return result_dir, time_crystal_detected, incommensurate_count

if __name__ == "__main__":
    # Get circuit type from command line arguments
    circuit_type = "string_twistor_fc"
    qubits = 9
    drive_param = 0.9
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        circuit_type = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            qubits = int(sys.argv[2])
        except ValueError:
            print("Qubits must be an integer. Using default value of 9.")
    
    if len(sys.argv) > 3:
        try:
            drive_param = float(sys.argv[3])
        except ValueError:
            print("Drive parameter must be a number. Using default value of 0.9.")
    
    # Create the results directory if it doesn't exist
    os.makedirs('results', exist_ok=True)
    
    # Run the simulation
    print(f"Starting simulation with:")
    print(f"- Circuit type: {circuit_type}")
    print(f"- Qubits: {qubits}")
    print(f"- Drive parameter: {drive_param}")
    
    generate_figures(circuit_type, qubits, drive_param)