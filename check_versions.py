"""Script to check library versions."""

try:
    import qiskit
    print(f'Qiskit version: {qiskit.__version__}')
except ImportError:
    print("Qiskit not found")

try:
    import qiskit_aer
    print(f'Qiskit-Aer version: {qiskit_aer.__version__}')
except ImportError:
    print("Qiskit-Aer not found")

try:
    import pylatexenc
    print(f'PyLatexEnc version: {pylatexenc.__version__}')
except ImportError:
    print("PyLatexEnc not found")

try:
    import pywt
    print(f'PyWavelets version: {pywt.__version__}')
except ImportError:
    print("PyWavelets not found")