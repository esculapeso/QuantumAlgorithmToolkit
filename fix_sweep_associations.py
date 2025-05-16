"""
Script to fix the association between parameter sweeps and their simulations.
This finds simulation results and links them to their parameter sweep sessions.
"""
import os
import re
import sys
from flask import Flask
from models import db, ParameterSweep, SimulationResult

def fix_sweep_associations():
    """
    Fix the association between parameter sweeps and their simulations.
    This matches simulations with parameter sweeps based on the sweep session ID pattern.
    """
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        # Get all parameter sweeps
        sweeps = ParameterSweep.query.all()
        print(f"Found {len(sweeps)} parameter sweep sessions.")
        
        for sweep in sweeps:
            # The session ID is also the scan name used in the results
            sweep_id = sweep.session_id
            
            # Find all simulations that might belong to this sweep
            # Look for simulations where the result_name contains the sweep_id
            potential_simulations = SimulationResult.query.filter(
                SimulationResult.result_name.like(f"%{sweep_id}%")
            ).all()
            
            # Alternatively, if we need more fine-grained matching:
            # Use a regular expression pattern to match the sweep ID in result names
            # potential_simulations = []
            # pattern = re.compile(rf"{sweep_id}_\d+_")
            # for sim in SimulationResult.query.all():
            #     if pattern.search(sim.result_name):
            #         potential_simulations.append(sim)
            
            print(f"Sweep: {sweep_id} ({sweep.circuit_type}) - Found {len(potential_simulations)} potential simulations.")
            
            if not potential_simulations:
                continue
            
            # Determine the sweep parameters from the first simulation
            if potential_simulations[0].sweep_param1 and not sweep.param1:
                sweep.param1 = potential_simulations[0].sweep_param1
            
            if potential_simulations[0].sweep_param2 and not sweep.param2:
                sweep.param2 = potential_simulations[0].sweep_param2
            
            # Update the circuit type if needed
            if sweep.circuit_type != potential_simulations[0].circuit_type:
                print(f"  Updating sweep circuit type from {sweep.circuit_type} to {potential_simulations[0].circuit_type}")
                sweep.circuit_type = potential_simulations[0].circuit_type
            
            # Associate each simulation with this sweep
            updated_count = 0
            for sim in potential_simulations:
                if sim.sweep_session != sweep_id:
                    sim.sweep_session = sweep_id
                    
                    # Extract sweep index from the result_name
                    # Pattern: sweep_id_INDEX_...
                    match = re.search(rf"{sweep_id}_(\d+)_", sim.result_name)
                    if match:
                        sim.sweep_index = int(match.group(1))
                    else:
                        # Fallback: just use the order in the list
                        sim.sweep_index = potential_simulations.index(sim) + 1
                    
                    updated_count += 1
            
            # Update the sweep with correct simulation count
            sweep.completed_simulations = len(potential_simulations)
            sweep.total_simulations = len(potential_simulations)
            
            print(f"  Updated {updated_count} simulations with sweep association {sweep_id}")
            print(f"  Updated sweep record: {sweep.completed_simulations}/{sweep.total_simulations} simulations")
        
        # Commit all changes
        db.session.commit()
        print("All sweep associations have been fixed.")
        
    return True

if __name__ == "__main__":
    success = fix_sweep_associations()
    sys.exit(0 if success else 1)