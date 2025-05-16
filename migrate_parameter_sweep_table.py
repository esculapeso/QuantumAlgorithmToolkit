"""
Script to create the parameter sweep table in the database and migrate existing data.
This script creates the parameter_sweeps table and populates it with data from existing simulations.
"""
import logging
import sys
import datetime
from flask import Flask
from models import db, ParameterSweep, SimulationResult

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_parameter_sweep_table():
    """
    Create the parameter_sweeps table and migrate existing sweep data.
    """
    try:
        # Create the parameter_sweeps table
        logging.info("Creating parameter_sweeps table...")
        db.create_all()
        logging.info("Parameter sweeps table successfully created")
        
        # Migrate existing sweep data
        migrate_existing_sweeps()
        
        return True
    except Exception as e:
        logging.error(f"Error creating parameter sweeps table: {e}")
        return False

def migrate_existing_sweeps():
    """
    Migrate existing sweep data from SimulationResult records to ParameterSweep records.
    """
    # Find all unique sweep_session values
    sweep_sessions = db.session.query(SimulationResult.sweep_session).filter(
        SimulationResult.sweep_session.isnot(None)
    ).distinct().all()
    
    logging.info(f"Found {len(sweep_sessions)} existing sweep sessions to migrate")
    
    # For each sweep session, create a ParameterSweep record
    for (session_id,) in sweep_sessions:
        # Check if this sweep session already exists in the parameter_sweeps table
        existing_sweep = ParameterSweep.query.filter_by(session_id=session_id).first()
        if existing_sweep:
            logging.info(f"Sweep session {session_id} already exists, skipping")
            continue
            
        # Get all simulations in this sweep
        simulations = SimulationResult.query.filter_by(sweep_session=session_id).all()
        
        if not simulations:
            continue
            
        # Get sample simulation to extract metadata
        sample = simulations[0]
        
        # Extract param names
        param1_name = sample.sweep_param1
        param2_name = sample.sweep_param2
        
        # Create new sweep record
        sweep = ParameterSweep()
        sweep.session_id = session_id
        sweep.circuit_type = sample.circuit_type
        sweep.param1_name = param1_name
        sweep.param2_name = param2_name
        sweep.total_simulations = len(simulations)
        sweep.completed_simulations = len(simulations)
        sweep.status = "completed"
        sweep.created_at = sample.created_at
        
        db.session.add(sweep)
        logging.info(f"Migrated sweep session {session_id} with {len(simulations)} simulations")
    
    # Commit the changes
    db.session.commit()
    logging.info("Sweep data migration completed")

if __name__ == "__main__":
    # Create a minimal Flask app for this script
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quantum_sim.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        if migrate_parameter_sweep_table():
            print("Parameter sweeps table created and data migrated successfully.")
        else:
            print("Failed to create parameter sweeps table or migrate data.")