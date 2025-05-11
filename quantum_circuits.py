"""
Quantum circuit generation module.
Contains functions to create different types of quantum circuits.
"""

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter
from qiskit.circuit.library import QFT
from qiskit.quantum_info import Statevector

# Define a dummy AerSimulator if the real one can't be imported
class DummyAerSimulator:
    """Fallback simulator when AerSimulator is not available"""
    def __init__(self, *args, **kwargs):
        print("WARNING: Using dummy simulator - actual quantum simulation won't work")
        self.method = kwargs.get('method', 'auto')
        self.num_qubits = 3  # Default value
        
    def run(self, *args, **kwargs):
        """Returns a dummy result"""
        from collections import namedtuple
        DummyResult = namedtuple('DummyResult', ['get_counts', 'get_statevector', 'result'])
        
        def get_counts(*args, **kwargs):
            return {'00': 50, '01': 25, '10': 25, '11': 0}
            
        def get_statevector(*args, **kwargs):
            import numpy as np
            # Return a simple superposition state
            return np.array([0.5, 0.5, 0.5, 0.5])
            
        def result(*args, **kwargs):
            # Return self to allow chained calls
            return DummyResult(get_counts=get_counts, get_statevector=get_statevector, result=result)
            
        return DummyResult(get_counts=get_counts, get_statevector=get_statevector, result=result)

# Try to import the real AerSimulator
try:
    from qiskit_aer import AerSimulator
except ImportError:
    try:
        from qiskit.providers.aer import AerSimulator
    except ImportError:
        print("WARNING: AerSimulator not found - using fallback simulator for demonstration only")
        AerSimulator = DummyAerSimulator

def create_penrose_circuit(qubits, shots, drive_steps, init_state=None, drive_param=0.9):
    """Creates a Penrose-inspired quantum circuit."""
    # Create a circuit with specified number of qubits
    qc = QuantumCircuit(qubits)
    
    # Initialize with custom state if provided
    if init_state is not None:
        if isinstance(init_state, str):
            if init_state == 'superposition':
                # Put all qubits in superposition
                for q in range(qubits):
                    qc.h(q)
            elif init_state.startswith('|'):
                # Parse a ket notation (simplified)
                try:
                    # Convert |01+-> to appropriate gates
                    state_spec = init_state.strip('|').strip('>')
                    if len(state_spec) != qubits:
                        raise ValueError(f"State spec '{state_spec}' length doesn't match qubit count {qubits}")
                    
                    for q, char in enumerate(state_spec):
                        if char == '1':
                            qc.x(q)  # |1>
                        elif char == '+':
                            qc.h(q)  # |+>
                        elif char == '-':
                            qc.x(q)
                            qc.h(q)  # |->
                        # |0> is default, no gate needed
                except Exception as e:
                    print(f"Error initializing circuit with '{init_state}': {e}")
                    # Fall back to all-zero state
    
    # Define time parameter
    t = Parameter('t')
    
    # Add drive sequence using penrose tiling inspired sequence
    for step in range(drive_steps):
        angle = t * drive_param
        phase_factor = np.pi * ((1 + np.sqrt(5))/2) * step  # Golden ratio for Penrose
        
        # Apply pattern of gates
        for q in range(qubits):
            # Alternate between X, Y rotations with penrose-inspired phases
            if (q + step) % 2 == 0:
                qc.rx(angle + phase_factor, q)
            else:
                qc.ry(angle + phase_factor, q)
            
        # Add entangling layer
        for q in range(qubits-1):
            qc.cz(q, q+1)
        # Optional: add a non-local entanglement
        if qubits > 2:
            qc.cz(0, qubits-1)  # Connect first and last qubits
    
    return qc, t

