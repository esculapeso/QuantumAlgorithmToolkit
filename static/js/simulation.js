/**
 * JavaScript functions for the simulation interface
 */

// Global variables
let simulationId = null;
let checkInterval = null;

/**
 * Handle the form submission for starting a new simulation
 */
function handleSimulationFormSubmit(event, form, progressSection, progressBar, progressStatus, progressDetail, runButton) {
    event.preventDefault();
    
    // Show progress section
    progressSection.classList.remove('d-none');
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressDetail.textContent = 'Initializing simulation...';
    runButton.disabled = true;
    
    // Get form data
    const formData = new FormData(form);
    
    // Check if time points exceeds 300
    const timePoints = parseInt(formData.get('time_points'), 10);
    if (timePoints > 300) {
        progressDetail.textContent = 'Starting long-running simulation in the background...';
    }
    
    // Send AJAX request
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        
        return response.json().catch(error => {
            // Handle JSON parsing errors (e.g., if server returned HTML instead of JSON)
            console.error("Failed to parse JSON response:", error);
            throw new Error("The server returned an invalid response format. Try reducing the number of time points.");
        });
    })
    .then(data => {
        if (data.error) {
            progressStatus.textContent = 'Error';
            progressDetail.textContent = data.error;
            progressSection.classList.remove('alert-info');
            progressSection.classList.add('alert-danger');
            runButton.disabled = false;
            return;
        }
        
        simulationId = data.simulation_id;
        
        // Start checking progress
        checkInterval = setInterval(() => checkProgress(
            simulationId, 
            progressBar, 
            progressStatus, 
            progressDetail, 
            progressSection, 
            runButton
        ), 1000);
    })
    .catch(error => {
        console.error('Simulation error:', error);
        progressStatus.textContent = 'Error';
        progressDetail.textContent = 'Failed to start simulation: ' + error.message;
        progressSection.classList.remove('alert-info');
        progressSection.classList.add('alert-danger');
        runButton.disabled = false;
    });
}

/**
 * Check the progress of a running simulation
 */
function checkProgress(simulationId, progressBar, progressStatus, progressDetail, progressSection, runButton) {
    if (!simulationId) return;
    
    fetch(`/simulation_status/${simulationId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            
            return response.json().catch(error => {
                // Handle JSON parsing errors
                console.error("Failed to parse JSON from status endpoint:", error);
                throw new Error("The server returned an invalid response format.");
            });
        })
        .then(data => {
            // Update progress information
            if (data.status === 'completed') {
                clearInterval(checkInterval);
                progressBar.style.width = '100%';
                progressBar.textContent = '100%';
                progressStatus.textContent = 'Simulation Complete!';
                progressDetail.textContent = data.message || 'Redirecting to results...';
                
                // Redirect to result page
                if (data.result_path) {
                    setTimeout(() => {
                        window.location.href = `/result/${data.result_path}`;
                    }, 1000);
                } else {
                    runButton.disabled = false;
                }
            } else if (data.status === 'running' || data.status === 'starting') {
                const progress = data.progress || 0;
                progressBar.style.width = `${progress}%`;
                progressBar.textContent = `${progress}%`;
                progressDetail.textContent = data.message || `Processing: ${progress}% complete`;
            } else if (data.status === 'error') {
                clearInterval(checkInterval);
                progressBar.style.width = '100%';
                progressStatus.textContent = 'Error';
                progressDetail.textContent = data.error || 'An unknown error occurred';
                progressSection.classList.remove('alert-info');
                progressSection.classList.add('alert-danger');
                runButton.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
            
            // Only show a UI error if we haven't already
            if (progressSection.classList.contains('alert-info')) {
                clearInterval(checkInterval);
                progressStatus.textContent = 'Error';
                progressDetail.textContent = 'Failed to check simulation status: ' + error.message;
                progressSection.classList.remove('alert-info');
                progressSection.classList.add('alert-danger');
                runButton.disabled = false;
            }
        });
}