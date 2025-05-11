"""
Analysis module for quantum simulation results.
Contains functions for FFT analysis and frequency comb detection.
"""

import numpy as np
from scipy import signal
from fractions import Fraction

# Try to import pywt but continue if not available
try:
    import pywt
    PYWT_AVAILABLE = True
except ImportError:
    print("WARNING: PyWavelets not available, some features will be limited")
    PYWT_AVAILABLE = False

from utils import is_harmonic_related
import config

def run_expectation_and_fft_analysis(expectation_values, times, drive_freq, fs=None, num_fft_bins=None):
    """
    Runs FFT analysis on expectation values.
    """
    analysis = {
        'drive_frequency': drive_freq,
        'has_subharmonics': False,
        'primary_mx_freq': 0.0,
        'primary_mz_freq': 0.0,
        'fft_bins': num_fft_bins,
        'sampling_freq': fs
    }
    
    # Extract values from expectation_values dictionary
    times_array = np.array(times)
    mx_values = np.array(expectation_values['mx'])
    my_values = np.array(expectation_values['my'])
    mz_values = np.array(expectation_values['mz'])
    
    # Sampling rate and FFT parameters
    if fs is None:
        if len(times_array) > 1:
            # Calculate from time points
            fs = 1 / (times_array[1] - times_array[0])
        else:
            # Default fallback
            fs = 100.0
    
    analysis['sampling_freq'] = fs
    
    # Calculate FFT size
    if num_fft_bins is None:
        # Use power of 2 for efficiency
        num_fft_bins = 2 ** int(np.ceil(np.log2(len(times_array))))
    
    analysis['fft_bins'] = num_fft_bins
    
    # Apply window function to reduce spectral leakage
    window = signal.windows.hann(len(times_array))
    
    # Calculate FFT for each component
    # NOTE: We use real FFT for real-valued signals
    mx_fft = np.fft.rfft(mx_values * window, n=num_fft_bins)
    my_fft = np.fft.rfft(my_values * window, n=num_fft_bins)
    mz_fft = np.fft.rfft(mz_values * window, n=num_fft_bins)
    
    # Calculate frequency bins
    freq_bins = np.fft.rfftfreq(num_fft_bins, d=1/fs)
    
    # Store complex FFT results for later phase analysis
    analysis['mx_fft_complex_pos'] = mx_fft
    analysis['my_fft_complex_pos'] = my_fft
    analysis['mz_fft_complex_pos'] = mz_fft
    analysis['positive_frequencies'] = freq_bins
    
    # Calculate amplitudes (normalized)
    mx_fft_amp = np.abs(mx_fft) / (len(times_array)/2)
    my_fft_amp = np.abs(my_fft) / (len(times_array)/2)
    mz_fft_amp = np.abs(mz_fft) / (len(times_array)/2)
    
    # Store FFT amplitude data
    analysis['mx_fft_pos'] = mx_fft_amp
    analysis['my_fft_pos'] = my_fft_amp
    analysis['mz_fft_pos'] = mz_fft_amp
    
    # Find prominent peaks in FFT
    # (Adjust parameters as needed based on typical signal characteristics)
    min_peak_height = 0.05  # Minimum normalized height to be considered a peak
    min_peak_distance = max(3, int(len(freq_bins) / 100))  # Minimum samples between peaks
    
    try:
        # Find peaks for each component
        mx_peaks_indices, _ = signal.find_peaks(mx_fft_amp, height=min_peak_height, distance=min_peak_distance)
        my_peaks_indices, _ = signal.find_peaks(my_fft_amp, height=min_peak_height, distance=min_peak_distance)
        mz_peaks_indices, _ = signal.find_peaks(mz_fft_amp, height=min_peak_height, distance=min_peak_distance)
        
        # Store peak data
        analysis['mx_peaks_indices'] = mx_peaks_indices
        analysis['my_peaks_indices'] = my_peaks_indices
        analysis['mz_peaks_indices'] = mz_peaks_indices
        
        # Analyze for primary frequencies and subharmonics
        # We focus on the strongest peaks that aren't DC (zero frequency)
        
        if len(mx_peaks_indices) > 0:
            # Remove DC component if it's the first peak
            mx_filtered_indices = mx_peaks_indices[freq_bins[mx_peaks_indices] > 0.01]
            
            if len(mx_filtered_indices) > 0:
                # Find the tallest peak
                strongest_idx = mx_filtered_indices[np.argmax(mx_fft_amp[mx_filtered_indices])]
                primary_mx_freq = freq_bins[strongest_idx]
                primary_mx_amp = mx_fft_amp[strongest_idx]
                
                analysis['primary_mx_freq'] = primary_mx_freq
                analysis['primary_mx_amp'] = primary_mx_amp
                
                # Check if the strongest frequency is a subharmonic of the drive
                is_related, relation = is_harmonic_related(
                    primary_mx_freq, drive_freq, 
                    tolerance=config.DEFAULT_HARMONIC_TOLERANCE
                )
                
                if is_related and '/' in relation:
                    analysis['has_subharmonics'] = True
                    analysis['mx_harmonic_relation'] = relation
        
        if len(mz_peaks_indices) > 0:
            # Remove DC component if it's the first peak
            mz_filtered_indices = mz_peaks_indices[freq_bins[mz_peaks_indices] > 0.01]
            
            if len(mz_filtered_indices) > 0:
                # Find the tallest peak
                strongest_idx = mz_filtered_indices[np.argmax(mz_fft_amp[mz_filtered_indices])]
                primary_mz_freq = freq_bins[strongest_idx]
                primary_mz_amp = mz_fft_amp[strongest_idx]
                
                analysis['primary_mz_freq'] = primary_mz_freq
                analysis['primary_mz_amp'] = primary_mz_amp
                
                # Check if the strongest frequency is a subharmonic of the drive
                is_related, relation = is_harmonic_related(
                    primary_mz_freq, drive_freq, 
                    tolerance=config.DEFAULT_HARMONIC_TOLERANCE
                )
                
                if is_related and '/' in relation:
                    analysis['has_subharmonics'] = True
                    analysis['mz_harmonic_relation'] = relation
    
    except Exception as e:
        print(f"Error during peak finding: {e}")
        # Continue with analysis even if peak finding fails
    
    return analysis

