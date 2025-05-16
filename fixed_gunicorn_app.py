"""
Fixed gunicorn entry point for the quantum simulation application.
This file will properly initialize and configure the Flask application.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Create the SQLAlchemy instance
db = SQLAlchemy(model_class=Base)

# Create the Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "quantum-simulation-secret")

# Configure the application
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///quantum_sim.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with SQLAlchemy
db.init_app(app)

# Initialize database tables
with app.app_context():
    try:
        # Import models here to avoid circular imports
        from models import User, SimulationResult, FrequencyPeak, CombStructure, ParameterSweep
        db.create_all()
        print("Database tables created successfully!")
        
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            admin.username = 'admin'
            admin.role = 'admin'
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Import routes after app is created and initialized
import routes

# This allows gunicorn to find the application
application = app