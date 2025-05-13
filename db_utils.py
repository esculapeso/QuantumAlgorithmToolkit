"""
Database utility functions for the quantum simulation package.
"""
from models import db, SimulationResult, FrequencyPeak, CombStructure

def save_simulation_to_db(result, result_name):
    """
    Save simulation results to the database.
    
    Args:
        result (dict): The simulation result dictionary
        result_name (str): The name/ID of the result folder
    
    Returns:
        SimulationResult: The created database record
    """
    # Extract parameters
    params = result.get('parameters', {})
    
    # Extract analysis results
    analysis = result.get('analysis', {})
    fc_analysis = result.get('fc_analysis', {})
    comb_analysis = result.get('comb_analysis', {})
    log_comb_analysis = result.get('log_comb_analysis', {})
    
    # Create simulation result record
    sim_result = SimulationResult()
    sim_result.result_name = result_name
    sim_result.circuit_type = params.get('circuit_type', '')
    sim_result.qubits = params.get('qubits', 0)
    sim_result.shots = params.get('shots', 0)
    sim_result.drive_steps = params.get('drive_steps', 0)
    sim_result.time_points = params.get('time_points', 0)
    sim_result.max_time = params.get('max_time', 0.0)
    sim_result.drive_param = params.get('drive_param', 0.0)
    sim_result.init_state = params.get('init_state', '')
    
    sim_result.drive_frequency = analysis.get('drive_frequency', 0.0)
    sim_result.time_crystal_detected = analysis.get('has_subharmonics', False)
    sim_result.incommensurate_count = fc_analysis.get('incommensurate_peak_count', 0)
    sim_result.linear_combs_detected = (
        comb_analysis.get('mx_comb_found', False) or 
        comb_analysis.get('mz_comb_found', False)
    )
    sim_result.log_combs_detected = (
        log_comb_analysis.get('mx_log_comb_found', False) or 
        log_comb_analysis.get('mz_log_comb_found', False)
    )
    
    sim_result.results_path = result.get('results_path', '')
    sim_result.elapsed_time = result.get('elapsed_time', 0.0)
    
    # Store additional data that doesn't fit in the schema
    extra_data = {
        'notes': '',
        'peak_counts': {
            'mx': len(analysis.get('mx_peaks', [])),
            'my': len(analysis.get('my_peaks', [])),
            'mz': len(analysis.get('mz_peaks', []))
        }
    }
    sim_result.set_extra_data(extra_data)
    
    # Save to database
    db.session.add(sim_result)
    db.session.commit()
    
    # Add frequency peaks information
    save_peaks(sim_result.id, analysis, fc_analysis)
    
    # Add comb structures information
    save_combs(sim_result.id, comb_analysis, log_comb_analysis)
    
    return sim_result

def save_peaks(simulation_id, analysis, fc_analysis):
    """Save detected frequency peaks to the database."""
    # Process peaks for each component (mx, my, mz)
    for component in ['mx', 'my', 'mz']:
        peaks = analysis.get(f'{component}_peaks', [])
        amps = analysis.get(f'{component}_amplitudes', [])
        phases = analysis.get(f'{component}_phases', [])
        
        # Get information about incommensurate frequencies
        incommensurate_freqs = fc_analysis.get(f'{component}_incommensurate_freqs', [])
        
        # Get information about harmonics
        harmonic_indices = analysis.get(f'{component}_harmonic_indices', [])
        
        # Convert numpy types to Python native types
        peaks = [convert_numpy_type(p) for p in peaks]
        amps = [convert_numpy_type(a) for a in amps]
        phases = [convert_numpy_type(p) for p in phases]
        incommensurate_freqs = [convert_numpy_type(f) for f in incommensurate_freqs]
        harmonic_indices = [convert_numpy_type(i) for i in harmonic_indices]
        
        for i, freq in enumerate(peaks):
            # Only store peaks with significant amplitude
            if i < len(amps):
                # Convert to float to ensure comparison works
                amp_val = float(amps[i])
                if amp_val > 0.01:
                    phase = phases[i] if i < len(phases) else 0.0
                
                    # Check if this frequency is incommensurate
                    is_incomm = freq in incommensurate_freqs
                    
                    # Check if this frequency is a harmonic
                    is_harmonic = i in harmonic_indices
                    
                    # Create peak record
                    peak = FrequencyPeak()
                    peak.simulation_id = simulation_id
                    peak.frequency = freq
                    peak.amplitude = amp_val  # Use the converted amplitude value
                    peak.phase = phase
                    peak.component = component
                    peak.is_harmonic = is_harmonic
                    peak.is_incommensurate = is_incomm
                    db.session.add(peak)
    
    try:
        db.session.commit()
    except Exception as e:
        print(f"Error saving peaks to database: {e}")
        db.session.rollback()

