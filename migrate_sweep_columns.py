"""
Script to run the database migration to add parameter sweep tracking columns.
"""
import sys
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import inspect

# Create a minimal Flask app for the migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db = SQLAlchemy(app)

def migrate_database():
    """
    Run the database migration to add the parameter sweep tracking columns.
    """
    print("Starting database migration to add parameter sweep tracking columns...")
    
    # Connect to the database
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        
        # Check if the simulation_results table exists
        if 'simulation_results' not in inspector.get_table_names():
            print("Error: simulation_results table not found")
            return False
        
        # Get existing columns
        columns = [column['name'] for column in inspector.get_columns('simulation_results')]
        
        # Define columns to add
        columns_to_add = [
            ('sweep_session', sa.String(255)),
            ('sweep_index', sa.Integer),
            ('sweep_param1', sa.String(50)),
            ('sweep_value1', sa.Float),
            ('sweep_param2', sa.String(50)),
            ('sweep_value2', sa.Float)
        ]
        
        # Add columns if they don't exist
        with engine.begin() as connection:
            for column_name, column_type in columns_to_add:
                if column_name not in columns:
                    print(f"Adding column {column_name} to simulation_results table...")
                    # Convert SQLAlchemy types to PostgreSQL types
                    pg_type = "VARCHAR(255)" if isinstance(column_type, sa.String) and column_type.length == 255 else \
                             "VARCHAR(50)" if isinstance(column_type, sa.String) and column_type.length == 50 else \
                             "INTEGER" if isinstance(column_type, sa.Integer) else \
                             "FLOAT" if isinstance(column_type, sa.Float) else \
                             "TEXT"
                    connection.execute(sa.text(
                        f"ALTER TABLE simulation_results ADD COLUMN {column_name} {pg_type}"
                    ))
                else:
                    print(f"Column {column_name} already exists")
            
            # Add index on sweep_session if it doesn't exist
            indices = inspector.get_indexes('simulation_results')
            index_names = [index['name'] for index in indices]
            
            if 'ix_simulation_results_sweep_session' not in index_names:
                print("Adding index on sweep_session column...")
                connection.execute(sa.text(
                    "CREATE INDEX ix_simulation_results_sweep_session ON simulation_results (sweep_session)"
                ))
            else:
                print("Index on sweep_session already exists")
                
        print("Migration completed successfully")
        return True

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)