def analyze_fft_peaks_for_fc(analysis,
                             peak_height_threshold=config.DEFAULT_PEAK_HEIGHT_THRESHOLD,
                             max_rational_denominator=config.DEFAULT_MAX_RATIONAL_DENOMINATOR,
                             rational_tolerance=config.DEFAULT_RATIONAL_TOLERANCE,
                             harmonic_tolerance=config.DEFAULT_HARMONIC_TOLERANCE):
    """Analyzes FFT peaks to identify potentially incommensurate frequencies."""
    potential_fc_peaks = []
    incommensurate_peak_count = 0
    strongest_incommensurate_peak = None
    max_incommensurate_amp = 0
    
    drive_freq = analysis.get('drive_frequency', 0)
    if drive_freq <= 1e-9:
        return {
            'potential_fc_peaks': [],
            'incommensurate_peak_count': 0,
            'strongest_incommensurate_peak': None
        }
    
    pos_freqs = analysis.get('positive_frequencies', np.array([]))
    mx_fft_pos_amp = analysis.get('mx_fft_pos', np.array([]))
    mz_fft_pos_amp = analysis.get('mz_fft_pos', np.array([]))
    
    if pos_freqs.size == 0 or mx_fft_pos_amp.size == 0 or mz_fft_pos_amp.size == 0:
        return {
            'potential_fc_peaks': [],
            'incommensurate_peak_count': 0,
            'strongest_incommensurate_peak': None
        }
    
    try:
        fft_len = len(pos_freqs)
        distance = max(3, int(fft_len / 200))
        mx_peaks_indices = signal.find_peaks(mx_fft_pos_amp, height=peak_height_threshold, distance=distance)[0]
        mz_peaks_indices = signal.find_peaks(mz_fft_pos_amp, height=peak_height_threshold, distance=distance)[0]
    except Exception as e:
        print(f"Warning [analyze_fft_peaks_for_fc]: Error finding peaks: {e}")
        return {
            'potential_fc_peaks': [],
            'incommensurate_peak_count': 0,
            'strongest_incommensurate_peak': None
        }
    
    all_peaks_data = {}
    for idx in mx_peaks_indices:
        freq = pos_freqs[idx]
        amp = mx_fft_pos_amp[idx]
        if freq not in all_peaks_data or amp > all_peaks_data[freq]['amplitude']:
            all_peaks_data[freq] = {'frequency': freq, 'amplitude': amp, 'basis': 'Mx'}
    
    for idx in mz_peaks_indices:
        freq = pos_freqs[idx]
        amp = mz_fft_pos_amp[idx]
        if freq not in all_peaks_data or amp > all_peaks_data[freq]['amplitude']:
            all_peaks_data[freq] = {'frequency': freq, 'amplitude': amp, 'basis': 'Mz'}
    
    for freq, peak_data in all_peaks_data.items():
        is_related, relation = is_harmonic_related(freq, drive_freq, tolerance=harmonic_tolerance)
        if not is_related:
            ratio_to_drive = freq / drive_freq
            is_potentially_incommensurate = True
            try:
                frac = Fraction(ratio_to_drive).limit_denominator(max_rational_denominator)
                if abs(ratio_to_drive - float(frac)) < rational_tolerance:
                    is_potentially_incommensurate = False
                    relation = f"~drive*{frac.numerator}/{frac.denominator}"
            except (ValueError, OverflowError):
                pass  # Keep True if error
            
            peak_info = {
                'frequency': freq,
                'amplitude': peak_data['amplitude'],
                'basis': peak_data['basis'],
                'ratio_to_drive': ratio_to_drive,
                'relation_guess': relation,
                'is_potentially_incommensurate': is_potentially_incommensurate
            }
            potential_fc_peaks.append(peak_info)
            
            if is_potentially_incommensurate:
                incommensurate_peak_count += 1
                if peak_data['amplitude'] > max_incommensurate_amp:
                    max_incommensurate_amp = peak_data['amplitude']
                    strongest_incommensurate_peak = peak_info
    
    return {
        'potential_fc_peaks': potential_fc_peaks,
        'incommensurate_peak_count': incommensurate_peak_count,
        'strongest_incommensurate_peak': strongest_incommensurate_peak
    }