def convert_numpy_type(value):
    """
    Convert numpy types to Python native types for database compatibility.
    
    Args:
        value: The value to convert
        
    Returns:
        The converted value as a Python native type
    """
    # Import numpy only if needed to avoid dependency issues
    try:
        import numpy as np
        
        # Check if value is a numpy integer type
        if hasattr(np, 'integer') and isinstance(value, np.integer):
            return int(value)
        
        # Check if value is a numpy floating point type
        if hasattr(np, 'floating') and isinstance(value, np.floating):
            return float(value)
        
        # Check if value is a numpy array
        if hasattr(np, 'ndarray') and isinstance(value, np.ndarray):
            return value.tolist()
        
        # Check if value is a numpy boolean
        if hasattr(np, 'bool_') and isinstance(value, np.bool_):
            return bool(value)
        
        # Special case for numpy scalar types
        if str(type(value)).startswith("<class 'numpy."):
            return value.item() if hasattr(value, 'item') else value
            
    except (ImportError, AttributeError):
        pass
    
    # If it's not a numpy type or numpy isn't available, return as is
    return value

def save_combs(simulation_id, comb_analysis, log_comb_analysis):
    """Save detected frequency comb structures to the database."""
    # Process linear combs
    for component in ['mx', 'mz']:
        comb_found = comb_analysis.get(f'{component}_comb_found', False)
        if comb_found:
            comb = CombStructure()
            comb.simulation_id = simulation_id
            comb.component = component
            comb.is_logarithmic = False
            
            # Convert numpy types to Python native types
            base_freq = convert_numpy_type(comb_analysis.get(f'{component}_base_freq', 0.0))
            spacing = convert_numpy_type(comb_analysis.get(f'{component}_best_omega', 0.0))
            num_teeth = convert_numpy_type(comb_analysis.get(f'{component}_num_teeth', 0))
            
            comb.base_frequency = base_freq
            comb.spacing = spacing
            comb.num_teeth = num_teeth
            
            db.session.add(comb)
    
    # Process logarithmic combs
    for component in ['mx', 'mz']:
        log_comb_found = log_comb_analysis.get(f'{component}_log_comb_found', False)
        if log_comb_found:
            log_comb = CombStructure()
            log_comb.simulation_id = simulation_id
            log_comb.component = component
            log_comb.is_logarithmic = True
            
            # Convert numpy types to Python native types
            base_freq = convert_numpy_type(log_comb_analysis.get(f'{component}_base_freq', 0.0))
            spacing = convert_numpy_type(log_comb_analysis.get(f'{component}_best_r', 0.0))
            num_teeth = convert_numpy_type(log_comb_analysis.get(f'{component}_log_num_teeth', 0))
            
            log_comb.base_frequency = base_freq
            log_comb.spacing = spacing
            log_comb.num_teeth = num_teeth
            
            db.session.add(log_comb)
    
    try:
        db.session.commit()
    except Exception as e:
        print(f"Error saving combs to database: {e}")
        db.session.rollback()

def get_recent_simulations(limit=10):
    """Get the most recent simulation results from the database."""
    return SimulationResult.query.order_by(
        SimulationResult.created_at.desc()
    ).limit(limit).all()

def get_simulation_by_id(simulation_id):
    """Get a simulation result by its database ID."""
    return SimulationResult.query.get(simulation_id)

def get_simulation_by_name(result_name):
    """Get a simulation result by its result name."""
    return SimulationResult.query.filter_by(result_name=result_name).first()

def search_simulations(circuit_type=None, min_qubits=None, max_qubits=None, 
                      time_crystal_detected=None, comb_detected=None):
    """
    Search for simulations based on filters.
    
    Args:
        circuit_type (str): Filter by circuit type
        min_qubits (int): Filter by minimum number of qubits
        max_qubits (int): Filter by maximum number of qubits
        time_crystal_detected (bool): Filter by time crystal detection
        comb_detected (bool): Filter by frequency comb detection
    
    Returns:
        list: Filtered simulation results
    """
    query = SimulationResult.query
    
    if circuit_type:
        query = query.filter(SimulationResult.circuit_type == circuit_type)
    
    if min_qubits is not None:
        query = query.filter(SimulationResult.qubits >= min_qubits)
    
    if max_qubits is not None:
        query = query.filter(SimulationResult.qubits <= max_qubits)
    
    if time_crystal_detected is not None:
        query = query.filter(SimulationResult.time_crystal_detected == time_crystal_detected)
    
    if comb_detected is not None:
        query = query.filter(
            (SimulationResult.linear_combs_detected == True) | 
            (SimulationResult.log_combs_detected == True)
        )
    
    return query.order_by(SimulationResult.created_at.desc()).all()