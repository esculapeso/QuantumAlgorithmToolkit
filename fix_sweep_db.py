"""
Script to fix database issues with parameter sweeps.
This script updates all parameter sweep records to ensure they accurately reflect completed simulations.
"""
import os
import re
import datetime
from flask import Flask
from sqlalchemy import create_engine, text
from models import db, ParameterSweep, SimulationResult

def fix_sweep_database():
    """Update parameter sweep records to match completed simulations."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Starting sweep database repair...")
        
        # 1. First, check all simulations that have sweep information but no sweep record
        print("\nChecking for orphaned sweep simulations...")
        orphaned_simulations = SimulationResult.query.filter(
            SimulationResult.sweep_session.isnot(None),
            ~SimulationResult.sweep_session.in_(
                db.session.query(ParameterSweep.session_id)
            )
        ).all()
        
        orphaned_sessions = {}
        for sim in orphaned_simulations:
            if sim.sweep_session not in orphaned_sessions:
                orphaned_sessions[sim.sweep_session] = []
            orphaned_sessions[sim.sweep_session].append(sim)
        
        print(f"Found {len(orphaned_sessions)} orphaned sweep sessions with {len(orphaned_simulations)} total simulations.")
        
        # 2. Create missing sweep records
        for session_id, simulations in orphaned_sessions.items():
            print(f"\nCreating sweep record for: {session_id}")
            
            # Get circuit type and parameters from the first simulation
            first_sim = simulations[0]
            circuit_type = first_sim.circuit_type
            param1 = first_sim.sweep_param1
            param2 = first_sim.sweep_param2
            
            # Create a new sweep record
            new_sweep = ParameterSweep()
            new_sweep.session_id = session_id
            new_sweep.circuit_type = circuit_type
            new_sweep.param1 = param1
            new_sweep.param2 = param2
            new_sweep.total_simulations = len(simulations)
            new_sweep.completed_simulations = len(simulations)
            new_sweep.created_at = first_sim.created_at
            
            db.session.add(new_sweep)
            print(f"  Added sweep record: {circuit_type}, {param1}/{param2}, {len(simulations)} simulations")
        
        db.session.commit()
        
        # 3. Check for mismatched simulation counts
        print("\nChecking for incorrect simulation counts...")
        all_sweeps = ParameterSweep.query.all()
        
        for sweep in all_sweeps:
            actual_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
            if sweep.completed_simulations != actual_count or sweep.total_simulations < actual_count:
                print(f"Updating {sweep.session_id}: recorded={sweep.completed_simulations}/{sweep.total_simulations}, actual={actual_count}")
                sweep.completed_simulations = actual_count
                if sweep.total_simulations < actual_count:
                    sweep.total_simulations = actual_count
        
        db.session.commit()
        
        # 4. Update sweep indexes if needed
        print("\nChecking for incorrect sweep indexes...")
        for sweep in all_sweeps:
            simulations = SimulationResult.query.filter_by(sweep_session=sweep.session_id).all()
            
            if not simulations:
                continue
                
            # Sort simulations to ensure proper ordering
            for i, sim in enumerate(sorted(simulations, key=lambda s: s.result_name)):
                if sim.sweep_index != i + 1:
                    print(f"  Updating {sim.result_name}: index {sim.sweep_index} -> {i+1}")
                    sim.sweep_index = i + 1
        
        db.session.commit()
        
        # 5. Check for the latest sweep session and update it
        print("\nChecking for recent sweep sessions without simulations...")
        # Get the most recent sweep
        recent_sweeps = ParameterSweep.query.order_by(ParameterSweep.created_at.desc()).limit(5).all()
        
        for sweep in recent_sweeps:
            sim_count = SimulationResult.query.filter_by(sweep_session=sweep.session_id).count()
            
            if sim_count == 0:
                print(f"Recent sweep {sweep.session_id} has 0 simulations.")
                
                # Check if there are any simulations with similar names
                potential_simulations = SimulationResult.query.filter(
                    SimulationResult.result_name.like(f"%{sweep.session_id}%")
                ).all()
                
                if potential_simulations:
                    print(f"  Found {len(potential_simulations)} potential simulations for {sweep.session_id}")
                    
                    for sim in potential_simulations:
                        if not sim.sweep_session:
                            sim.sweep_session = sweep.session_id
                            sim.sweep_param1 = sweep.param1
                            sim.sweep_param2 = sweep.param2
                            
                            # Try to extract index from name
                            match = re.search(r'_(\d+)_', sim.result_name)
                            if match:
                                sim.sweep_index = int(match.group(1))
                            
                            print(f"  Associated {sim.result_name} with sweep {sweep.session_id}")
                    
                    # Update the sweep record
                    sweep.completed_simulations = len(potential_simulations)
                    sweep.total_simulations = max(sweep.total_simulations, len(potential_simulations))
                    
                    print(f"  Updated sweep {sweep.session_id}: {sweep.completed_simulations}/{sweep.total_simulations}")
        
        db.session.commit()
        
        print("\nDatabase sweep repair completed successfully.")

if __name__ == "__main__":
    fix_sweep_database()