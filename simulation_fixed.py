"""
Main simulation module for quantum simulation package.
Contains functions for running quantum simulations and analyzing results.
"""

import os
import sys
import time
import datetime
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import itertools
import traceback

# Check if we're running in Google Colab
IN_COLAB = 'google.colab' in sys.modules

def run_parameter_scan(circuit_type, parameter_sets, init_state='superposition', 
                     sweep_session=None, scan_name='scan', save_results=True, 
                     show_plots=False, aer_method='statevector', verbose=True):
    """
    Run a parameter sweep over multiple parameter combinations.
    
    Args:
        circuit_type (str): The quantum circuit type to use
        parameter_sets (list): List of parameter dictionaries, each containing a set of parameters
        init_state (str): Initial quantum state ('superposition', 'up', 'down', etc.)
        sweep_session (str): Session identifier for the parameter sweep
        scan_name (str): Name for this parameter scan
        save_results (bool): Whether to save results to disk
        show_plots (bool): Whether to display plots during simulation
        aer_method (str): Backend method for Qiskit Aer ('statevector', 'density_matrix', etc.)
        verbose (bool): Whether to print detailed progress information
    
    Returns:
        list: Results from all parameter combinations
    """
    # Start timing
    start_time = time.time()
    
    # Create folder for scan results
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    scan_folder = f"{circuit_type}_{scan_name}_{timestamp}"
    
    if save_results:
        scan_path = os.path.join(config.RESULTS_BASE_PATH, scan_folder)
        os.makedirs(scan_path, exist_ok=True)
        
        # Set up Google Drive if enabled
        gdrive_save_path = setup_gdrive_if_needed()
        if gdrive_save_path:
            gdrive_scan_path = os.path.join(gdrive_save_path, scan_folder)
            os.makedirs(gdrive_scan_path, exist_ok=True)
    else:
        scan_path = None
        gdrive_save_path = None
    
    # Initialize results storage
    all_results = []
    summary_data = []
    
    # Loop through each parameter set
    for i, params in enumerate(parameter_sets):
        # Make a deep copy to avoid modifying the original
        current_params = params.copy()
        
        # Get the active parameters being swept
        active_params = []
        for key, value in current_params.items():
            if key not in ['circuit_type', 'init_state', 'param_set_name', 'save_results', 
                         'show_plots', 'aer_method', 'verbose']:
                active_params.append(key)
        
        if verbose:
            print(f"\nRunning parameter set {i+1}/{len(parameter_sets)}:")
            for key in active_params:
                if key in current_params:
                    print(f"  {key}: {current_params[key]}")
        
        # Create a name for this parameter set that only includes changed parameters
        param_values = []
        for key in active_params:
            if key in current_params:
                formatted_value = format_param(current_params[key], '.2f' if isinstance(current_params[key], float) else '')
                param_values.append(f"{key}={formatted_value}")
        param_set_name = '_'.join(param_values)
        
        # Run simulation with these parameters
        try:
            # Get which parameters are being swept for database tracking
            sweep_param_names = []
            sweep_param_values = []
            for key in active_params:
                sweep_param_names.append(key)
                sweep_param_values.append(current_params[key])
                
            # Set up sweep tracking parameters for first and second parameters
            sweep_param1 = sweep_param_names[0] if len(sweep_param_names) > 0 else None
            sweep_value1 = sweep_param_values[0] if len(sweep_param_values) > 0 else None
            sweep_param2 = sweep_param_names[1] if len(sweep_param_names) > 1 else None
            sweep_value2 = sweep_param_values[1] if len(sweep_param_values) > 1 else None
            
            # Merge the parameter set with default settings
            sim_params = {
                'circuit_type': circuit_type,
                'param_set_name': param_set_name,
                'save_results': save_results,
                'show_plots': show_plots,
                'aer_method': aer_method,
                'verbose': verbose,
                'sweep_session': sweep_session,
                'sweep_index': i,
                'sweep_param1': sweep_param1,
                'sweep_value1': sweep_value1,
                'sweep_param2': sweep_param2,
                'sweep_value2': sweep_value2
            }
            
            # Copy params but remove any param_ranges key to avoid errors
            filtered_params = {k: v for k, v in current_params.items() if k != 'param_ranges'}
            sim_params.update(filtered_params)
            
            # Actually run the simulation
            result = run_simulation(**sim_params)
            
            if 'error' in result:
                print(f"Error in parameter set {i+1}: {result['error']}")
                summary_row = {
                    'param_set': i+1,
                    'status': 'error',
                    'error_message': result['error']
                }
                summary_row.update(params)
                summary_data.append(summary_row)
                continue
            
            # Extract key results for summary
            summary_row = {
                'param_set': i+1,
                'status': 'success',
                'has_subharmonics': result['analysis'].get('has_subharmonics', False),
                'incommensurate_count': result['fc_analysis'].get('incommensurate_peak_count', 0),
                'mx_comb_found': result['comb_analysis'].get('mx_comb_found', False),
                'mx_comb_teeth': result['comb_analysis'].get('mx_num_teeth', 0),
                'mz_comb_found': result['comb_analysis'].get('mz_comb_found', False),
                'mz_comb_teeth': result['comb_analysis'].get('mz_num_teeth', 0),
                'mx_log_comb_found': result['log_comb_analysis'].get('mx_log_comb_found', False),
                'mz_log_comb_found': result['log_comb_analysis'].get('mz_log_comb_found', False),
                'elapsed_time': result['elapsed_time']
            }
            summary_row.update(params)
            summary_data.append(summary_row)
            
            # Save individual results
            result_path = None
            if save_results:
                result_folder = os.path.join(scan_path, f"param_set_{i+1}")
                os.makedirs(result_folder, exist_ok=True)
                
                # Save summary data for this parameter set
                result_summary_path = os.path.join(result_folder, "summary.json")
                with open(result_summary_path, 'w') as f:
                    json.dump(summary_row, f, indent=2, default=convert_numpy_type)
                
                result_path = result_folder
                
            # Add to results list
            all_results.append(result)
            
        except Exception as e:
            print(f"Error in simulation {i+1}: {e}")
            traceback.print_exc()
    
    # Save summary data for all parameter sets
    if save_results and summary_data:
        # Convert to DataFrame for easier CSV export
        import pandas as pd
        summary_df = pd.DataFrame(summary_data)
        
        try:
            summary_csv_path = os.path.join(scan_path, 'summary_results.csv')
            summary_df.to_csv(summary_csv_path, index=False)
            
            # Also save as Excel if pandas has Excel support
            try:
                summary_excel_path = os.path.join(scan_path, 'summary_results.xlsx')
                summary_df.to_excel(summary_excel_path, index=False, sheet_name='Scan Results')
            except:
                # Excel writing might fail if openpyxl is not installed - ignore
                pass
            
            if gdrive_save_path:
                try:
                    gdrive_csv_path = os.path.join(gdrive_save_path, scan_folder, 'summary_results.csv')
                    summary_df.to_csv(gdrive_csv_path, index=False)
                    
                    try:
                        gdrive_excel_path = os.path.join(gdrive_save_path, scan_folder, 'summary_results.xlsx')
                        summary_df.to_excel(gdrive_excel_path, index=False, sheet_name='Scan Results')
                    except:
                        pass
                except Exception as e:
                    print(f"Error saving summary to Google Drive: {e}")
                    
        except Exception as e:
            print(f"Error saving summary data: {e}")
            traceback.print_exc()
            
    # Calculate and print total elapsed time
    total_time = time.time() - start_time
    if verbose:
        print(f"\nParameter scan completed in {total_time:.2f} seconds")
        print(f"Processed {len(parameter_sets)} parameter sets")
        print(f"Results {'saved to ' + scan_path if save_results else 'not saved'}")
        
    return all_results

