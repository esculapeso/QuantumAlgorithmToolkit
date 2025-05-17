"""
A quick direct fix for the parameter sweep tracking.
This script searches for any simulations from parameter_scan_20250517 
and ensures they're properly linked in the database.
"""
import os
import sys
import traceback
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def quick_sweep_fix():
    """Quickly fix the parameter sweep tracking for specific sweeps."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Looking for recent sweep simulations...")
        
        # Find recent simulation results
        recent_simulations = SimulationResult.query.filter(
            SimulationResult.result_name.like('%parameter_scan_20250517%')
        ).all()
        
        print(f"Found {len(recent_simulations)} recent simulation(s)")
        
        # Group by their potential sweep session
        sweep_groups = {}
        for sim in recent_simulations:
            parts = sim.result_name.split('_')
            # Find the parameter_scan part
            for i, part in enumerate(parts):
                if part == 'parameter' and i+1 < len(parts) and parts[i+1] == 'scan':
                    sweep_id = f"parameter_scan_{parts[i+2]}"
                    if sweep_id not in sweep_groups:
                        sweep_groups[sweep_id] = []
                    sweep_groups[sweep_id].append(sim)
                    break
        
        print(f"Identified {len(sweep_groups)} potential sweep sessions")
        
        # Process each sweep group
        for sweep_id, simulations in sweep_groups.items():
            print(f"\nProcessing sweep: {sweep_id} with {len(simulations)} simulations")
            
            # Check if a parameter sweep record exists
            sweep_record = ParameterSweep.query.filter_by(session_id=sweep_id).first()
            
            if not sweep_record:
                print(f"Creating new parameter sweep record for {sweep_id}")
                sweep_record = ParameterSweep()
                sweep_record.session_id = sweep_id
                sweep_record.circuit_type = simulations[0].circuit_type
                
                # Try to identify the swept parameters
                qubits = set(sim.qubits for sim in simulations)
                drive_params = set(sim.drive_param for sim in simulations)
                
                # Determine which parameters are being swept
                if len(qubits) > 1:
                    sweep_record.param1 = 'qubits'
                    print(f"  Detected 'qubits' parameter sweep: {qubits}")
                
                if len(drive_params) > 1:
                    if sweep_record.param1:
                        sweep_record.param2 = 'drive_param'
                    else:
                        sweep_record.param1 = 'drive_param'
                    print(f"  Detected 'drive_param' parameter sweep: {drive_params}")
                
                sweep_record.total_simulations = len(simulations)
                sweep_record.completed_simulations = len(simulations)
                sweep_record.created_at = simulations[0].created_at
                
                db.session.add(sweep_record)
                db.session.commit()
                print(f"  Created parameter sweep record: {sweep_id}")
            else:
                print(f"Updating existing parameter sweep record: {sweep_id}")
                sweep_record.total_simulations = max(sweep_record.total_simulations, len(simulations))
                sweep_record.completed_simulations = len(simulations)
                db.session.commit()
                print(f"  Updated parameter sweep record: {sweep_id}")
            
            # Update each simulation to be associated with this sweep
            for i, sim in enumerate(sorted(simulations, key=lambda s: s.result_name)):
                if not sim.sweep_session or sim.sweep_session != sweep_id:
                    print(f"  Linking simulation: {sim.result_name}")
                    sim.sweep_session = sweep_id
                    sim.sweep_index = i + 1
                    
                    # Set parameter values if we can determine them
                    if sweep_record.param1 == 'qubits':
                        sim.sweep_param1 = 'qubits'
                        sim.sweep_value1 = float(sim.qubits)
                    elif sweep_record.param1 == 'drive_param':
                        sim.sweep_param1 = 'drive_param'
                        sim.sweep_value1 = float(sim.drive_param)
                    
                    if sweep_record.param2 == 'qubits':
                        sim.sweep_param2 = 'qubits'
                        sim.sweep_value2 = float(sim.qubits)
                    elif sweep_record.param2 == 'drive_param':
                        sim.sweep_param2 = 'drive_param'
                        sim.sweep_value2 = float(sim.drive_param)
                
            db.session.commit()
            print(f"  Updated {len(simulations)} simulation records")
        
        print("\nFix completed successfully")
        return True

if __name__ == "__main__":
    try:
        success = quick_sweep_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)