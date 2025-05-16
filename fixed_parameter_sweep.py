"""
Main implementation for the parameter sweep route.
This is a temporary file to fix the syntax errors in main.py.
"""

@app.route('/parameter_sweep')
@login_required
def parameter_sweep():
    """Render the parameter sweep page."""
    from sqlalchemy import func
    # Available circuit types
    circuit_types = [
        {"id": "penrose", "name": "Penrose-inspired Circuit"},
        {"id": "qft_basic", "name": "QFT Basic Circuit"},
        {"id": "comb_generator", "name": "Frequency Comb Generator"},
        {"id": "comb_twistor", "name": "Twistor-inspired Comb Circuit"},
        {"id": "graphene_fc", "name": "Graphene Lattice Circuit"},
        {"id": "string_twistor_fc", "name": "String Twistor Frequency Crystal"}
    ]
    
    # Current timestamp for default scan name
    now = datetime.datetime.now()
    
    # Get active sweep from query string if specified
    active_sweep = request.args.get('active_sweep')
    active_sweep_info = None
    
    # Check if we have an active sweep
    if active_sweep:
        # Get count of completed simulations for this sweep
        completed_count = SimulationResult.query.filter_by(sweep_session=active_sweep).count()
        
        # Get total expected simulations (fallback method)
        total_expected = 1  # This is just a fallback
        
        # Get first simulation to extract metadata
        first_sim = SimulationResult.query.filter_by(sweep_session=active_sweep).first()
        
        if first_sim:
            # Extract parameter names
            param1 = first_sim.sweep_param1
            param2 = first_sim.sweep_param2
            
            # Calculate progress
            progress = int((completed_count / total_expected) * 100) if total_expected > 0 else 0
            progress = min(progress, 100)
            
            active_sweep_info = {
                'circuit_type': first_sim.circuit_type,
                'param1': param1.replace('_', ' ').title() if param1 else None,
                'param2': param2.replace('_', ' ').title() if param2 else None,
                'completed': completed_count,
                'total': total_expected,
                'progress': progress,
                'sweep_session': active_sweep
            }
    
    # Get list of completed sweep sessions
    completed_sweeps = []
    try:
        # Get distinct sweep sessions
        sweep_query = db.session.query(
            SimulationResult.sweep_session,
            func.count(SimulationResult.id).label('count'),
            func.min(SimulationResult.created_at).label('created_at'),
            func.max(SimulationResult.circuit_type).label('circuit_type')
        ).filter(
            SimulationResult.sweep_session != None
        ).group_by(
            SimulationResult.sweep_session
        ).order_by(
            func.min(SimulationResult.created_at).desc()
        ).limit(10)
        
        sweep_sessions = sweep_query.all()
        
        # Format each sweep session for display
        for sweep_session, count, created_at, circuit_type in sweep_sessions:
            # Get the first simulation to extract parameter names
            first_sim = SimulationResult.query.filter_by(sweep_session=sweep_session).first()
            if first_sim:
                param1 = first_sim.sweep_param1
                param2 = first_sim.sweep_param2
                
                completed_sweeps.append({
                    'id': sweep_session,
                    'count': count,
                    'created_at': created_at,
                    'circuit_type': circuit_type,
                    'param1': param1.replace('_', ' ').title() if param1 else None,
                    'param2': param2.replace('_', ' ').title() if param2 else None
                })
    except Exception as e:
        print(f"Error getting completed sweeps: {str(e)}")
        traceback.print_exc()
    
    # Render the parameter sweep page
    return render_template('parameter_sweep.html', 
                           circuit_types=circuit_types, 
                           default_time=now.strftime('%Y%m%d-%H%M%S'),
                           active_sweep=active_sweep_info,
                           completed_sweeps=completed_sweeps)