"""
Script to create a test parameter sweep with directly linked simulations,
specifically for testing the grid layout with both parameters varying.
"""
import os
import sys
import datetime
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def create_grid_sweep():
    """
    Create a test parameter sweep with directly linked simulations for the grid view.
    This creates a grid with 2 different parameters.
    """
    # Create Flask app context for the test
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        # Create a unique sweep ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sweep_id = f"test_grid_sweep_{timestamp}"
        
        # Create a new sweep record
        sweep = ParameterSweep()
        sweep.session_id = sweep_id
        sweep.circuit_type = "graphene_fc"
        sweep.param1 = "qubits"
        sweep.param2 = "drive_param"
        sweep.total_simulations = 6
        sweep.completed_simulations = 6
        
        # Save to database
        db.session.add(sweep)
        db.session.commit()
        print(f"Created sweep record: {sweep_id}")
        
        # Find graphene_fc simulations with different parameters
        simulations = SimulationResult.query.filter_by(circuit_type="graphene_fc").order_by(SimulationResult.created_at.desc()).limit(6).all()
        
        if len(simulations) < 6:
            print(f"Not enough graphene_fc simulations found. Need 6, found {len(simulations)}.")
            return False
        
        # Set values for the grid - We'll create a 2x3 grid with:
        # qubits: [3, 4, 5] as rows (param1)
        # drive_param: [0.7, 0.9] as columns (param2)
        qubit_values = [3, 4, 5]
        drive_values = [0.7, 0.9]
        
        # Update the simulations to link to the sweep
        sim_index = 0
        for qubit in qubit_values:
            for drive in drive_values:
                sim = simulations[sim_index]
                sim.sweep_session = sweep_id
                sim.sweep_index = sim_index + 1
                sim.sweep_param1 = "qubits"
                sim.sweep_value1 = float(qubit)
                sim.sweep_param2 = "drive_param"
                sim.sweep_value2 = float(drive)
                print(f"Linked simulation {sim_index+1}: {sim.result_name} (qubits={qubit}, drive_param={drive})")
                sim_index += 1
        
        db.session.commit()
        print(f"Successfully linked {len(simulations)} simulations to sweep {sweep_id}")
        
        print("\nTest sweep details:")
        print(f"Sweep ID: {sweep_id}")
        print(f"Circuit Type: {sweep.circuit_type}")
        print(f"Parameter 1: {sweep.param1} (rows)")
        print(f"Parameter 2: {sweep.param2} (columns)")
        print(f"Grid: {len(qubit_values)}x{len(drive_values)} (rows x columns)")
        print(f"Simulations: {sweep.completed_simulations}/{sweep.total_simulations}")
        
        print("\nYou can view this sweep at: /sweep_grid/" + sweep_id)
        return True

if __name__ == "__main__":
    create_grid_sweep()