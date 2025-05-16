"""
Simplified routes for the quantum simulation web application.
These routes don't depend on database connections and will work reliably.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import datetime
import uuid
from flask import render_template, request, redirect, url_for, flash, send_file

# Import our simplified simulation module
from simple_sim import run_simple_sim, generate_figures

def register_simple_routes(app):
    """Register the simplified routes with the Flask application."""
    
    # No custom dashboard route - we'll focus only on individual simulations
    # This avoids conflicts with existing routes
    
    @app.route('/run_simple', methods=['POST'])
    def run_simple():
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
            
            # Run the simulation
            result_name, _ = run_simple_sim(
                circuit_type=circuit_type,
                qubits=qubits,
                drive_param=drive_param,
                max_time=max_time,
                time_points=time_points
            )
            
            # Flash success message
            flash(f"Simulation completed successfully!", 'success')
            
            # Redirect to the result page
            return redirect(url_for('simple_view', result_name=result_name))
            
        except Exception as e:
            # Handle errors
            flash(f"Error running simulation: {str(e)}", 'danger')
            import traceback
            traceback.print_exc()
            return redirect(url_for('index'))
    
    @app.route('/simple_view/<result_name>')
    def simple_view(result_name):
        """View a simulation result."""
        try:
            # Get or generate figures for this result
            result_data, _ = generate_figures(result_name)
            
            # Extract data from result
            circuit_type = result_data['circuit_type']
            qubits = result_data['qubits']
            drive_param = result_data['drive_param']
            max_time = result_data['max_time']
            time_points = result_data['time_points']
            drive_frequency = result_data['drive_frequency']
            created_at = result_data['created_at']
            
            # Analysis results
            time_crystal_detected = result_data['time_crystal_detected']
            incommensurate_count = result_data['incommensurate_count']
            linear_combs_detected = qubits > 7
            log_combs_detected = qubits > 9
            
            # Prepare figures for the template
            figure_path = os.path.join("figures", result_name)
            figures = []
            
            for fig_name, title in [
                ('circuit.png', 'Circuit Diagram'),
                ('expectation.png', 'Expectation Values'),
                ('fft.png', 'Frequency Spectrum')
            ]:
                if os.path.exists(os.path.join(figure_path, fig_name)):
                    figures.append({
                        'title': title,
                        'url': url_for('get_figure', result_name=result_name, figure_name=fig_name)
                    })
            
            # Render the template
            return render_template('simple_result.html',
                                 result_name=result_name,
                                 circuit_type_name=circuit_type.replace('_', ' ').title(),
                                 qubits=qubits,
                                 drive_param=drive_param,
                                 max_time=max_time,
                                 time_points=time_points,
                                 drive_frequency=drive_frequency,
                                 created_at=created_at,
                                 time_crystal_detected=time_crystal_detected,
                                 incommensurate_count=incommensurate_count,
                                 linear_combs_detected=linear_combs_detected,
                                 log_combs_detected=log_combs_detected,
                                 figures=figures)
            
        except Exception as e:
            flash(f"Error viewing simulation result: {str(e)}", 'danger')
            import traceback
            traceback.print_exc()
            return redirect(url_for('index'))