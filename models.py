"""
Database models for the quantum simulation package.
Contains SQLAlchemy models for storing simulation results.
"""
import datetime
import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class SimulationResult(db.Model):
    """Stores results from quantum simulations."""
    __tablename__ = 'simulation_results'
    
    id = db.Column(db.Integer, primary_key=True)
    result_name = db.Column(db.String(255), unique=True, nullable=False)
    circuit_type = db.Column(db.String(50), nullable=False)
    qubits = db.Column(db.Integer, nullable=False)
    shots = db.Column(db.Integer, nullable=False)
    drive_steps = db.Column(db.Integer, nullable=False)
    time_points = db.Column(db.Integer, nullable=False)
    max_time = db.Column(db.Float, nullable=False)
    drive_param = db.Column(db.Float, nullable=False)
    init_state = db.Column(db.String(50), nullable=False)
    
    # User preferences
    is_starred = db.Column(db.Boolean, default=False)
    
    # Parameter sweep information
    sweep_session = db.Column(db.String(255), db.ForeignKey('parameter_sweeps.session_id'), nullable=True, index=True)
    sweep_index = db.Column(db.Integer, nullable=True)
    sweep_param1 = db.Column(db.String(50), nullable=True)
    sweep_value1 = db.Column(db.Float, nullable=True)
    sweep_param2 = db.Column(db.String(50), nullable=True)
    sweep_value2 = db.Column(db.Float, nullable=True)
    
    # Relationship to the parameter sweep
    parameter_sweep = db.relationship('ParameterSweep', back_populates='simulations')
    
    # Analysis results
    drive_frequency = db.Column(db.Float, nullable=True)
    time_crystal_detected = db.Column(db.Boolean, default=False)
    incommensurate_count = db.Column(db.Integer, default=0)
    linear_combs_detected = db.Column(db.Boolean, default=False)
    log_combs_detected = db.Column(db.Boolean, default=False)
    
    # Path to result data and figures
    results_path = db.Column(db.String(255), nullable=False)
    elapsed_time = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Additional data stored as JSON
    extra_data = db.Column(db.Text, nullable=True)
    
    def set_extra_data(self, data_dict):
        """Serialize dictionary to JSON string for storage."""
        self.extra_data = json.dumps(data_dict)
    
    def get_extra_data(self):
        """Deserialize JSON string to dictionary."""
        if self.extra_data:
            return json.loads(self.extra_data)
        return {}
    
    def __repr__(self):
        return f"<SimulationResult {self.result_name} ({self.circuit_type}, {self.qubits} qubits)>"


class FrequencyPeak(db.Model):
    """Stores information about detected frequency peaks in simulations."""
    __tablename__ = 'frequency_peaks'
    
    id = db.Column(db.Integer, primary_key=True)
    simulation_id = db.Column(db.Integer, db.ForeignKey('simulation_results.id'), nullable=False)
    simulation = db.relationship('SimulationResult', backref=db.backref('peaks', lazy=True))
    
    frequency = db.Column(db.Float, nullable=False)
    amplitude = db.Column(db.Float, nullable=False)
    phase = db.Column(db.Float, nullable=True)
    component = db.Column(db.String(10), nullable=False)  # 'mx', 'my', 'mz'
    is_harmonic = db.Column(db.Boolean, default=False)
    is_incommensurate = db.Column(db.Boolean, default=False)
    is_comb_tooth = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f"<FrequencyPeak {self.frequency:.4f}Hz in {self.component}>"


class CombStructure(db.Model):
    """Stores information about detected frequency comb structures."""
    __tablename__ = 'comb_structures'
    
    id = db.Column(db.Integer, primary_key=True)
    simulation_id = db.Column(db.Integer, db.ForeignKey('simulation_results.id'), nullable=False)
    simulation = db.relationship('SimulationResult', backref=db.backref('combs', lazy=True))
    
    component = db.Column(db.String(10), nullable=False)  # 'mx', 'my', 'mz'
    is_logarithmic = db.Column(db.Boolean, default=False)
    base_frequency = db.Column(db.Float, nullable=False)
    spacing = db.Column(db.Float, nullable=False)  # For linear combs = omega, for log combs = ratio
    num_teeth = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        comb_type = "Logarithmic" if self.is_logarithmic else "Linear"
        return f"<{comb_type}Comb {self.base_frequency:.4f}Hz+{self.spacing:.4f} in {self.component}>"


class ParameterSweep(db.Model):
    """Stores information about parameter sweep sessions."""
    __tablename__ = 'parameter_sweeps'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    circuit_type = db.Column(db.String(50), nullable=False)
    param1 = db.Column(db.String(50), nullable=True)
    param2 = db.Column(db.String(50), nullable=True)
    total_simulations = db.Column(db.Integer, default=0)
    completed_simulations = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationship to simulations in this sweep
    simulations = db.relationship('SimulationResult', back_populates='parameter_sweep')
    
    def __repr__(self):
        return f"<ParameterSweep {self.session_id} - {self.circuit_type}>"