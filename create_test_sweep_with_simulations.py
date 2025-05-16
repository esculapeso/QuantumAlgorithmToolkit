"""
Script to create a test parameter sweep with directly linked simulations.
"""
import os
import sys
import datetime
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def create_test_sweep():
    """
    Create a test parameter sweep with directly linked simulations.
    """
    # Create Flask app context for the test
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        # Create a unique sweep ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sweep_id = f"test_direct_linked_sweep_{timestamp}"
        
        # Create a new sweep record
        sweep = ParameterSweep()
        sweep.session_id = sweep_id
        sweep.circuit_type = "qft_basic"
        sweep.param1 = "qubits"
        sweep.param2 = None
        sweep.total_simulations = 3
        sweep.completed_simulations = 3
        
        # Save to database
        db.session.add(sweep)
        db.session.commit()
        print(f"Created sweep record: {sweep_id}")
        
        # Find three recent QFT simulations to link to this sweep
        simulations = SimulationResult.query.filter_by(circuit_type="qft_basic").order_by(SimulationResult.created_at.desc()).limit(3).all()
        
        if simulations:
            # Update the simulations to link to the sweep
            for i, sim in enumerate(simulations):
                sim.sweep_session = sweep_id
                sim.sweep_index = i + 1
                sim.sweep_param1 = "qubits"
                sim.sweep_value1 = float(sim.qubits)
                sim.sweep_param2 = None
                sim.sweep_value2 = None
                print(f"Linked simulation {i+1}: {sim.result_name} (qubits={sim.qubits})")
            
            db.session.commit()
            print(f"Successfully linked {len(simulations)} simulations to sweep {sweep_id}")
            
            print("\nTest sweep details:")
            print(f"Sweep ID: {sweep_id}")
            print(f"Circuit Type: {sweep.circuit_type}")
            print(f"Parameter 1: {sweep.param1}")
            print(f"Simulations: {sweep.completed_simulations}/{sweep.total_simulations}")
            
            print("\nYou can view this sweep at: /sweep_grid/" + sweep_id)
            return True
        else:
            print("No simulations found to link to sweep.")
            return False

if __name__ == "__main__":
    create_test_sweep()