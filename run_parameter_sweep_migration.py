"""
Script to create the parameter_sweeps table and initialize it with existing sweep data.
"""
import os
import sys
import traceback
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def run_migration():
    """
    Create the parameter_sweeps table and populate it with data from existing sweeps.
    """
    try:
        # Create a Flask app context
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        
        with app.app_context():
            # Check if the parameter_sweeps table exists
            print("Checking if parameter_sweeps table exists...")
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'parameter_sweeps' not in tables:
                print("Creating parameter_sweeps table...")
                db.create_all()
            else:
                print("parameter_sweeps table already exists.")
            
            # Get all unique sweep sessions from simulation_results
            print("Finding existing parameter sweeps...")
            sweep_sessions = db.session.query(
                SimulationResult.sweep_session,
                SimulationResult.circuit_type,
                db.func.count(SimulationResult.id).label('sim_count')
            ).filter(
                SimulationResult.sweep_session != None
            ).group_by(
                SimulationResult.sweep_session,
                SimulationResult.circuit_type
            ).all()
            
            print(f"Found {len(sweep_sessions)} existing sweep sessions.")
            
            # Create ParameterSweep records for each sweep session
            for i, sweep in enumerate(sweep_sessions):
                # Check if sweep already exists
                existing = ParameterSweep.query.filter_by(session_id=sweep.sweep_session).first()
                if existing:
                    print(f"  Sweep {i+1}/{len(sweep_sessions)}: {sweep.sweep_session} already exists.")
                    continue
                
                # Get parameter information from first simulation in sweep
                first_sim = SimulationResult.query.filter_by(sweep_session=sweep.sweep_session).first()
                
                if first_sim:
                    # Create new sweep record
                    new_sweep = ParameterSweep()
                    new_sweep.session_id = sweep.sweep_session
                    new_sweep.circuit_type = sweep.circuit_type
                    new_sweep.param1 = first_sim.sweep_param1
                    new_sweep.param2 = first_sim.sweep_param2
                    new_sweep.total_simulations = sweep.sim_count
                    new_sweep.completed_simulations = sweep.sim_count
                    new_sweep.created_at = first_sim.created_at
                    
                    # Save to database
                    db.session.add(new_sweep)
                    print(f"  Created sweep {i+1}/{len(sweep_sessions)}: {sweep.sweep_session} with {sweep.sim_count} simulations.")
            
            # Commit all changes
            db.session.commit()
            print("Migration completed successfully.")
            
            # Verify migration
            all_sweeps = ParameterSweep.query.all()
            print(f"Total parameter sweeps in database: {len(all_sweeps)}")
            for sweep in all_sweeps:
                print(f"  - {sweep.session_id}: {sweep.circuit_type}, {sweep.completed_simulations}/{sweep.total_simulations} simulations")
            
            return True
            
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)