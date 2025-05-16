"""
Script to fix the sweep tracking columns in the database.
"""
import os
from flask import Flask
import sqlalchemy as sa
from sqlalchemy import inspect

# Create a minimal Flask app for the migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")

def fix_sweep_columns():
    """
    Drop and recreate the parameter sweep tracking columns with the correct types.
    """
    print("Starting database fix for parameter sweep tracking columns...")
    
    # Connect to the database directly
    engine = sa.create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    inspector = inspect(engine)
    
    # Check if the simulation_results table exists
    if 'simulation_results' not in inspector.get_table_names():
        print("Error: simulation_results table not found")
        return False
    
    # Get existing columns
    columns = [column['name'] for column in inspector.get_columns('simulation_results')]
    
    # Define columns to fix
    columns_to_fix = [
        ('sweep_session', 'TEXT'),
        ('sweep_index', 'INTEGER'),
        ('sweep_param1', 'TEXT'),
        ('sweep_value1', 'FLOAT'),
        ('sweep_param2', 'TEXT'),
        ('sweep_value2', 'FLOAT')
    ]
    
    # Drop and recreate columns with correct types
    with engine.begin() as connection:
        for column_name, pg_type in columns_to_fix:
            if column_name in columns:
                print(f"Dropping and recreating column {column_name} with type {pg_type}...")
                connection.execute(sa.text(f"ALTER TABLE simulation_results DROP COLUMN {column_name}"))
                connection.execute(sa.text(f"ALTER TABLE simulation_results ADD COLUMN {column_name} {pg_type}"))
            else:
                print(f"Adding column {column_name} with type {pg_type}...")
                connection.execute(sa.text(f"ALTER TABLE simulation_results ADD COLUMN {column_name} {pg_type}"))
        
        # Add index on sweep_session if needed
        indices = inspector.get_indexes('simulation_results')
        index_names = [index['name'] for index in indices]
        
        if 'ix_simulation_results_sweep_session' not in index_names:
            print("Adding index on sweep_session column...")
            connection.execute(sa.text(
                "CREATE INDEX ix_simulation_results_sweep_session ON simulation_results (sweep_session)"
            ))
        else:
            print("Index on sweep_session already exists")
            
    print("Database fix completed successfully")
    return True

if __name__ == "__main__":
    success = fix_sweep_columns()
    print(f"Database fix {'completed successfully' if success else 'failed'}")