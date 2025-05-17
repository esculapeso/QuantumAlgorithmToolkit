"""
Script to add a database trigger to ensure parameter sweeps are properly updated.
This helps fix the issue with parameter sweep simulations not being correctly associated.
"""
import os
import sys
from flask import Flask
from sqlalchemy import create_engine, text
from models import db

def create_db_trigger():
    """Create a database trigger to ensure parameter sweeps are properly tracked."""
    # Set up Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    
    with app.app_context():
        print("Setting up parameter sweep tracking improvement...")
        
        # Get DB connection information
        db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        
        try:
            # Create database engine
            engine = create_engine(db_uri)
            
            # Execute a simple query to verify connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM parameter_sweeps"))
                sweep_count = result.scalar()
                print(f"Found {sweep_count} parameter sweep records.")
                
                # Create a function to scan for all possible sweep sessions
                print("Running consistency check on all sweep sessions...")
                
                # 1. First, collect unique sweep_session values
                result = conn.execute(text("""
                    SELECT DISTINCT sweep_session 
                    FROM simulation_results 
                    WHERE sweep_session IS NOT NULL
                """))
                
                sessions = [row[0] for row in result]
                print(f"Found {len(sessions)} unique sweep sessions in simulation records.")
                
                # 2. For each session, check if it has a parameter_sweep record
                for session_id in sessions:
                    # Check if parameter sweep record exists
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM parameter_sweeps
                        WHERE session_id = :session_id
                    """), {"session_id": session_id})
                    
                    has_record = result.scalar() > 0
                    
                    if not has_record:
                        print(f"Creating missing sweep record for {session_id}...")
                        
                        # Get information about the first simulation in this sweep
                        result = conn.execute(text("""
                            SELECT circuit_type, sweep_param1, sweep_param2, COUNT(*)
                            FROM simulation_results
                            WHERE sweep_session = :session_id
                            GROUP BY circuit_type, sweep_param1, sweep_param2
                            LIMIT 1
                        """), {"session_id": session_id})
                        
                        row = result.fetchone()
                        if row:
                            circuit_type, param1, param2, count = row
                            
                            # Insert the parameter sweep record
                            conn.execute(text("""
                                INSERT INTO parameter_sweeps 
                                (session_id, circuit_type, param1, param2, 
                                 total_simulations, completed_simulations, created_at)
                                VALUES
                                (:session_id, :circuit_type, :param1, :param2,
                                 :count, :count, CURRENT_TIMESTAMP)
                            """), {
                                "session_id": session_id,
                                "circuit_type": circuit_type,
                                "param1": param1,
                                "param2": param2,
                                "count": count
                            })
                            
                            conn.commit()
                            print(f"  Created sweep record for {session_id} with {count} simulations")
                
                # Create a database function to update parameter_sweeps based on simulation results
                print("\nSetting up automatic parameter sweep maintenance...")
                
                # First, check if our maintenance function exists
                result = conn.execute(text("""
                    SELECT 1 FROM pg_proc WHERE proname = 'update_parameter_sweep'
                """))
                
                if result.first():
                    print("Updating existing maintenance function...")
                    conn.execute(text("DROP FUNCTION IF EXISTS update_parameter_sweep()"))
                
                # Create a database function to update parameter sweeps
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION update_parameter_sweep()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        -- Only proceed if sweep_session is set
                        IF NEW.sweep_session IS NOT NULL THEN
                            -- Check if this sweep exists
                            IF NOT EXISTS (SELECT 1 FROM parameter_sweeps WHERE session_id = NEW.sweep_session) THEN
                                -- Create a new parameter sweep record
                                INSERT INTO parameter_sweeps 
                                    (session_id, circuit_type, param1, param2, 
                                     total_simulations, completed_simulations, created_at)
                                VALUES
                                    (NEW.sweep_session, NEW.circuit_type, NEW.sweep_param1, NEW.sweep_param2,
                                     1, 1, CURRENT_TIMESTAMP);
                            ELSE
                                -- Update the existing sweep record
                                UPDATE parameter_sweeps
                                SET completed_simulations = (
                                    SELECT COUNT(*) FROM simulation_results 
                                    WHERE sweep_session = NEW.sweep_session
                                ),
                                total_simulations = GREATEST(
                                    (SELECT COUNT(*) FROM simulation_results 
                                     WHERE sweep_session = NEW.sweep_session),
                                    total_simulations
                                )
                                WHERE session_id = NEW.sweep_session;
                            END IF;
                        END IF;
                        RETURN NULL;
                    END;
                    $$ LANGUAGE plpgsql;
                """))
                
                # Create a trigger to call this function whenever a simulation is added or updated
                conn.execute(text("""
                    DROP TRIGGER IF EXISTS simulation_sweep_trigger ON simulation_results;
                    
                    CREATE TRIGGER simulation_sweep_trigger
                    AFTER INSERT OR UPDATE ON simulation_results
                    FOR EACH ROW
                    WHEN (NEW.sweep_session IS NOT NULL)
                    EXECUTE FUNCTION update_parameter_sweep();
                """))
                
                conn.commit()
                print("Database trigger for parameter sweep maintenance installed successfully.")
                
                # Refresh existing sweep records based on actual simulation counts
                print("\nUpdating existing sweep records...")
                conn.execute(text("""
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
                """))
                
                conn.commit()
                print("All parameter sweep records updated.")
                
        except Exception as e:
            print(f"Error updating database: {str(e)}")
            traceback.print_exc()
            return False
            
    return True

if __name__ == "__main__":
    import traceback
    
    try:
        success = create_db_trigger()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)