def analyze_frequency_comb(analysis, fc_fft_analysis,
                           min_omega_cand_amp=config.DEFAULT_MIN_OMEGA_CAND_AMP,
                           min_comb_teeth=config.DEFAULT_MIN_COMB_TEETH,
                           freq_tolerance_factor=config.DEFAULT_FREQ_TOLERANCE_FACTOR,
                           max_amp_rel_std_dev=config.DEFAULT_MAX_AMP_REL_STD_DEV,
                           max_phase_step_std_dev=config.DEFAULT_MAX_PHASE_STEP_STD_DEV):
    """
    Analyzes complex FFT data for LINEAR frequency comb structures (constant spacing).
    """
    results = {
        'mx_comb_found': False, 'mx_best_omega': 0, 'mx_mean_theta': 0,
        'mx_amp_rel_std_dev': float('inf'), 'mx_phase_step_std_dev': float('inf'),
        'mx_best_comb_score': float('inf'), 'mx_num_teeth': 0,
        'mx_omega_dev': float('inf'),  # Initialize Omega deviation for Mx
        'mx_comb_freqs': [], 'mx_comb_details': [],
        'mz_comb_found': False, 'mz_best_omega': 0, 'mz_mean_theta': 0,
        'mz_amp_rel_std_dev': float('inf'), 'mz_phase_step_std_dev': float('inf'),
        'mz_best_comb_score': float('inf'), 'mz_num_teeth': 0,
        'mz_omega_dev': float('inf'),  # Initialize Omega deviation for Mz
        'mz_comb_freqs': [], 'mz_comb_details': [],
    }

    # --- Get necessary data from analysis dictionaries ---
    pos_freqs = analysis.get('positive_frequencies')
    mx_fft_complex = analysis.get('mx_fft_complex_pos')
    mz_fft_complex = analysis.get('mz_fft_complex_pos')

    if pos_freqs is None or mx_fft_complex is None or mz_fft_complex is None or pos_freqs.size == 0:
        print("Warning [analyze_frequency_comb]: Missing complex FFT data or frequencies.")
        return results

    # --- Helper function to find nearest index ---
    def find_nearest_index(array, value):
        idx = np.searchsorted(array, value, side="left")
        return idx-1 if idx > 0 and (idx == len(array) or abs(value - array[idx-1]) < abs(value - array[idx])) else idx

    # --- Analyze for combs in Mx and Mz separately ---
    for basis, fft_complex in [('mx', mx_fft_complex), ('mz', mz_fft_complex)]:
        best_comb_score_found = float('inf')  # Use a separate variable to track the best score found *during* the loop for this basis

        # Get significant peak indices and frequencies for this basis
        peak_indices_key = f'{basis}_peaks_indices'
        significant_peak_indices = analysis.get(peak_indices_key, np.array([]))
        if significant_peak_indices.size == 0:
            continue  # Skip if no peaks found

        significant_peak_freqs = pos_freqs[significant_peak_indices]
        # Amplitudes corresponding to these peaks (using normalized amplitude from analysis['mx_fft_pos'])
        amp_key = f'{basis}_fft_pos'
        significant_peak_amps = analysis.get(amp_key, np.array([]))[significant_peak_indices]

        # --- Identify candidate Omegas from ALL significant peaks above threshold ---
        candidate_omegas = []
        if significant_peak_freqs.size > 0 and significant_peak_amps.size == significant_peak_freqs.size:
            # Filter peaks by minimum amplitude threshold
            valid_omega_indices = np.where(significant_peak_amps >= min_omega_cand_amp)[0]
            if valid_omega_indices.size > 0:
                # Use frequencies of these peaks as candidates, sorted by amplitude
                candidate_freqs = significant_peak_freqs[valid_omega_indices]
                candidate_amps = significant_peak_amps[valid_omega_indices]
                # Sort candidates by amplitude, descending
                sorted_cand_indices = np.argsort(candidate_amps)[::-1]
                candidate_omegas = candidate_freqs[sorted_cand_indices]

        if len(candidate_omegas) == 0:
            continue  # Cannot proceed without candidate Omegas for this basis

        # --- Analyze the frequency content to search for combs ---
        # Linear relationship first (constant Omega spacing)
        for omega_candidate in candidate_omegas:
            if omega_candidate <= 0:
                continue  # Skip any zero or negative candidates

            # Calculate comb tooth frequencies
            # Start from first tooth to a reasonable upper limit
            max_teeth = min(25, int(pos_freqs[-1] / omega_candidate) + 1)
            if max_teeth < min_comb_teeth:
                continue  # Skip if we can't even fit minimum teeth
                
            comb_freqs = np.array([n * omega_candidate for n in range(1, max_teeth + 1)])
            
            # Limit to frequencies within our analyzed range
            valid_teeth_mask = (comb_freqs <= pos_freqs[-1])
            if np.sum(valid_teeth_mask) < min_comb_teeth:
                continue  # Skip if we don't have enough teeth
                
            valid_comb_freqs = comb_freqs[valid_teeth_mask]
            
            # Find the actual FFT values at these frequencies
            comb_indices = []
            comb_details = []
            
            for freq in valid_comb_freqs:
                # Get the nearest index in our frequency array
                idx = find_nearest_index(pos_freqs, freq)
                
                # Check if this frequency is close enough to a comb tooth location
                freq_diff = abs(pos_freqs[idx] - freq)
                freq_diff_rel = freq_diff / freq if freq > 0 else 0
                
                if freq_diff_rel <= freq_tolerance_factor:
                    # This is a good approximation of a comb tooth
                    complex_val = fft_complex[idx]
                    amp = np.abs(complex_val) / (len(pos_freqs)/2)  # Normalize
                    phase = np.angle(complex_val)
                    
                    # Store the tooth information
                    tooth_num = np.where(valid_comb_freqs == freq)[0][0] + 1  # 1-based tooth number
                    comb_indices.append(idx)
                    
                    comb_details.append({
                        'freq': pos_freqs[idx],
                        'expected_freq': freq,
                        'tooth_number': tooth_num,
                        'freq_error': freq_diff,
                        'freq_error_rel': freq_diff_rel,
                        'amplitude': amp,
                        'phase': phase
                    })
            
            # We need a minimum number of teeth to consider this a valid comb
            if len(comb_indices) < min_comb_teeth:
                continue
                
            # Calculate comb quality metrics
            comb_amps = np.array([detail['amplitude'] for detail in comb_details])
            comb_phases = np.array([detail['phase'] for detail in comb_details])
            comb_teeth_nums = np.array([detail['tooth_number'] for detail in comb_details])
            
            # Amplitude consistency check
            # We expect amplitudes to vary but not wildly
            amp_rel_std_dev = np.std(comb_amps) / np.mean(comb_amps) if np.mean(comb_amps) > 0 else float('inf')
            
            # Phase relationship check
            # In an ideal frequency comb, the phase should have a linear relationship with frequency
            # Calculate phase steps between consecutive teeth
            phase_steps = []
            for i in range(len(comb_teeth_nums) - 1):
                if comb_teeth_nums[i+1] == comb_teeth_nums[i] + 1:  # Only if consecutive teeth
                    # Wrap phase difference to [-pi, pi]
                    phase_diff = (comb_phases[i+1] - comb_phases[i]) % (2*np.pi)
                    if phase_diff > np.pi:
                        phase_diff -= 2*np.pi
                    phase_steps.append(phase_diff)
            
            # Calculate variability in phase steps
            phase_step_std_dev = np.std(phase_steps) if len(phase_steps) > 1 else 0
            
            # Score this comb (lower is better)
            comb_score = amp_rel_std_dev + phase_step_std_dev
            
            # Calculate Omega (frequency spacing) deviation
            omega_deviations = []
            for i in range(len(comb_teeth_nums) - 1):
                if comb_teeth_nums[i+1] == comb_teeth_nums[i] + 1:  # Only if consecutive teeth
                    obs_spacing = comb_details[i+1]['freq'] - comb_details[i]['freq']
                    expected_spacing = omega_candidate
                    rel_dev = abs(obs_spacing - expected_spacing) / expected_spacing
                    omega_deviations.append(rel_dev)
            
            omega_dev = np.mean(omega_deviations) if omega_deviations else float('inf')
            
            # Get the mean phase of all teeth as representative
            mean_phase = np.mean(comb_phases)
            
            # Check if this is the best comb so far for this basis
            if comb_score < best_comb_score_found:
                best_comb_score_found = comb_score
                
                # Store detailed results
                results[f'{basis}_comb_found'] = True
                results[f'{basis}_best_omega'] = omega_candidate
                results[f'{basis}_num_teeth'] = len(comb_indices)
                results[f'{basis}_amp_rel_std_dev'] = amp_rel_std_dev
                results[f'{basis}_phase_step_std_dev'] = phase_step_std_dev
                results[f'{basis}_best_comb_score'] = comb_score
                results[f'{basis}_mean_theta'] = mean_phase
                results[f'{basis}_comb_freqs'] = valid_comb_freqs[:len(comb_indices)]
                results[f'{basis}_comb_details'] = comb_details
                results[f'{basis}_omega_dev'] = omega_dev

    return results