def create_qft_basic_circuit(qubits, shots, drive_steps, init_state=None, drive_param=0.9):
    """Creates a QFT-based quantum circuit."""
    # Create circuit
    qc = QuantumCircuit(qubits)
    
    # Initialize with custom state if provided
    if init_state is not None:
        if isinstance(init_state, str):
            if init_state == 'superposition':
                for q in range(qubits):
                    qc.h(q)
            # Other initializations handled as in the penrose function
    
    # Define time parameter
    t = Parameter('t')
    
    # Apply QFT-based sequence
    for step in range(drive_steps):
        angle = t * drive_param
        
        # Apply rotations
        for q in range(qubits):
            phase_factor = np.pi * step / (q+1)  # Frequency depends on qubit index
            qc.rx(angle + phase_factor, q)
        
        # Apply partial QFT
        if step % 2 == 0 and qubits > 1:
            # Add QFT on a subset of qubits
            qft_size = min(3, qubits)  # Limit QFT size for larger circuits
            qft_start = (step // 2) % (qubits - qft_size + 1)  # Cycle through positions
            
            # Custom QFT implementation for partial register
            for i in range(qft_size):
                q1 = qft_start + i
                qc.h(q1)
                for j in range(i+1, qft_size):
                    q2 = qft_start + j
                    qc.cp(np.pi/(2**(j-i)), q1, q2)
        
        # Add entangling layer
        for q in range(qubits-1):
            qc.cz(q, q+1)
    
    return qc, t

def create_comb_generator_circuit(qubits, shots, drive_steps, init_state=None, drive_param=0.9):
    """Creates a circuit designed to generate frequency combs."""
    # Create circuit
    qc = QuantumCircuit(qubits)
    
    # Initialize with custom state if provided
    if init_state is not None:
        if isinstance(init_state, str):
            if init_state == 'superposition':
                for q in range(qubits):
                    qc.h(q)
            # Other initializations handled as in previous functions
    
    # Define time parameter
    t = Parameter('t')
    
    # Create frequency comb circuit
    for step in range(drive_steps):
        angle = t * drive_param
        
        # Base frequencies for each qubit - establishing the "teeth" of the comb
        for q in range(qubits):
            # Each qubit gets a different base frequency
            base_freq = np.pi * (q+1) / qubits
            qc.rx(angle * base_freq, q)
        
        # Entangle to create interference
        for q in range(qubits-1):
            qc.cx(q, q+1)
        
        # Apply rotation layer with harmonics
        for q in range(qubits):
            harmonic = np.pi * (step+1) / (drive_steps/2)
            qc.ry(angle * harmonic, q)
        
        # Connect first and last qubits to create circular boundary condition
        if qubits > 2:
            qc.cx(qubits-1, 0)
    
    return qc, t

def create_comb_twistor_circuit(qubits, shots, drive_steps, init_state=None, drive_param=0.9):
    """Creates a circuit with twistor-inspired comb generation."""
    # Create circuit
    qc = QuantumCircuit(qubits)
    
    # Initialize with custom state if provided
    if init_state is not None:
        if isinstance(init_state, str):
            if init_state == 'superposition':
                for q in range(qubits):
                    qc.h(q)
            # Other initializations handled as in previous functions
    
    # Define time parameter
    t = Parameter('t')
    
    # Twistor-inspired sequence
    for step in range(drive_steps):
        angle = t * drive_param
        
        # Phase factors inspired by twistor diagrams
        for q in range(qubits):
            # Create a twisting pattern of phases
            twist_factor = np.pi * ((q+1) * (step+1)) / (qubits * drive_steps)
            qc.rx(angle + twist_factor, q)
            qc.rz(angle * twist_factor, q)
        
        # Create entanglement pattern resembling a twistor diagram
        for q in range(qubits-1):
            qc.cx(q, q+1)
        
        # Add long-range connections in a twisting pattern
        if qubits > 3:
            twist_target = (step % (qubits-1))
            qc.cx(0, twist_target+1)  # Connect qubit 0 to a cycling target
    
    return qc, t

def create_graphene_fc_circuit(qubits, shots, drive_steps, init_state=None, drive_param=0.9):
    """Creates a circuit inspired by graphene lattice for frequency crystal generation."""
    if qubits < 6:
        print(f"Warning: Graphene circuit works best with at least 6 qubits. Using {qubits} qubits.")
    
    # Create circuit
    qc = QuantumCircuit(qubits)
    
    # Initialize with custom state if provided
    if init_state is not None:
        if isinstance(init_state, str):
            if init_state == 'superposition':
                for q in range(qubits):
                    qc.h(q)
            # Other initializations handled as in previous functions
    
    # Define time parameter
    t = Parameter('t')
    
    # Set up a virtual adjacency matrix similar to graphene hexagonal lattice
    # We'll map it to our linear qubit array
    adjacency = []
    
    # Create a simplified graphene-like pattern mapped to linear array
    # In real graphene, each carbon atom connects to 3 neighbors
    for q in range(qubits):
        connections = []
        # Direct neighbor connections
        if q > 0:
            connections.append(q-1)  # left neighbor
        if q < qubits-1:
            connections.append(q+1)  # right neighbor
            
        # Add one "out of plane" connection to simulate 3rd graphene connection
        # Use a pattern that doesn't create too many overlapping connections
        jump = max(2, qubits // 3)
        third = (q + jump) % qubits
        if third != q and third not in connections:
            connections.append(third)
            
        adjacency.append(connections)
    
    # Build circuit based on graphene-like structure
    for step in range(drive_steps):
        angle = t * drive_param
        
        # Individual rotations with phase factors
        for q in range(qubits):
            # Use a phase pattern inspired by electronic properties of graphene
            phase_factor = np.pi * ((q % 2) + 1) * ((step % 3) + 1) / 3
            qc.rx(angle * phase_factor, q)
            qc.rz(angle / (phase_factor + 0.5), q)  # Add asymmetry
        
        # Apply entanglement based on our graphene-inspired adjacency map
        # We'll cycle through connections to avoid too deep circuits
        cycle_index = step % 3  # Use 3 cycles to cover all possible connections
        
        for q in range(qubits):
            # Get the connections for this qubit
            q_connections = adjacency[q]
            if not q_connections:
                continue
                
            # Choose one connection based on the current cycle
            target = q_connections[cycle_index % len(q_connections)]
            
            # Only apply if q < target to avoid applying the same gate twice
            if q < target:
                qc.cz(q, target)
                
        # Add a layer of single-qubit phase gates to all qubits
        for q in range(qubits):
            k = (q + step) % qubits
            qc.p(angle * (k+1)/qubits, q)
    
    return qc, t

def get_circuit_generator(circuit_type):
    """Returns the appropriate circuit generator function based on the circuit type."""
    circuit_generators = {
        'penrose': create_penrose_circuit,
        'qft_basic': create_qft_basic_circuit,
        'comb_generator': create_comb_generator_circuit,
        'comb_twistor': create_comb_twistor_circuit,
        'graphene_fc': create_graphene_fc_circuit
    }
    
    if circuit_type not in circuit_generators:
        raise ValueError(f"Unknown circuit type: {circuit_type}. Supported types: {', '.join(circuit_generators.keys())}")
    
    return circuit_generators[circuit_type]
