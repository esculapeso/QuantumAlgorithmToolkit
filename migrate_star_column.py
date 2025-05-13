"""
Script to run the database migration to add the is_starred column.
"""
import os
import sys
from sqlalchemy import text

# Add the current directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from models import db

def migrate_database():
    """
    Run the database migration to add the is_starred column to the simulation_results table.
    """
    print("Starting database migration to add is_starred column...")
    
    with app.app_context():
        try:
            # Check if column already exists
            conn = db.engine.connect()
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='simulation_results' AND column_name='is_starred'"
            ))
            
            if result.rowcount > 0:
                print("Column is_starred already exists, skipping migration")
                return
            
            # Add the column
            conn.execute(text(
                "ALTER TABLE simulation_results ADD COLUMN is_starred BOOLEAN DEFAULT FALSE"
            ))
            
            # Commit the transaction
            conn.commit()
            
            print("Successfully added is_starred column to simulation_results table")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            
if __name__ == "__main__":
    migrate_database()