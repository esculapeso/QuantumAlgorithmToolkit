"""
Fixed application file for the quantum simulation project.
This file handles all the Flask application setup to ensure proper database integration.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

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

# Apply ProxyFix for proper URL generation
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")