"""
Utility functions for quantum simulation package.
Contains helper functions used across the codebase.
"""

import os
import json
import datetime
import traceback
from fractions import Fraction
import random
import sys
import config

def ensure_dependencies():
    """Check and install required dependencies."""
    try:
        import qiskit
        # Try to import qiskit_aer, but fall back to alternative import if needed
        try:
            import qiskit_aer
        except ImportError:
            try:
                from qiskit.providers import aer
                print("Using qiskit.providers.aer instead of qiskit_aer")
            except ImportError:
                print("WARNING: Neither qiskit_aer nor qiskit.providers.aer could be imported")
        
        import matplotlib
        import scipy
        import numpy as np
        from scipy import signal
        # Try to import simps, but use a fallback if not available
        try:
            from scipy.integrate import simps  # Using Simpson's rule for potential integration
        except ImportError:
            # Define a simple version of Simpson's rule integration as fallback
            def simps(y, x=None, dx=1.0):
                """Simple fallback implementation of Simpson's rule integration"""
                if x is None:
                    return np.sum(y) * dx
                else:
                    return np.trapz(y, x)  # Fall back to trapezoid rule
        import pandas
        
        # PyWavelets is optional - we'll try to import it but won't fail if it's not available
        try:
            import pywt
            print("PyWavelets (pywt) is available.")
        except ImportError:
            print("WARNING: PyWavelets (pywt) is not available. Some wavelet analysis features may be limited.")
        
        print("Required packages seem to be installed.")
        return True
    except ImportError as e:
        print(f"ERROR: Missing required packages: {e}")
        print("Please install the following packages: qiskit, matplotlib, scipy, numpy, pandas")
        return False

def is_harmonic_related(freq, drive_freq, tolerance=0.15, max_n=10, max_m=5):
    """Checks relationship between freq and drive_freq."""
    if freq <= 1e-9 or drive_freq <= 1e-9: return False, "N/A (zero freq)"
    if abs(freq / drive_freq - 1.0) < tolerance: return True, "drive"
    for n in range(2, max_n + 1):  # Subharmonics
        expected = drive_freq / n
        if abs(freq / expected - 1.0) < tolerance: return True, f"drive/{n}"
    for n in range(2, max_n + 1):  # Harmonics
        expected = drive_freq * n
        if abs(freq / expected - 1.0) < tolerance: return True, f"drive*{n}"
    for n in range(2, max_n + 1):  # Fractional
        for m in range(1, max_m + 1):
            if n == m: continue
            expected = drive_freq * m / n
            if abs(freq / expected - 1.0) < tolerance: return True, f"drive*{m}/{n}"
    return False, "non-harmonic"

def format_param(value, fmt_spec):
    """Safely formats numeric values, passes others as strings."""
    if isinstance(value, (int, float)):
        try: return f"{value:{fmt_spec}}"
        except ValueError: return str(value)
    else: return str(value)

def create_folder_structure(circuit_type, param_set_name):
    """
    Create and return paths for this analysis run.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder_name = f"{circuit_type}_{param_set_name}_{timestamp}"
    
    fig_path = os.path.join(config.FIGURES_BASE_PATH, folder_name)
    res_path = os.path.join(config.RESULTS_BASE_PATH, folder_name)
    data_path = os.path.join(config.NUMERIC_DATA_BASE_PATH, folder_name)
    
    os.makedirs(fig_path, exist_ok=True)
    os.makedirs(res_path, exist_ok=True)
    os.makedirs(data_path, exist_ok=True)
    
    return fig_path, res_path, data_path

def setup_gdrive_if_needed():
    """Setup Google Drive if enabled."""
    if not config.SAVE_TO_GOOGLE_DRIVE:
        return None
    
    try:
        from google.colab import drive
        drive.mount(config.GDRIVE_MOUNT_POINT)
        gdrive_save_path = os.path.join(config.GDRIVE_MOUNT_POINT, config.GDRIVE_SAVE_FOLDER)
        os.makedirs(gdrive_save_path, exist_ok=True)
        return gdrive_save_path
    except (ImportError, ModuleNotFoundError):
        print("Google Colab drive module not available. Saving to Google Drive disabled.")
        return None
    except Exception as e:
        print(f"Error mounting Google Drive: {e}")
        return None

def save_to_gdrive(gdrive_save_path, local_fig_path, local_res_path, local_data_path):
    """Copy results to Google Drive if enabled."""
    if not gdrive_save_path:
        return
    
    import shutil
    try:
        # Create target directories
        gdrive_fig_path = os.path.join(gdrive_save_path, os.path.basename(local_fig_path))
        gdrive_res_path = os.path.join(gdrive_save_path, os.path.basename(local_res_path))
        gdrive_data_path = os.path.join(gdrive_save_path, os.path.basename(local_data_path))
        
        os.makedirs(gdrive_fig_path, exist_ok=True)
        os.makedirs(gdrive_res_path, exist_ok=True)
        os.makedirs(gdrive_data_path, exist_ok=True)
        
        # Copy files
        for file in os.listdir(local_fig_path):
            shutil.copy2(os.path.join(local_fig_path, file), gdrive_fig_path)
        
        for file in os.listdir(local_res_path):
            shutil.copy2(os.path.join(local_res_path, file), gdrive_res_path)
            
        for file in os.listdir(local_data_path):
            shutil.copy2(os.path.join(local_data_path, file), gdrive_data_path)
            
        print(f"Successfully copied results to Google Drive: {gdrive_save_path}")
    except Exception as e:
        print(f"Error copying to Google Drive: {e}")
        traceback.print_exc()
