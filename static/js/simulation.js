document.addEventListener('DOMContentLoaded', function() {
    // Enable auto-refresh on simulations page to see new completed simulations
    initSimulationsPageAutoRefresh();
    
    // Initialize parameter sweep UI interactions
    initParameterSweepUI();
    
    // Initialize form handling for simulation form
    const form = document.querySelector('#simulation-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // For large simulations, show a message
            const qubits = parseInt(document.getElementById('qubits').value);
            const timePoints = parseInt(document.getElementById('time_points').value);
            
            if (qubits > 3 || timePoints > 100) {
                // Show a tooltip that this will take longer
                const infoBox = document.createElement('div');
                infoBox.className = 'alert alert-info mt-3';
                infoBox.innerHTML = '<strong>Running larger simulation...</strong> This may take some time to complete. ' +
                    'For very large simulations, you\'ll be redirected to the Simulations page where you can track progress.';
                
                // Add the info box after the form
                form.parentNode.appendChild(infoBox);
                
                // If extremely large, give additional warning
                if (qubits > 6 || timePoints > 500) {
                    const warningBox = document.createElement('div');
                    warningBox.className = 'alert alert-warning mt-1';
                    warningBox.innerHTML = '<strong>Note:</strong> Very large simulations may take several minutes to complete. ' +
                        'Each simulation will appear in the "Completed Simulations" list when it finishes.';
                    
                    // Add the warning box after the info box
                    form.parentNode.appendChild(warningBox);
                }
            }
        });
    }
    
    // Function to handle auto-refresh on the simulations page
    function initSimulationsPageAutoRefresh() {
        // Check if we're on the simulations page
        if (!window.location.pathname.includes('/simulations')) return;
        
        // Check if there are any simulations in the table
        const simTable = document.querySelector('.table.table-striped');
        if (!simTable) return;
        
        // Auto-refresh every 10 seconds to see new completed simulations
        setTimeout(function() {
            // Refresh the page with current URL parameters
            window.location.reload();
        }, 10000); // 10 seconds
    }
    
    // Function to initialize parameter sweep UI
    function initParameterSweepUI() {
        // Find all the sweep toggle checkboxes
        const sweepToggles = document.querySelectorAll('input[type="checkbox"][id^="sweep_"]');
        
        // Add event listeners to all sweep toggles
        sweepToggles.forEach(toggle => {
            toggle.addEventListener('change', function() {
                // Get the parameter name from the toggle ID
                const paramName = this.id.replace('sweep_', '');
                
                // Find the min, max, and steps inputs for this parameter
                const minInput = document.getElementById(`${paramName}_min`);
                const maxInput = document.getElementById(`${paramName}_max`);
                const stepsInput = document.getElementById(`${paramName}_steps`);
                const rangeControls = document.getElementById(`${paramName}_range_controls`);
                
                if (minInput && maxInput && stepsInput && rangeControls) {
                    // Show or hide the range controls based on the toggle state
                    if (this.checked) {
                        rangeControls.classList.remove('d-none');
                    } else {
                        rangeControls.classList.add('d-none');
                    }
                }
            });
        });
    }
});