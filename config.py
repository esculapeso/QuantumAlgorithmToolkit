"""
Configuration module for quantum simulation package.
Contains global configuration parameters.
"""

import os

# --- Google Drive Mounting (for Colab) ---
SAVE_TO_GOOGLE_DRIVE = True  # Defaulting to True as requested
GDRIVE_MOUNT_POINT = '/content/gdrive'
GDRIVE_SAVE_FOLDER = 'My Drive/QuantumSimulations'  # Example path

# --- Global paths ---
FIGURES_BASE_PATH = 'figures'
RESULTS_BASE_PATH = 'results'
NUMERIC_DATA_BASE_PATH = 'numeric_data'

# Create directories if they don't exist
os.makedirs(FIGURES_BASE_PATH, exist_ok=True)
os.makedirs(RESULTS_BASE_PATH, exist_ok=True)
os.makedirs(NUMERIC_DATA_BASE_PATH, exist_ok=True)

# Default parameters for simulation
DEFAULT_SIMULATION_PARAMS = {
    "qubits": 3,
    "shots": 8192,
    "drive_steps": 5,
    "time_points": 100,
    "max_time": 10.0,
    "drive_param": 0.9,
    "init_state": "superposition"
}

# Default parameters for analysis
DEFAULT_PEAK_HEIGHT_THRESHOLD = 0.05
DEFAULT_MAX_RATIONAL_DENOMINATOR = 50
DEFAULT_RATIONAL_TOLERANCE = 1e-3
DEFAULT_HARMONIC_TOLERANCE = 0.10
DEFAULT_MIN_OMEGA_CAND_AMP = 0.1
DEFAULT_MIN_COMB_TEETH = 3
DEFAULT_FREQ_TOLERANCE_FACTOR = 0.05
DEFAULT_MAX_AMP_REL_STD_DEV = 0.5
DEFAULT_MAX_PHASE_STEP_STD_DEV = 0.5
