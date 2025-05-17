"""
Direct fix for parameter sweep database tracking.
This script directly adds parameter sweep records for any missing sweep sessions.
"""
import os
import sys
import datetime
import traceback
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def direct_sweep_fix():
    """Directly fix parameter sweep database tracking."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        try:
            print("Performing direct parameter sweep fix...")
            
            # Find all simulations that have sweep_session set but no corresponding sweep record
            sweep_sessions = db.session.query(
                SimulationResult.sweep_session,
                SimulationResult.circuit_type,
                db.func.min(SimulationResult.created_at).label('created_at'),
                db.func.count(SimulationResult.id).label('count')
            ).filter(
                SimulationResult.sweep_session.isnot(None)
            ).group_by(
                SimulationResult.sweep_session,
                SimulationResult.circuit_type
            ).all()
            
            print(f"Found {len(sweep_sessions)} total sweep sessions")
            
            # Check each sweep session to ensure it has a database record
            for sweep in sweep_sessions:
                # Check if this sweep session already exists in parameter_sweeps
                existing_sweep = ParameterSweep.query.filter_by(session_id=sweep.sweep_session).first()
                
                if existing_sweep:
                    # Update the completed_simulations count
                    actual_count = SimulationResult.query.filter_by(sweep_session=sweep.sweep_session).count()
                    if existing_sweep.completed_simulations != actual_count:
                        print(f"Updating sweep {sweep.sweep_session}: {existing_sweep.completed_simulations} → {actual_count}")
                        existing_sweep.completed_simulations = actual_count
                        existing_sweep.total_simulations = max(existing_sweep.total_simulations, actual_count)
                        db.session.commit()
                else:
                    # Get parameter information from the simulations
                    simulations = SimulationResult.query.filter_by(sweep_session=sweep.sweep_session).all()
                    
                    # Find swept parameters
                    qubits = set(sim.qubits for sim in simulations)
                    drive_params = set(sim.drive_param for sim in simulations)
                    time_points = set(sim.time_points for sim in simulations)
                    
                    # Determine which parameters were swept
                    param1 = None
                    param2 = None
                    
                    if len(qubits) > 1:
                        param1 = 'qubits'
                    if len(drive_params) > 1:
                        if param1:
                            param2 = 'drive_param'
                        else:
                            param1 = 'drive_param'
                    if len(time_points) > 1 and not param2:
                        if param1:
                            param2 = 'time_points'
                        else:
                            param1 = 'time_points'
                    
                    # If we still don't have params, use the ones from the first simulation
                    if not param1 and simulations:
                        param1 = simulations[0].sweep_param1
                        param2 = simulations[0].sweep_param2
                    
                    # Create new parameter sweep record
                    new_sweep = ParameterSweep()
                    new_sweep.session_id = sweep.sweep_session
                    new_sweep.circuit_type = sweep.circuit_type
                    new_sweep.param1 = param1
                    new_sweep.param2 = param2
                    new_sweep.total_simulations = sweep.count
                    new_sweep.completed_simulations = sweep.count
                    new_sweep.created_at = sweep.created_at or datetime.datetime.now()
                    
                    db.session.add(new_sweep)
                    db.session.commit()
                    
                    print(f"Created new sweep record: {sweep.sweep_session} with {sweep.count} simulations")
            
            # Now run a SQL update to ensure all sweep indexes are sequential
            sweep_sessions = ParameterSweep.query.all()
            for sweep_record in sweep_sessions:
                simulations = SimulationResult.query.filter_by(
                    sweep_session=sweep_record.session_id
                ).order_by(
                    SimulationResult.result_name
                ).all()
                
                for i, sim in enumerate(simulations):
                    if sim.sweep_index != i + 1:
                        sim.sweep_index = i + 1
                        # Also ensure parameter values are set
                        if sweep_record.param1 == 'qubits' and not sim.sweep_value1:
                            sim.sweep_param1 = 'qubits'
                            sim.sweep_value1 = float(sim.qubits)
                        if sweep_record.param2 == 'drive_param' and not sim.sweep_value2:
                            sim.sweep_param2 = 'drive_param'
                            sim.sweep_value2 = float(sim.drive_param)
                
                db.session.commit()
                print(f"Indexed {len(simulations)} simulations for sweep {sweep_record.session_id}")
            
            print("\nParameter sweep database fix complete.")
            
            # Verify all sweep entries match their actual simulation counts
            all_sweeps = ParameterSweep.query.all()
            print("\nVerification of sweep records:")
            print("Session ID                  | Recorded | Actual")
            print("-" * 60)
            
            for sweep in all_sweeps:
                actual_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
                status = "✓" if sweep.completed_simulations == actual_count else "✗"
                print(f"{sweep.session_id:30} | {sweep.completed_simulations:8} | {actual_count:6} {status}")
            
            return True
            
        except Exception as e:
            print(f"Error: {str(e)}")
            traceback.print_exc()
            return False

if __name__ == "__main__":
    result = direct_sweep_fix()
    sys.exit(0 if result else 1)