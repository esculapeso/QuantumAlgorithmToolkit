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
        
        for i, freq in enumerate(peaks):
            # Only store peaks with significant amplitude
            if i < len(amps) and amps[i] > 0.01:
                phase = phases[i] if i < len(phases) else 0.0
                
                # Check if this frequency is incommensurate
                is_incomm = freq in incommensurate_freqs
                
                # Check if this frequency is a harmonic
                is_harmonic = i in harmonic_indices
                
                # Create peak record
                peak = FrequencyPeak()
                peak.simulation_id = simulation_id
                peak.frequency = freq
                peak.amplitude = amps[i]
                peak.phase = phase
                peak.component = component
                peak.is_harmonic = is_harmonic
                peak.is_incommensurate = is_incomm
                db.session.add(peak)
    
    db.session.commit()

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
            comb.base_frequency = comb_analysis.get(f'{component}_base_freq', 0.0)
            comb.spacing = comb_analysis.get(f'{component}_best_omega', 0.0)
            comb.num_teeth = comb_analysis.get(f'{component}_num_teeth', 0)
            db.session.add(comb)
    
    # Process logarithmic combs
    for component in ['mx', 'mz']:
        log_comb_found = log_comb_analysis.get(f'{component}_log_comb_found', False)
        if log_comb_found:
            log_comb = CombStructure()
            log_comb.simulation_id = simulation_id
            log_comb.component = component
            log_comb.is_logarithmic = True
            log_comb.base_frequency = log_comb_analysis.get(f'{component}_base_freq', 0.0)
            log_comb.spacing = log_comb_analysis.get(f'{component}_best_r', 0.0)
            log_comb.num_teeth = log_comb_analysis.get(f'{component}_log_num_teeth', 0)
            db.session.add(log_comb)
    
    db.session.commit()

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