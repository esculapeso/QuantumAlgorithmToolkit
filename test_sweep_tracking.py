"""
Script to directly test parameter sweep tracking functionality.
This will create a parameter sweep record and verify it works correctly.
"""
import os
import sys
import datetime
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def create_test_sweep():
    """
    Create a test parameter sweep record directly.
    """
    # Create Flask app context for the test
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        # Create a unique sweep ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sweep_id = f"test_direct_sweep_{timestamp}"
        
        # Create a new sweep record directly
        try:
            sweep = ParameterSweep()
            sweep.session_id = sweep_id
            sweep.circuit_type = "string_twistor_fc"
            sweep.param1 = "qubits"
            sweep.param2 = "drive_param"
            sweep.total_simulations = 4
            sweep.completed_simulations = 0
            
            # Save to database
            db.session.add(sweep)
            db.session.commit()
            print(f"Successfully created sweep record with ID: {sweep_id}")
            
            # Verify it was created
            new_sweep = ParameterSweep.query.filter_by(session_id=sweep_id).first()
            if new_sweep:
                print("Verified: Sweep record found in database.")
                print(f"  - Circuit type: {new_sweep.circuit_type}")
                print(f"  - Parameters: {new_sweep.param1}, {new_sweep.param2}")
                print(f"  - Simulation count: {new_sweep.completed_simulations}/{new_sweep.total_simulations}")
            else:
                print("Error: Sweep record was not found in database after creation.")
            
            # List all sweeps in the database
            print("\nAll parameter sweeps in database:")
            all_sweeps = ParameterSweep.query.all()
            for i, s in enumerate(all_sweeps):
                print(f"{i+1}. {s.session_id}: {s.circuit_type}, {s.completed_simulations}/{s.total_simulations}")
                
            return True
            
        except Exception as e:
            print(f"Error creating sweep record: {str(e)}")
            return False

if __name__ == "__main__":
    success = create_test_sweep()
    sys.exit(0 if success else 1)