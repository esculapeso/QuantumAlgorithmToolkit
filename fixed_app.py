"""
Fixed application file for the quantum simulation project.
This file resolves SQLAlchemy initialization issues.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

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

# Create the SQLAlchemy instance AFTER app is configured
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Import models first
with app.app_context():
    import models  # noqa: F401

# Initialize Login Manager 
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()
    
    # Create admin user if it doesn't exist
    try:
        from models import User
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
        print(f"Error setting up admin user: {e}")

# Import all routes AFTER the app and models are fully initialized
import routes