"""
Script to create a test parameter sweep to verify the database fix.
"""
import os
import sys
import datetime
from flask import Flask
from models import db, ParameterSweep, SimulationResult
import main

def run_test_sweep():
    """Run a test parameter sweep to verify the sweep tracking fix."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Creating a test parameter sweep to verify database tracking...")
        
        # Create a unique sweep name
        sweep_id = f"test_sweep_fix_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Define parameter sets for a simple sweep
        parameter_sets = []
        
        # Vary the qubits for this test
        for qubits in [8, 9, 10]:
            parameter_sets.append({
                'qubits': qubits,
                'time_points': 50,  # Use fewer time points for a quick test
                'drive_param': 0.9,
                'init_state': 'superposition'
            })
        
        # Create the parameter sweep record
        sweep_record = ParameterSweep()
        sweep_record.session_id = sweep_id
        sweep_record.circuit_type = 'penrose'
        sweep_record.param1 = 'qubits'
        sweep_record.param2 = None
        sweep_record.total_simulations = len(parameter_sets)
        sweep_record.completed_simulations = 0
        db.session.add(sweep_record)
        db.session.commit()
        
        print(f"Created parameter sweep record: {sweep_id}")
        
        # Run the sequential simulations
        main.run_sequential_simulations('penrose', parameter_sets, sweep_id)
        
        # Verify the sweep record was updated
        sweep_record = ParameterSweep.query.filter_by(session_id=sweep_id).first()
        simulations = SimulationResult.query.filter_by(sweep_session=sweep_id).all()
        
        print(f"\nSweep record status: {sweep_record.completed_simulations}/{sweep_record.total_simulations}")
        print(f"Actual simulations found: {len(simulations)}")
        
        for sim in simulations:
            print(f"  - {sim.result_name} (qubits={sim.qubits}, sweep_index={sim.sweep_index})")
        
        print(f"\nTest verification complete. View the sweep results at: /sweep_grid/{sweep_id}")
    
    return True

if __name__ == "__main__":
    try:
        success = run_test_sweep()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)