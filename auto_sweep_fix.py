"""
Script to fix parameter sweep tracking by adding a direct connection in the model.
This creates database triggers to automatically maintain parameter sweep records.
"""
import os
import sys
import datetime
from flask import Flask
from models import db

def apply_sweep_fix():
    """Apply database fixes to ensure parameter sweeps are correctly tracked."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Applying parameter sweep tracking fix...")
        
        try:
            # Execute the SQL commands directly using a connection
            conn = db.engine.connect()
            
            # 1. Create SQL function that will update parameter_sweeps when simulations are added
            conn.execute(db.text('''
                CREATE OR REPLACE FUNCTION maintain_parameter_sweep()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.sweep_session IS NOT NULL THEN
                        -- Check if this sweep exists
                        IF NOT EXISTS (SELECT 1 FROM parameter_sweeps WHERE session_id = NEW.sweep_session) THEN
                            -- Create a new sweep record
                            INSERT INTO parameter_sweeps 
                                (session_id, circuit_type, param1, param2, 
                                 total_simulations, completed_simulations, created_at)
                            VALUES 
                                (NEW.sweep_session, NEW.circuit_type, NEW.sweep_param1, NEW.sweep_param2,
                                 1, 1, NEW.created_at);
                        ELSE
                            -- Update the existing sweep record
                            UPDATE parameter_sweeps
                            SET completed_simulations = (
                                SELECT COUNT(*) FROM simulation_results 
                                WHERE sweep_session = NEW.sweep_session
                            ),
                            circuit_type = COALESCE(circuit_type, NEW.circuit_type),
                            param1 = COALESCE(param1, NEW.sweep_param1),
                            param2 = COALESCE(param2, NEW.sweep_param2),
                            created_at = COALESCE(created_at, NEW.created_at)
                            WHERE session_id = NEW.sweep_session;
                        END IF;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            '''))
            
            # 2. Create a trigger to run this function after INSERT or UPDATE on simulation_results
            conn.execute(db.text('''
                DROP TRIGGER IF EXISTS sweep_maintenance_trigger ON simulation_results;
                
                CREATE TRIGGER sweep_maintenance_trigger
                AFTER INSERT OR UPDATE OF sweep_session ON simulation_results
                FOR EACH ROW
                EXECUTE FUNCTION maintain_parameter_sweep();
            '''))
            
            # 3. Fix any orphaned simulation records
            conn.execute(db.text('''
                SELECT DISTINCT sweep_session 
                FROM simulation_results 
                WHERE sweep_session IS NOT NULL
                  AND sweep_session NOT IN (SELECT session_id FROM parameter_sweeps)
            '''))
            
            orphaned_sessions = [row[0] for row in conn.fetchall()]
            print(f"Found {len(orphaned_sessions)} orphaned sweep sessions")
            
            for session_id in orphaned_sessions:
                # Get the first simulation for this session
                conn.execute(db.text('''
                    SELECT circuit_type, sweep_param1, sweep_param2, created_at, COUNT(*)
                    FROM simulation_results
                    WHERE sweep_session = :session_id
                    GROUP BY circuit_type, sweep_param1, sweep_param2, created_at
                    LIMIT 1
                '''), {"session_id": session_id})
                
                row = conn.fetchone()
                if row:
                    circuit_type, param1, param2, created_at, count = row
                    
                    # Create the parameter sweep record
                    conn.execute(db.text('''
                        INSERT INTO parameter_sweeps
                        (session_id, circuit_type, param1, param2, total_simulations, completed_simulations, created_at)
                        VALUES
                        (:session_id, :circuit_type, :param1, :param2, :count, :count, :created_at)
                    '''), {
                        "session_id": session_id,
                        "circuit_type": circuit_type,
                        "param1": param1,
                        "param2": param2,
                        "count": count,
                        "created_at": created_at or datetime.datetime.now()
                    })
                    
                    print(f"  Created parameter sweep record for {session_id}")
            
            # 4. Update the existing parameter sweep records with accurate counts
            conn.execute(db.text('''
                UPDATE parameter_sweeps ps
                SET completed_simulations = (
                    SELECT COUNT(*) FROM simulation_results
                    WHERE sweep_session = ps.session_id
                ),
                total_simulations = GREATEST(
                    (SELECT COUNT(*) FROM simulation_results 
                     WHERE sweep_session = ps.session_id),
                    ps.total_simulations
                )
            '''))
            
            conn.commit()
            print("Parameter sweep tracking fix applied successfully")
            
            # 5. Verify that all sweeps have accurate counts
            conn.execute(db.text('''
                SELECT ps.session_id, ps.total_simulations, ps.completed_simulations,
                       (SELECT COUNT(*) FROM simulation_results WHERE sweep_session = ps.session_id) as actual_count
                FROM parameter_sweeps ps
            '''))
            
            print("\nSweep Session Overview:")
            print("Session ID                  | Total | Completed | Actual")
            print("-" * 60)
            
            for row in conn.fetchall():
                session_id, total, completed, actual = row
                status = "✓" if completed == actual else "✗"
                print(f"{session_id:30} | {total:5} | {completed:9} | {actual:6} {status}")
            
            return True
            
        except Exception as e:
            print(f"Error applying sweep fix: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = apply_sweep_fix()
    sys.exit(0 if success else 1)