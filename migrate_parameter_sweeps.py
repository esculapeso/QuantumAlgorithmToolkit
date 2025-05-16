"""
Script to create the parameter_sweeps table and update relationships.
"""
import os
import sys
import datetime
import traceback

def migrate_database():
    """
    Run the database migration to add the parameter_sweeps table.
    """
    try:
        # Import Flask and database models
        from flask import Flask
        from models import db, ParameterSweep, SimulationResult

        # Create a Flask app
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)

        with app.app_context():
            # Create the parameter_sweeps table
            db.create_all()
            
            # Extract sweep sessions from existing simulation results
            sweep_sessions = db.session.query(
                SimulationResult.sweep_session, 
                SimulationResult.circuit_type,
                db.func.count(SimulationResult.id).label('count')
            ).filter(
                SimulationResult.sweep_session != None
            ).group_by(
                SimulationResult.sweep_session, 
                SimulationResult.circuit_type
            ).all()
            
            # Create ParameterSweep records for each unique sweep_session
            for sweep in sweep_sessions:
                # Check if this sweep session already exists in parameter_sweeps
                existing_sweep = ParameterSweep.query.filter_by(session_id=sweep.sweep_session).first()
                if existing_sweep:
                    continue
                
                # Get the first simulation to extract parameter names
                first_sim = SimulationResult.query.filter_by(sweep_session=sweep.sweep_session).first()
                
                if first_sim:
                    # Create a new ParameterSweep record
                    new_sweep = ParameterSweep(
                        session_id=sweep.sweep_session,
                        circuit_type=sweep.circuit_type,
                        param1=first_sim.sweep_param1,
                        param2=first_sim.sweep_param2,
                        total_simulations=sweep.count,
                        completed_simulations=sweep.count,
                        created_at=first_sim.created_at
                    )
                    db.session.add(new_sweep)
            
            # Commit changes
            db.session.commit()
            print("Parameter sweeps migration completed successfully.")
            
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("Migration completed successfully.")
    else:
        print("Migration failed.")
        sys.exit(1)