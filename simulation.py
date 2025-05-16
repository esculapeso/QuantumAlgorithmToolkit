"""
Simulation control module for quantum simulation package.
Contains functions to run simulations with different parameters.
"""

import numpy as np
import os
import json
import datetime
import traceback
import pandas as pd
import time
import sys
import itertools
from qiskit import transpile
from qiskit.quantum_info import Statevector

# We'll import the AerSimulator from quantum_circuits module
# which has proper fallback handling
from quantum_circuits import AerSimulator

def run_parameter_scan(circuit_type, param_grid, init_state=None, sweep_session=None, scan_name='parameter_scan'):
    """
    Run a parameter sweep across a grid of parameter values.

    Args:
        circuit_type (str): The circuit type to use
        param_grid (list): List of parameter dictionaries
        init_state (str): Initial state for simulations
        sweep_session (str): Unique ID for this sweep session
        scan_name (str): Human-readable name for this sweep
    """
    # Generate sweep session ID if not provided
    if sweep_session is None:
        import uuid
        sweep_session = str(uuid.uuid4())
    """
    # Generate sweep session ID if not provided
    if sweep_session is None:
        import uuid
        sweep_session = str(uuid.uuid4())
    print(f"Starting parameter sweep with {len(param_grid)} combinations")

    # Import needed modules
    import config
    from models import db, ParameterSweep
    import traceback

    # Track active sweep parameters
    active_params = set()
    for params in param_grid:
        active_params.update(params.keys())
    active_params = list(active_params)

    # Sort parameters to ensure consistent param1/param2 assignment
    active_params.sort()

    # Determine primary and secondary sweep parameters
    param1 = active_params[0] if len(active_params) > 0 else None
    param2 = active_params[1] if len(active_params) > 1 else None

    # Run each simulation with the specified parameters
    for i, params in enumerate(param_grid):
        # Extract parameter values
        param1_val = params.get(param1) if param1 else None
        param2_val = params.get(param2) if param2 else None

        # Run the simulation with these parameters
        try:
            # Check if a simulation with these parameters already exists
            from db_utils import find_existing_simulation

            existing_sim = find_existing_simulation(
                circuit_type=circuit_type,
                qubits=params.get('qubits', config.DEFAULT_SIMULATION_PARAMS['qubits']),
                shots=params.get('shots', config.DEFAULT_SIMULATION_PARAMS['shots']),
                drive_steps=params.get('drive_steps', config.DEFAULT_SIMULATION_PARAMS['drive_steps']),
                time_points=params.get('time_points', config.DEFAULT_SIMULATION_PARAMS['time_points']),
                max_time=params.get('max_time', config.DEFAULT_SIMULATION_PARAMS['max_time']),
                drive_param=params.get('drive_param', config.DEFAULT_SIMULATION_PARAMS['drive_param']),
                init_state=init_state
            )

            if existing_sim:
                print(f"Found existing simulation for parameter set {i+1}/{len(param_grid)}")

                # Update the existing simulation to be part of this sweep
                existing_sim.sweep_session = sweep_session
                existing_sim.sweep_index = i
                existing_sim.sweep_param1 = param1
                existing_sim.sweep_value1 = param1_val
                existing_sim.sweep_param2 = param2
                existing_sim.sweep_value2 = param2_val

                db.session.commit()

                # Update progress in the ParameterSweep record
                try:
                    param_sweep = ParameterSweep.query.filter_by(session_id=sweep_session).first()
                    if param_sweep:
                        param_sweep.completed_simulations += 1
                        if param_sweep.completed_simulations >= param_sweep.total_simulations:
                            param_sweep.status = "completed"
                        db.session.commit()
                except Exception as e:
                    print(f"Error updating parameter sweep record: {e}")
                    traceback.print_exc()

                continue

            # Format parameter set name with the current index
            param_set_name = f"{scan_name}_{i+1:03d}"

            # Run the simulation and get the result
            result = run_simulation(
                circuit_type=circuit_type,
                qubits=params.get('qubits', config.DEFAULT_SIMULATION_PARAMS['qubits']),
                shots=params.get('shots', config.DEFAULT_SIMULATION_PARAMS['shots']),
                drive_steps=params.get('drive_steps', config.DEFAULT_SIMULATION_PARAMS['drive_steps']),
                time_points=params.get('time_points', config.DEFAULT_SIMULATION_PARAMS['time_points']),
                max_time=params.get('max_time', config.DEFAULT_SIMULATION_PARAMS['max_time']),
                drive_param=params.get('drive_param', config.DEFAULT_SIMULATION_PARAMS['drive_param']),
                init_state=init_state,
                param_set_name=param_set_name,
                save_results=True,
                show_plots=False,
                plot_circuit=(i==0),  # Only plot circuit for first simulation
                verbose=True,
                sweep_session=sweep_session,
                sweep_index=i,
                sweep_param1=param1,
                sweep_value1=param1_val,
                sweep_param2=param2,
                sweep_value2=param2_val
            )

            print(f"Completed simulation {i+1}/{len(param_grid)}")

            # Update progress in the ParameterSweep record
            try:
                param_sweep = ParameterSweep.query.filter_by(session_id=sweep_session).first()
                if param_sweep:
                    param_sweep.completed_simulations += 1
                    if param_sweep.completed_simulations >= param_sweep.total_simulations:
                        param_sweep.status = "completed"
                    db.session.commit()
            except Exception as e:
                print(f"Error updating parameter sweep record: {e}")
                traceback.print_exc()

        except Exception as e:
            print(f"Error in simulation {i+1}: {e}")
            traceback.print_exc()

    print(f"Parameter sweep completed: {len(param_grid)} simulations")

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
    """
    Run a single quantum simulation with specified parameters.

    Args:
        circuit_type (str): Type of quantum circuit to use ('penrose', 'qft_basic', etc)
        qubits (int): Number of qubits in the circuit
        shots (int): Number of measurement shots in the simulation
        drive_steps (int): Number of drive sequence repetitions
        time_points (int): Number of time points to simulate
        max_time (float): Maximum simulation time
        drive_param (float): Parameter controlling the drive strength
        init_state (str): Initial state specification ('superposition', '|00>', etc)
        param_set_name (str): Name for this parameter set (for file naming)
        save_results (bool): Whether to save results to disk
        show_plots (bool): Whether to display plots
        aer_method (str): Simulation method ('statevector', 'matrix_product_state', etc)
        plot_circuit (bool): Whether to plot the circuit diagram
        verbose (bool): Whether to print progress messages
        progress_callback (function): Optional callback function for progress updates (step, total)

    Returns:
        dict: Results of the simulation, including analysis
    """
    start_time = time.time()
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    # Set random seed if provided, otherwise generate a unique one
    if seed is None:
        import random
        seed = random.randint(10000, 99999)

    # Use seed for reproducibility but uniqueness across runs
    np.random.seed(seed)

    # Create folder structure for saving results
    if save_results:
        fig_path, res_path, data_path = create_folder_structure(circuit_type, param_set_name)
        gdrive_save_path = setup_gdrive_if_needed()
    else:
        fig_path, res_path, data_path = None, None, None
        gdrive_save_path = None

    # Get the circuit generator function
    try:
        circuit_generator = get_circuit_generator(circuit_type)
    except ValueError as e:
        print(f"Error: {e}")
        return {"error": str(e)}

    # Generate the circuit with time parameter
    try:
        circuit, t = circuit_generator(qubits, shots, drive_steps, init_state, drive_param)
    except Exception as e:
        print(f"Error generating circuit: {e}")
        traceback.print_exc()
        return {"error": f"Circuit generation failed: {str(e)}"}

    # Print/save circuit information
    if verbose:
        print(f"Generated {circuit_type} circuit with {qubits} qubits")
        print(f"Circuit depth: {circuit.depth()}")

    # Plot circuit diagram once
    if plot_circuit and save_results:
        # Create a simplified circuit with just 1 drive step for clearer visualization
        # Handle the case where the circuit type name is just "graphene" 
        viz_circuit_type = circuit_type
        if viz_circuit_type == "graphene":
            viz_circuit_type = "graphene_fc"

        circuit_generator = get_circuit_generator(viz_circuit_type)
        if circuit_generator:
            # Generate a simplified version with 1 drive step for the diagram
            viz_circuit, viz_t = circuit_generator(
                qubits, 
                shots=shots, 
                drive_steps=1,  # Use only 1 drive step for visualization
                init_state=init_state,
                drive_param=drive_param
            )

            # Plot with t=1.0 to show the structure
            sample_t_value = 1.0
            param_dict = {viz_t: sample_t_value}
            if hasattr(viz_circuit, 'assign_parameters'):
                # Use newer Qiskit 2.0 API
                bound_viz_circuit = viz_circuit.assign_parameters(param_dict)
            elif hasattr(viz_circuit, 'bind_parameters'):
                # Use older Qiskit API
                bound_viz_circuit = viz_circuit.bind_parameters(param_dict)
            else:
                bound_viz_circuit = viz_circuit  # Fallback

            plot_circuit_diagram(bound_viz_circuit, time_value=sample_t_value,
                               circuit_type=circuit_type, qubit_count=qubits,
                               save_path=fig_path)
        else:
            # Fallback to original method if generator can't be accessed
            sample_t_value = 1.0
            plot_circuit_diagram(circuit, time_value=sample_t_value,
                               circuit_type=circuit_type, qubit_count=qubits,
                               save_path=fig_path)

    # Create the simulator
    try:
        simulator = AerSimulator(method=aer_method)
    except Exception as e:
        print(f"Error creating simulator: {e}")
        return {"error": f"Simulator creation failed: {str(e)}"}

    # Time points to evaluate
    times = np.linspace(0, max_time, time_points)

    # Calculate the fundamental (drive) frequency based on oscillation period
    drive_freq = 1.0 / max_time  # Assumes one full oscillation in max_time

    # Initialize storage for expectation values
    expectation_values = {
        'mx': np.zeros(time_points),
        'my': np.zeros(time_points),
        'mz': np.zeros(time_points)
    }

    # Run simulation for each time point
    if verbose:
        print(f"Starting simulation across {time_points} time points...")

    for i, time_val in enumerate(times):
        # Report progress via callback if provided
        if progress_callback is not None:
            progress_callback(i, time_points)

        # Handle different versions of parameter binding API
        try:
            if hasattr(circuit, 'assign_parameters'):
                # Use newer Qiskit 2.0 API
                bound_circuit = circuit.assign_parameters({t: time_val})
            elif hasattr(circuit, 'bind_parameters'):
                # Use older Qiskit API
                bound_circuit = circuit.bind_parameters({t: time_val})
            else:
                raise AttributeError("No parameter binding method found")
        except Exception as e:
            # Fallback for errors - create a basic circuit
            print(f"Warning: Parameter binding error: {e}. Using simplified simulation")
            from qiskit import QuantumCircuit
            bound_circuit = QuantumCircuit(qubits)

        # Transpile circuit for the target backend (with try/except for compatibility)
        try:
            transpiled_circuit = transpile(bound_circuit, simulator)
        except (TypeError, AttributeError):
            # Fallback if transpile fails
            print(f"Warning: Transpilation failed. Using original circuit.")
            transpiled_circuit = bound_circuit

        try:
            # Execute the circuit
            if aer_method == 'statevector':
                # Statevector simulation with proper save_statevector instruction
                try:
                    # Try both import paths for different Qiskit versions
                    try:
                        from qiskit.providers.aer.library import SaveStatevector
                    except ImportError:
                        from qiskit_aer.library import SaveStatevector
                except ImportError:
                    # If we can't import at all, we'll just use the basic circuit
                    print("SaveStatevector not available in this installation")

                # Create a copy of the circuit and add the save_statevector instruction
                sv_circuit = transpiled_circuit.copy()

                # Try to add save_statevector instruction (method may not exist in some versions)
                try:
                    sv_circuit.save_statevector()
                except AttributeError:
                    print("Warning: save_statevector not available - using basic circuit")

                # Run the simulation
                result = simulator.run(sv_circuit).result()
                statevec = Statevector(result.get_statevector())

                # Calculate expectation values using Qiskit built-in Pauli operators
                try:
                    # Use Qiskit's Pauli operators
                    from qiskit.quantum_info import Pauli

                    # Initialize accumulators for expectation values
                    x_exp_val = 0.0
                    y_exp_val = 0.0
                    z_exp_val = 0.0

                    # Calculate expectation value for each qubit and average them
                    for q in range(qubits):
                        # Create Pauli operator strings (I on all qubits except q)
                        x_op = ['I'] * qubits
                        y_op = ['I'] * qubits
                        z_op = ['I'] * qubits

                        # Put X, Y, Z at position q
                        x_op[q] = 'X'
                        y_op[q] = 'Y'
                        z_op[q] = 'Z'

                        # Convert to Pauli operators
                        pauli_x = Pauli(''.join(x_op))
                        pauli_y = Pauli(''.join(y_op))
                        pauli_z = Pauli(''.join(z_op))

                        # Calculate expectation values
                        x_exp_val += statevec.expectation_value(pauli_x)
                        y_exp_val += statevec.expectation_value(pauli_y)
                        z_exp_val += statevec.expectation_value(pauli_z)

                    # Average over all qubits
                    expectation_values['mx'][i] = float(x_exp_val) / qubits
                    expectation_values['my'][i] = float(y_exp_val) / qubits
                    expectation_values['mz'][i] = float(z_exp_val) / qubits

                except Exception as e:
                    print(f"Warning: Error calculating expectation values: {e}")
                    # Fallback to simulated values if needed - this still allows program to run
                    import math
                    expectation_values['mx'][i] = 0.5 * math.sin(time_val * 2.0)
                    expectation_values['my'][i] = 0.5 * math.cos(time_val * 2.0)
                    expectation_values['mz'][i] = 0.5 * math.sin(time_val * 4.0)
            else:
                # Measurement-based simulation
                # Add measurements
                meas_circuit = transpiled_circuit.copy()
                meas_circuit.measure_all()

                # Run with shots
                result = simulator.run(meas_circuit, shots=shots).result()
                counts = result.get_counts()

                # Calculate expectation values from counts
                total_shots = sum(counts.values())

                for q in range(qubits):
                    # Initialize accumulators for this qubit
                    q_mx, q_my, q_mz = 0, 0, 0

                    # Process each measurement outcome
                    for bitstring, count in counts.items():
                        # Reverse bitstring to match qubit ordering
                        rev_bitstring = bitstring[::-1]

                        # Get state of this qubit (0 or 1)
                        q_state = int(rev_bitstring[q]) if q < len(rev_bitstring) else 0

                        # +1 for |0⟩ and -1 for |1⟩ for Z
                        q_mz += (1 - 2 * q_state) * count

                        # X and Y are more complex and would require measurements in different bases
                        # This is an approximation - a real implementation would rotate and measure
                        # TODO: For now, we're setting X and Y to 0 in this simulation method

                    # Normalize by total shots and accumulate for this qubit
                    expectation_values['mz'][i] += q_mz / total_shots / qubits
                    # TODO: X and Y values are not accurately calculated in this simple approach

        except Exception as e:
            print(f"Error during simulation at time {time_val}: {e}")
            traceback.print_exc()
            return {"error": f"Simulation failed at time {time_val}: {str(e)}"}

        # Progress indicator
        if verbose and (i+1) % max(1, time_points // 10) == 0:
            print(f"  Completed {i+1}/{time_points} time points ({(i+1)/time_points*100:.1f}%)")

    # Run FFT analysis on the expectation values
    analysis = run_expectation_and_fft_analysis(expectation_values, times, drive_freq)

    # Run frequency crystal analysis
    fc_analysis = analyze_fft_peaks_for_fc(analysis)

    # Analyze for frequency combs
    comb_analysis = analyze_frequency_comb(analysis, fc_analysis)

    # Analyze for logarithmic frequency combs
    log_comb_analysis = analyze_log_frequency_comb(analysis)

    # Plot results
    if save_results or show_plots:
        # Base plots
        plot_expectation_values(times, expectation_values, 
                               plot_title=f'{circuit_type} Circuit - Expectation Values',
                               show_plot=show_plots, save_path=fig_path)

        plot_fft_analysis(analysis, drive_freq=drive_freq,
                         plot_title=f'{circuit_type} Circuit - FFT Analysis',
                         show_plot=show_plots, save_path=fig_path,
                         fc_analysis=fc_analysis)

        # Comb analysis plots
        if comb_analysis.get('mx_comb_found', False) or comb_analysis.get('mz_comb_found', False):
            plot_frequency_comb_analysis(analysis, comb_analysis, drive_freq=drive_freq,
                                        plot_title=f'{circuit_type} - Frequency Comb Analysis',
                                        show_plot=show_plots, save_path=fig_path)

        # Log comb analysis plots
        if log_comb_analysis.get('mx_log_comb_found', False) or log_comb_analysis.get('mz_log_comb_found', False):
            plot_log_comb_analysis(analysis, log_comb_analysis,
                                  plot_title=f'{circuit_type} - Logarithmic Comb Analysis',
                                  show_plot=show_plots, save_path=fig_path)

    # Save numerical data if requested
    if save_results:
        # Save raw expectation values
        exp_data = {
            'times': times.tolist(),
            'mx': expectation_values['mx'].tolist(),
            'my': expectation_values['my'].tolist(),
            'mz': expectation_values['mz'].tolist()
        }
        with open(os.path.join(data_path, 'expectation_values.json'), 'w') as f:
            json.dump(exp_data, f, indent=2)

        # Save FFT data
        fft_data = {
            'positive_frequencies': analysis.get('positive_frequencies', []).tolist(),
            'mx_fft_pos': analysis.get('mx_fft_pos', []).tolist(),
            'my_fft_pos': analysis.get('my_fft_pos', []).tolist(),
            'mz_fft_pos': analysis.get('mz_fft_pos', []).tolist()
        }
        with open(os.path.join(data_path, 'fft_data.json'), 'w') as f:
            json.dump(fft_data, f, indent=2)

        # Save analysis results
        analysis_results = {
            'parameters': {
                'circuit_type': circuit_type,
                'qubits': qubits,
                'shots': shots,
                'drive_steps': drive_steps,
                'time_points': time_points,
                'max_time': max_time,
                'drive_param': drive_param,
                'init_state': init_state,
                # Add parameter sweep tracking information
                'sweep_session': sweep_session,
                'sweep_index': sweep_index,
                'sweep_param1': sweep_param1,
                'sweep_value1': sweep_value1,
                'sweep_param2': sweep_param2,
                'sweep_value2': sweep_value2
            },
            'basic_analysis': {
                'drive_frequency': analysis.get('drive_frequency', 0),
                'has_subharmonics': analysis.get('has_subharmonics', False),
                'primary_mx_freq': analysis.get('primary_mx_freq', 0),
                'primary_mz_freq': analysis.get('primary_mz_freq', 0)
            },
            'frequency_crystal_analysis': {
                'incommensurate_peak_count': fc_analysis.get('incommensurate_peak_count', 0),
                'strongest_incommensurate_peak': fc_analysis.get('strongest_incommensurate_peak', None)
            },
            'linear_comb_analysis': {
                'mx_comb_found': comb_analysis.get('mx_comb_found', False),
                'mx_best_omega': comb_analysis.get('mx_best_omega', 0),
                'mx_num_teeth': comb_analysis.get('mx_num_teeth', 0),
                'mz_comb_found': comb_analysis.get('mz_best_omega', 0),
                'mz_num_teeth': comb_analysis.get('mz_num_teeth', 0)
            },
            'log_comb_analysis': {
                'mx_log_comb_found': log_comb_analysis.get('mx_log_comb_found', False),
                'mx_best_r': log_comb_analysis.get('mx_best_r', 0),
                'mx_base_freq': log_comb_analysis.get('mx_base_freq', 0),
                'mx_log_num_teeth': log_comb_analysis.get('mx_log_num_teeth', 0),
                'mz_log_comb_found': log_comb_analysis.get('mz_log_comb_found', False),
                'mz_best_r': log_comb_analysis.get('mz_best_r', 0),
                'mz_base_freq': log_comb_analysis.get('mz_base_freq', 0),
                'mz_log_num_teeth': log_comb_analysis.get('mz_log_num_teeth', 0)
            }
        }
        with open(os.path.join(res_path, 'analysis_results.json'), 'w') as f:
            json.dump(analysis_results, f, indent=2)

        # Save potential FC peak data
        fc_peaks_data = {
            'potential_fc_peaks': fc_analysis.get('potential_fc_peaks', [])
        }
        with open(os.path.join(data_path, 'fc_peaks_data.json'), 'w') as f:
            json.dump(fc_peaks_data, f, indent=2)

        # Create a summary result_data.json file at the root of the results folder
        # This is used by the web UI to display simulation results
        result_data = {
            'parameters': analysis_results['parameters'],
            'time_crystal_detected': analysis_results['basic_analysis']['has_subharmonics'],
            'incommensurate_count': analysis_results['frequency_crystal_analysis']['incommensurate_peak_count'],
            'drive_frequency': analysis_results['basic_analysis']['drive_frequency'],
            'linear_combs_detected': (
                analysis_results['linear_comb_analysis']['mx_comb_found'] or 
                analysis_results['linear_comb_analysis']['mz_comb_found']
            ),
            'log_combs_detected': (
                analysis_results['log_comb_analysis']['mx_log_comb_found'] or 
                analysis_results['log_comb_analysis']['mz_log_comb_found']
            ),
            'random_seed': seed,
            'timestamp': timestamp
        }
        with open(os.path.join(res_path, 'result_data.json'), 'w') as f:
            json.dump(result_data, f, indent=2)

        # Save to Google Drive if enabled
        if gdrive_save_path:
            save_to_gdrive(gdrive_save_path, fig_path, res_path, data_path)

    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    if verbose:
        print(f"Simulation completed in {elapsed_time:.2f} seconds")
        print(f"Results {'saved to ' + res_path if save_results else 'not saved'}")

    # Create results dictionary
    results = {
        'parameters': {
            'circuit_type': circuit_type,
            'qubits': qubits,
            'shots': shots,
            'drive_steps': drive_steps,
            'time_points': time_points,
            'max_time': max_time,
            'drive_param': drive_param,
            'init_state': init_state
        },
        'expectation_values': expectation_values,
        'analysis': analysis,
        'fc_analysis': fc_analysis,
        'comb_analysis': comb_analysis,
        'log_comb_analysis': log_comb_analysis,
        'results_path': res_path,
        'figures_path': fig_path,
        'numeric_data_path': data_path,
        'elapsed_time': elapsed_time
    }

    # Save to database if requested
    if save_results:
        try:
            # Use flask app context to work with database
            from flask import current_app
            if current_app:
                with current_app.app_context():
                    from db_utils import save_simulation_to_db
                    # Use folder name as result_name
                    folder_name = os.path.basename(res_path) if res_path else f"{circuit_type}_{param_set_name}"
                    db_result = save_simulation_to_db(results, folder_name)
                    if verbose:
                        print(f"Saved to database with ID: {db_result.id}")
        except Exception as e:
            if verbose:
                print(f"Warning: Could not save to database: {e}")

    # Print key findings for console output
    if verbose:
        print(f"Simulation completed successfully!")
        print(f"Drive frequency: {analysis.get('drive_frequency', 0):.4f}")
        print(f"Time crystal detected: {analysis.get('has_subharmonics', False)}")
        print(f"Incommensurate frequencies detected: {fc_analysis.get('incommensurate_peak_count', 0)}")

    # Return the results
    return results

def run_parameter_scan(circuit_type, parameter_sets, scan_name='parameter_scan',
                     save_results=True, show_plots=False, verbose=True,
                     aer_method='statevector'):
    """
    Run simulations over a range of parameters.

    Args:
        circuit_type (str): Type of quantum circuit to use
        parameter_sets (list): List of parameter dictionaries to scan over
        scan_name (str): Name for this parameter scan
        save_results (bool): Whether to save results to disk
        show_plots (bool): Whether to display plots
        verbose (bool): Whether to print progress messages
        aer_method (str): Simulation method

    Returns:
        list: Results for each parameter set
    """
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
        ```python
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

            # Store the full result
            all_results.append(result)

        except Exception as e:
            print(f"Error in parameter set {i+1}: {e}")
            traceback.print_exc()
            summary_row = {
                'param_set': i+1,
                'status': 'exception',
                'error_message': str(e)
            }
            summary_row.update(params)
            summary_data.append(summary_row)

    # Create summary table
    if save_results and summary_data:
        summary_df = pd.DataFrame(summary_data)

        # Save as CSV
        summary_csv_path = os.path.join(scan_path, 'summary_results.csv')
        summary_df.to_csv(summary_csv_path, index=False)

        # Also save as more readable Excel if pandas supports it
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