"""
Final fix for parameter sweep database tracking.
This script fixes all aspects of parameter sweep tracking, ensuring sweeps are properly recorded.
"""
import os
import sys
import datetime
from flask import Flask
from sqlalchemy import create_engine, text
from models import db, ParameterSweep, SimulationResult

def final_sweep_fix():
    """Apply final fixes to ensure parameter sweep database tracking works properly."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("\nFinal parameter sweep tracking fix")
        print("================================")
        
        # 1. First, check the parameter_scan_20250517 records
        scan_name = "parameter_scan_20250517"
        print(f"\nChecking parameter scan: {scan_name}")
        
        sweep_record = ParameterSweep.query.filter_by(session_id=scan_name).first()
        simulations = SimulationResult.query.filter(
            SimulationResult.result_name.like(f"%{scan_name}%")
        ).all()
        
        if sweep_record:
            print(f"  Found sweep record: {sweep_record.session_id} ({sweep_record.completed_simulations}/{sweep_record.total_simulations})")
        else:
            print(f"  No sweep record found for {scan_name}")
        
        print(f"  Found {len(simulations)} simulations that match the pattern")
        
        if not sweep_record and simulations:
            # Create the sweep record
            circuit_type = simulations[0].circuit_type
            
            # Determine swept parameters
            qubits = set(sim.qubits for sim in simulations)
            drive_params = set(sim.drive_param for sim in simulations)
            
            param1 = None
            param2 = None
            
            if len(qubits) > 1:
                param1 = 'qubits'
                print(f"    Detected 'qubits' parameter sweep: {qubits}")
            
            if len(drive_params) > 1:
                if param1:
                    param2 = 'drive_param'
                else:
                    param1 = 'drive_param'
                print(f"    Detected 'drive_param' parameter sweep: {drive_params}")
            
            new_sweep = ParameterSweep()
            new_sweep.session_id = scan_name
            new_sweep.circuit_type = circuit_type
            new_sweep.param1 = param1
            new_sweep.param2 = param2
            new_sweep.total_simulations = len(simulations)
            new_sweep.completed_simulations = len(simulations)
            new_sweep.created_at = simulations[0].created_at
            
            db.session.add(new_sweep)
            db.session.commit()
            
            print(f"    Created new sweep record for {scan_name} with {len(simulations)} simulations")
        
        # 2. Update the sweep_session field for simulations that match patterns
        print("\nFixing graphene_fc_parameter_scan_20250517 records...")
        
        # Find all simulations that match the pattern but don't have sweep_session set
        pattern = "graphene_fc_parameter_scan_20250517"
        orphaned_sims = SimulationResult.query.filter(
            SimulationResult.result_name.like(f"%{pattern}%"),
            SimulationResult.sweep_session.is_(None)
        ).all()
        
        if orphaned_sims:
            print(f"  Found {len(orphaned_sims)} orphaned simulations matching '{pattern}'")
            
            # Create or update sweep record
            sweep_record = ParameterSweep.query.filter_by(session_id=pattern).first()
            
            if not sweep_record:
                # Create new sweep record
                new_sweep = ParameterSweep()
                new_sweep.session_id = pattern
                new_sweep.circuit_type = orphaned_sims[0].circuit_type
                new_sweep.param1 = 'qubits'  # Most likely parameter being swept
                new_sweep.param2 = None
                new_sweep.total_simulations = len(orphaned_sims)
                new_sweep.completed_simulations = len(orphaned_sims)
                new_sweep.created_at = orphaned_sims[0].created_at
                
                db.session.add(new_sweep)
                db.session.commit()
                print(f"  Created sweep record for {pattern}")
                sweep_record = new_sweep
            
            # Update each simulation to be associated with this sweep
            for i, sim in enumerate(sorted(orphaned_sims, key=lambda s: s.result_name)):
                sim.sweep_session = pattern
                sim.sweep_index = i + 1
                sim.sweep_param1 = 'qubits'
                sim.sweep_value1 = float(sim.qubits)
                print(f"  Linked simulation: {sim.result_name}")
            
            sweep_record.completed_simulations = len(orphaned_sims)
            sweep_record.total_simulations = max(sweep_record.total_simulations, len(orphaned_sims))
            db.session.commit()
            print(f"  Updated sweep record: {sweep_record.completed_simulations}/{sweep_record.total_simulations}")
        
        # 3. Fix the qft_basic_parameter_scan_20250517 records
        print("\nFixing qft_basic_parameter_scan_20250517 records...")
        
        # Find all simulations that match the pattern but don't have sweep_session set
        pattern = "qft_basic_parameter_scan_20250517"
        orphaned_sims = SimulationResult.query.filter(
            SimulationResult.result_name.like(f"%{pattern}%"),
            SimulationResult.sweep_session.is_(None)
        ).all()
        
        if orphaned_sims:
            print(f"  Found {len(orphaned_sims)} orphaned simulations matching '{pattern}'")
            
            # Create or update sweep record
            sweep_record = ParameterSweep.query.filter_by(session_id=pattern).first()
            
            if not sweep_record:
                # Create new sweep record
                new_sweep = ParameterSweep()
                new_sweep.session_id = pattern
                new_sweep.circuit_type = orphaned_sims[0].circuit_type
                new_sweep.param1 = 'qubits'  # Most likely parameter being swept
                new_sweep.param2 = None
                new_sweep.total_simulations = len(orphaned_sims)
                new_sweep.completed_simulations = len(orphaned_sims)
                new_sweep.created_at = orphaned_sims[0].created_at
                
                db.session.add(new_sweep)
                db.session.commit()
                print(f"  Created sweep record for {pattern}")
                sweep_record = new_sweep
            
            # Update each simulation to be associated with this sweep
            for i, sim in enumerate(sorted(orphaned_sims, key=lambda s: s.result_name)):
                sim.sweep_session = pattern
                sim.sweep_index = i + 1
                sim.sweep_param1 = 'qubits'
                sim.sweep_value1 = float(sim.qubits)
                print(f"  Linked simulation: {sim.result_name}")
            
            sweep_record.completed_simulations = len(orphaned_sims)
            sweep_record.total_simulations = max(sweep_record.total_simulations, len(orphaned_sims))
            db.session.commit()
            print(f"  Updated sweep record: {sweep_record.completed_simulations}/{sweep_record.total_simulations}")
        
        # 4. Check for test_db_sweep_ records
        print("\nFixing test_db_sweep records...")
        
        # Get all sweep sessions for test_db_sweep
        test_sweeps = ParameterSweep.query.filter(
            ParameterSweep.session_id.like("test_db_sweep_%")
        ).all()
        
        for sweep in test_sweeps:
            simulations = SimulationResult.query.filter(
                SimulationResult.result_name.like(f"%{sweep.session_id}%")
            ).all()
            
            if simulations:
                print(f"  Found {len(simulations)} simulations for {sweep.session_id}")
                
                # Update simulations to link to this sweep
                for i, sim in enumerate(sorted(simulations, key=lambda s: s.result_name)):
                    if sim.sweep_session != sweep.session_id:
                        sim.sweep_session = sweep.session_id
                        sim.sweep_index = i + 1
                        if sweep.param1 == 'drive_param':
                            sim.sweep_param1 = 'drive_param'
                            sim.sweep_value1 = float(sim.drive_param)
                        print(f"  Linked simulation: {sim.result_name}")
                
                sweep.completed_simulations = len(simulations)
                db.session.commit()
                print(f"  Updated sweep record: {sweep.completed_simulations}/{sweep.total_simulations}")
        
        # Final verification
        print("\nVerifying all sweep records...")
        all_sweeps = ParameterSweep.query.all()
        
        print("\nSweep Session Overview:")
        print("Session ID                       | Total | Completed | Actual")
        print("-" * 65)
        
        for sweep in all_sweeps:
            actual_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
            status = "✓" if sweep.completed_simulations == actual_count else "✗"
            
            print(f"{sweep.session_id:32} | {sweep.total_simulations:5} | {sweep.completed_simulations:9} | {actual_count:6} {status}")
            
            if sweep.completed_simulations != actual_count:
                # Fix the count
                sweep.completed_simulations = actual_count
                db.session.commit()
                print(f"  Fixed count for {sweep.session_id}: {actual_count}/{sweep.total_simulations}")
        
        print("\nFinal sweep tracking fix complete!")
        
    return True

if __name__ == "__main__":
    try:
        success = final_sweep_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)