def generate_parameter_grid(**param_ranges):
    """
    Generate a grid of parameter combinations from ranges.
    
    Args:
        param_ranges: Keyword arguments where keys are parameter names and
                     values are lists of parameter values to scan.
    
    Returns:
        list: List of parameter dictionaries covering all combinations
    """
    param_names = list(param_ranges.keys())
    param_values = list(param_ranges.values())
    
    # Generate all combinations
    combinations = list(itertools.product(*param_values))
    
    # Convert to list of dictionaries
    param_sets = []
    for combo in combinations:
        param_dict = {name: value for name, value in zip(param_names, combo)}
        param_sets.append(param_dict)
        
    return param_sets

def generate_parameter_grid(param_ranges):
    """
    Generate a grid of parameter combinations based on specified ranges.
    
    Args:
        param_ranges (dict): Dictionary where keys are parameter names and values are
                           dictionaries with 'min', 'max', and 'steps' keys.
    
    Returns:
        list: List of parameter dictionaries, each containing a unique combination of parameters.
    """
    if param_ranges is None or not param_ranges:
        return []
        
    # For each parameter, generate a list of values
    param_values = {}
    for param_name, range_info in param_ranges.items():
        min_val = range_info['min']
        max_val = range_info['max']
        steps = range_info['steps']
        
        if min_val == max_val:
            # Single value parameter (not being swept)
            param_values[param_name] = [min_val]
        else:
            # Generate evenly spaced values
            if isinstance(min_val, int) and isinstance(max_val, int):
                # For integer parameters, use linspace and round to integers
                values = np.linspace(min_val, max_val, steps)
                param_values[param_name] = [int(round(v)) for v in values]
            else:
                # For float parameters, use linspace
                param_values[param_name] = list(np.linspace(min_val, max_val, steps))
    
    # Generate all combinations of parameter values
    param_names = list(param_values.keys())
    value_lists = [param_values[name] for name in param_names]
    
    # Generate grid of all parameter combinations
    grid = []
    for combo in itertools.product(*value_lists):
        param_dict = {}
        for i, name in enumerate(param_names):
            param_dict[name] = combo[i]
        grid.append(param_dict)
    
    return grid

import config
from utils import is_harmonic_related, format_param, create_folder_structure, setup_gdrive_if_needed, save_to_gdrive
from quantum_circuits import get_circuit_generator
from analysis import run_expectation_and_fft_analysis, analyze_fft_peaks_for_fc, analyze_frequency_comb, analyze_log_frequency_comb
from visualization import plot_expectation_values, plot_fft_analysis, plot_frequency_comb_analysis, plot_log_comb_analysis, plot_circuit_diagram

def run_simulation(circuit_type, qubits=3, shots=8192, drive_steps=5,
                  time_points=100, max_time=10.0, drive_param=0.9,
                  init_state='superposition', param_set_name='default',
                  sweep_session=None, sweep_index=None, sweep_param1=None, 
                  sweep_value1=None, sweep_param2=None, sweep_value2=None,
                  save_results=True, show_plots=False, aer_method='statevector',
                  plot_circuit=True, verbose=True, progress_callback=None, 
                  seed=None):
    # Function implementation would go here
    pass

def convert_numpy_type(value):
    """
    Convert numpy types to Python native types for database compatibility.
    
    Args:
        value: The value to convert
        
    Returns:
        The converted value as a Python native type
    """
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    return value
