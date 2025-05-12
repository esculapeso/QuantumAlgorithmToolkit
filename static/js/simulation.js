document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('#simulation-form');
    if (!form) return;
    
    const progressSection = document.getElementById('simulation-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const progressDetail = document.getElementById('progress-detail');
    const runButton = document.getElementById('run-sim-button');
    
    let simulationId = null;
    let checkInterval = null;
    
    form.addEventListener('submit', function(e) {
        // Check if this is a large simulation
        const qubits = parseInt(document.getElementById('qubits').value);
        const timePoints = parseInt(document.getElementById('time_points').value);
        
        if (qubits > 3 || timePoints > 100) {
            e.preventDefault();
            
            // Show progress section
            progressSection.classList.remove('d-none');
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            progressDetail.textContent = 'Initializing simulation...';
            runButton.disabled = true;
            
            // Get form data
            const formData = new FormData(form);
            
            // Send AJAX request
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                // Always check content type first
                const contentType = response.headers.get('content-type');
                
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                
                if (!contentType || !contentType.includes('application/json')) {
                    // Handle HTML response - likely a server error or timeout
                    return response.text().then(text => {
                        throw new Error('Server returned HTML instead of JSON. For very large simulations, please run with fewer time points or check the Simulations page for background jobs.');
                    });
                }
                
                return response.json();
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
                checkInterval = setInterval(checkProgress, 1000);
            })
            .catch(error => {
                console.error('Simulation error:', error);
                progressStatus.textContent = 'Error';
                progressDetail.textContent = 'Failed to start simulation: ' + error.message;
                progressSection.classList.remove('alert-info');
                progressSection.classList.add('alert-danger');
                runButton.disabled = false;
                
                // If very large simulation, suggest alternatives
                if (timePoints > 500) {
                    progressDetail.innerHTML = progressDetail.textContent + 
                        '<br><br>Recommendation: Try with fewer time points or check the <a href="/simulations">Simulations</a> page for any background jobs.';
                }
            });
        }
    });
    
    function checkProgress() {
        if (!simulationId) return;
        
        fetch(`/simulation_status/${simulationId}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            // Always check content type first
            const contentType = response.headers.get('content-type');
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            
            if (!contentType || !contentType.includes('application/json')) {
                // Handle HTML response - likely a server error
                return response.text().then(text => {
                    throw new Error('Server returned HTML instead of JSON. Please check the Simulations page for your job status.');
                });
            }
            
            return response.json();
        })
        .then(data => {
            if (data.error) {
                clearInterval(checkInterval);
                progressStatus.textContent = 'Error';
                progressDetail.textContent = data.error;
                progressSection.classList.remove('alert-info');
                progressSection.classList.add('alert-danger');
                runButton.disabled = false;
                return;
            }
            
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
            }
        })
        .catch(error => {
            console.error('Error checking status:', error);
            
            // Only show a UI error if we haven't already
            if (progressSection.classList.contains('alert-info')) {
                clearInterval(checkInterval);
                progressStatus.textContent = 'Error';
                progressDetail.textContent = 'Failed to check simulation status: ' + error.message;
                progressDetail.innerHTML += '<br><br>You can check the <a href="/simulations">Simulations</a> page to see if your job is still running.';
                progressSection.classList.remove('alert-info');
                progressSection.classList.add('alert-danger');
                runButton.disabled = false;
            }
        });
    }
});