def analyze_log_frequency_comb(analysis, min_r_factor=1.2, max_r_factor=3.0, r_step=0.02,
                           min_comb_teeth=3, freq_tolerance_factor=0.1, min_peak_amp=0.1):
    """
    Analyzes for LOGARITHMIC frequency combs (where ratio between adjacent teeth is constant).
    """
    results = {
        'mx_log_comb_found': False, 'mx_best_r': 0, 'mx_base_freq': 0,
        'mx_log_comb_score': float('inf'), 'mx_log_num_teeth': 0,
        'mx_log_comb_teeth': [],
        
        'mz_log_comb_found': False, 'mz_best_r': 0, 'mz_base_freq': 0,
        'mz_log_comb_score': float('inf'), 'mz_log_num_teeth': 0,
        'mz_log_comb_teeth': []
    }
    
    # --- Get necessary data from analysis dictionaries ---
    pos_freqs = analysis.get('positive_frequencies')
    mx_fft_amp = analysis.get('mx_fft_pos')
    mz_fft_amp = analysis.get('mz_fft_pos')
    
    if pos_freqs is None or mx_fft_amp is None or mz_fft_amp is None or pos_freqs.size == 0:
        print("Warning [analyze_log_frequency_comb]: Missing FFT data or frequencies.")
        return results
    
    # --- Helper function to find nearest index ---
    def find_nearest_index(array, value):
        idx = np.searchsorted(array, value, side="left")
        return idx-1 if idx > 0 and (idx == len(array) or abs(value - array[idx-1]) < abs(value - array[idx])) else idx
    
    # --- Analyze for logarithmic combs in Mx and Mz separately ---
    for basis, fft_amp in [('mx', mx_fft_amp), ('mz', mz_fft_amp)]:
        # Get significant peaks
        peak_indices, _ = signal.find_peaks(fft_amp, height=min_peak_amp, distance=3)
        if len(peak_indices) < min_comb_teeth:
            continue  # Need at least min_comb_teeth peaks
        
        peak_freqs = pos_freqs[peak_indices]
        peak_amps = fft_amp[peak_indices]
        
        # Eliminate any peaks too close to zero
        valid_indices = peak_freqs > 0.01  # Arbitrary small threshold
        if np.sum(valid_indices) < min_comb_teeth:
            continue
            
        peak_freqs = peak_freqs[valid_indices]
        peak_amps = peak_amps[valid_indices]
        
        # Try different potential base frequencies (first tooth of the comb)
        best_score = float('inf')
        best_r = 0
        best_base_freq = 0
        best_teeth = []
        
        # Try each peak as a potential base frequency
        for base_freq_idx, base_freq in enumerate(peak_freqs):
            # Try different growth factors (R)
            for r_factor in np.arange(min_r_factor, max_r_factor, r_step):
                # Generate logarithmic comb teeth frequencies
                max_tooth_number = int(np.log(pos_freqs[-1] / base_freq) / np.log(r_factor)) + 1
                if max_tooth_number < min_comb_teeth:
                    continue  # Not enough potential teeth in our range
                
                log_comb_freqs = [base_freq * (r_factor ** n) for n in range(max_tooth_number)]
                log_comb_freqs = [f for f in log_comb_freqs if f <= pos_freqs[-1]]  # Ensure within range
                
                # Check for each predicted tooth if there's a real peak nearby
                matched_teeth = []
                
                for tooth_idx, tooth_freq in enumerate(log_comb_freqs):
                    # Find closest peak
                    closest_peak_idx = np.argmin(np.abs(peak_freqs - tooth_freq))
                    closest_peak_freq = peak_freqs[closest_peak_idx]
                    
                    # Calculate relative error
                    rel_error = abs(closest_peak_freq - tooth_freq) / tooth_freq
                    
                    if rel_error <= freq_tolerance_factor:
                        # This is a match
                        matched_teeth.append({
                            'tooth_number': tooth_idx,
                            'expected_freq': tooth_freq,
                            'actual_freq': closest_peak_freq,
                            'rel_error': rel_error,
                            'amplitude': peak_amps[closest_peak_idx]
                        })
                
                # Score this comb if it has enough teeth
                if len(matched_teeth) >= min_comb_teeth:
                    # Score based on consistency and number of teeth
                    # We want:
                    # 1. More teeth (higher is better)
                    # 2. Lower average relative error (lower is better)
                    avg_error = np.mean([tooth['rel_error'] for tooth in matched_teeth])
                    
                    # Combined score (lower is better)
                    # We use reciprocal of teeth count to make lower better
                    comb_score = avg_error + (1.0 / len(matched_teeth))
                    
                    if comb_score < best_score:
                        best_score = comb_score
                        best_r = r_factor
                        best_base_freq = base_freq
                        best_teeth = matched_teeth
        
        # Store results if we found a valid logarithmic comb
        if best_score < float('inf'):
            results[f'{basis}_log_comb_found'] = True
            results[f'{basis}_best_r'] = best_r
            results[f'{basis}_base_freq'] = best_base_freq
            results[f'{basis}_log_comb_score'] = best_score
            results[f'{basis}_log_num_teeth'] = len(best_teeth)
            results[f'{basis}_log_comb_teeth'] = best_teeth
    
    return results
