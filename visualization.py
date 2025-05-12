"""
Visualization module for quantum simulation results.
Contains functions for plotting and data presentation.
"""

import numpy as np
# Configure matplotlib to use a non-interactive backend (avoid 'main thread' warnings)
import matplotlib
matplotlib.use('Agg')  # Must be before importing pyplot
import matplotlib.pyplot as plt
import os
import json
import datetime
from matplotlib.figure import Figure
import pandas as pd

def plot_expectation_values(times, expectation_values, plot_title='Qubit Expectation Values', 
                           show_plot=False, save_path=None, save_prefix='expectation'):
    """
    Plot expectation values <X>, <Y>, <Z> over time.
    """
    # Extract values
    mx_values = expectation_values['mx']
    my_values = expectation_values['my']
    mz_values = expectation_values['mz']
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot each component
    ax.plot(times, mx_values, 'r-', label='<X>', alpha=0.7)
    ax.plot(times, my_values, 'g-', label='<Y>', alpha=0.7)
    ax.plot(times, mz_values, 'b-', label='<Z>', alpha=0.7)
    
    # Add labels and title
    ax.set_xlabel('Time')
    ax.set_ylabel('Expectation Value')
    ax.set_title(plot_title)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()
    
    # Set y-axis limits slightly beyond [-1, 1]
    ax.set_ylim(-1.1, 1.1)
    
    # Save the figure if a path is provided
    if save_path:
        fig_filename = os.path.join(save_path, f"{save_prefix}_values.png")
        fig.savefig(fig_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return fig_filename
    
    # Show if requested (and return figure)
    if show_plot:
        plt.tight_layout()
        plt.show()
    else:
        plt.close(fig)
    
    return fig

def plot_fft_analysis(analysis, drive_freq=None, plot_title='FFT Analysis', 
                     show_plot=False, save_path=None, save_prefix='fft', 
                     highlight_harmonics=True, highlight_incommensurate=True,
                     fc_analysis=None, max_freq_display=None):
    """
    Plot FFT analysis of expectation values, highlighting key frequencies.
    """
    # Get frequency data
    pos_freqs = analysis.get('positive_frequencies', np.array([]))
    mx_fft_amp = analysis.get('mx_fft_pos', np.array([]))
    mz_fft_amp = analysis.get('mz_fft_pos', np.array([]))
    
    if pos_freqs.size == 0 or mx_fft_amp.size == 0 or mz_fft_amp.size == 0:
        print("Warning: Missing FFT data for plotting.")
        return None
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Limit x-axis if specified
    if max_freq_display and max_freq_display > 0:
        display_mask = pos_freqs <= max_freq_display
        display_freqs = pos_freqs[display_mask]
        display_mx = mx_fft_amp[display_mask]
        display_mz = mz_fft_amp[display_mask]
    else:
        display_freqs = pos_freqs
        display_mx = mx_fft_amp
        display_mz = mz_fft_amp
    
    # Plot FFT for X component
    ax1.plot(display_freqs, display_mx, 'r-', label='FFT(<X>)', alpha=0.7)
    ax1.set_ylabel('|FFT(<X>)|')
    ax1.set_title(f'{plot_title} - X Component')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # Plot FFT for Z component
    ax2.plot(display_freqs, display_mz, 'b-', label='FFT(<Z>)', alpha=0.7)
    ax2.set_xlabel('Frequency')
    ax2.set_ylabel('|FFT(<Z>)|')
    ax2.set_title('Z Component')
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    # Highlight drive frequency if provided
    if drive_freq is not None:
        for ax in [ax1, ax2]:
            ax.axvline(x=drive_freq, color='green', linestyle='--', label=f'Drive ({drive_freq:.3f})')
    
    # Highlight specific frequencies if requested
    if highlight_harmonics:
        # Highlight primary frequencies found in the analysis
        primary_mx_freq = analysis.get('primary_mx_freq', 0)
        primary_mz_freq = analysis.get('primary_mz_freq', 0)
        
        if primary_mx_freq > 0:
            relation = analysis.get('mx_harmonic_relation', '')
            label = f'Primary X ({primary_mx_freq:.3f})'
            if relation:
                label += f' - {relation}'
            ax1.axvline(x=primary_mx_freq, color='purple', linestyle='-.', alpha=0.7, label=label)
        
        if primary_mz_freq > 0:
            relation = analysis.get('mz_harmonic_relation', '')
            label = f'Primary Z ({primary_mz_freq:.3f})'
            if relation:
                label += f' - {relation}'
            ax2.axvline(x=primary_mz_freq, color='purple', linestyle='-.', alpha=0.7, label=label)
    
    # Highlight incommensurate frequencies if requested and available
    if highlight_incommensurate and fc_analysis:
        strongest_peak = fc_analysis.get('strongest_incommensurate_peak')
        if strongest_peak:
            freq = strongest_peak.get('frequency', 0)
            basis = strongest_peak.get('basis', '')
            ratio = strongest_peak.get('ratio_to_drive', 0)
            
            if freq > 0:
                label = f'Incomm ({freq:.3f}, ratio={ratio:.3f})'
                if basis == 'Mx':
                    ax1.axvline(x=freq, color='orange', linestyle=':', alpha=0.8, label=label)
                elif basis == 'Mz':
                    ax2.axvline(x=freq, color='orange', linestyle=':', alpha=0.8, label=label)
    
    # Add legends
    ax1.legend(loc='upper right')
    ax2.legend(loc='upper right')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the figure if a path is provided
    if save_path:
        fig_filename = os.path.join(save_path, f"{save_prefix}_analysis.png")
        fig.savefig(fig_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return fig_filename
    
    # Show if requested (and return figure)
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig

def plot_frequency_comb_analysis(analysis, comb_analysis, drive_freq=None, 
                               plot_title='Frequency Comb Analysis',
                               show_plot=False, save_path=None, save_prefix='comb',
                               max_freq_display=None):
    """
    Plot frequency comb analysis, highlighting detected comb structures.
    """
    # Get frequency data
    pos_freqs = analysis.get('positive_frequencies', np.array([]))
    mx_fft_amp = analysis.get('mx_fft_pos', np.array([]))
    mz_fft_amp = analysis.get('mz_fft_pos', np.array([]))
    
    if pos_freqs.size == 0 or mx_fft_amp.size == 0 or mz_fft_amp.size == 0:
        print("Warning: Missing FFT data for plotting frequency comb analysis.")
        return None
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Limit x-axis if specified
    if max_freq_display and max_freq_display > 0:
        display_mask = pos_freqs <= max_freq_display
        display_freqs = pos_freqs[display_mask]
        display_mx = mx_fft_amp[display_mask]
        display_mz = mz_fft_amp[display_mask]
    else:
        display_freqs = pos_freqs
        display_mx = mx_fft_amp
        display_mz = mz_fft_amp
    
    # Plot FFT for X component
    ax1.plot(display_freqs, display_mx, 'r-', label='FFT(<X>)', alpha=0.5)
    ax1.set_ylabel('|FFT(<X>)|')
    ax1.set_title(f'{plot_title} - X Component')
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # Plot FFT for Z component
    ax2.plot(display_freqs, display_mz, 'b-', label='FFT(<Z>)', alpha=0.5)
    ax2.set_xlabel('Frequency')
    ax2.set_ylabel('|FFT(<Z>)|')
    ax2.set_title('Z Component')
    ax2.grid(True, linestyle='--', alpha=0.6)
    
    # Highlight drive frequency if provided
    if drive_freq is not None:
        for ax in [ax1, ax2]:
            ax.axvline(x=drive_freq, color='green', linestyle='--', 
                      label=f'Drive ({drive_freq:.3f})', alpha=0.7)
    
    # Highlight detected linear frequency combs
    # X component comb
    if comb_analysis.get('mx_comb_found', False):
        omega = comb_analysis.get('mx_best_omega', 0)
        teeth = comb_analysis.get('mx_comb_details', [])
        
        if omega > 0 and teeth:
            # Mark Omega value
            ax1.axvline(x=omega, color='purple', linestyle='-.',
                       label=f'Ω = {omega:.3f}', alpha=0.7)
            
            # Mark each tooth with a vertical line
            for tooth in teeth:
                freq = tooth.get('freq', 0)
                amp = tooth.get('amplitude', 0)
                tooth_num = tooth.get('tooth_number', 0)
                
                if tooth_num <= 3:  # Label only first few teeth
                    ax1.axvline(x=freq, color='orange', linestyle=':',
                              label=f'{tooth_num}Ω = {freq:.3f}', alpha=0.6)
                else:
                    ax1.axvline(x=freq, color='orange', linestyle=':', alpha=0.4)
                
                # Add a marker at the peak
                ax1.plot(freq, amp, 'o', color='orange', markersize=5)
    
    # Z component comb
    if comb_analysis.get('mz_comb_found', False):
        omega = comb_analysis.get('mz_best_omega', 0)
        teeth = comb_analysis.get('mz_comb_details', [])
        
        if omega > 0 and teeth:
            # Mark Omega value
            ax2.axvline(x=omega, color='purple', linestyle='-.',
                       label=f'Ω = {omega:.3f}', alpha=0.7)
            
            # Mark each tooth with a vertical line
            for tooth in teeth:
                freq = tooth.get('freq', 0)
                amp = tooth.get('amplitude', 0)
                tooth_num = tooth.get('tooth_number', 0)
                
                if tooth_num <= 3:  # Label only first few teeth
                    ax2.axvline(x=freq, color='orange', linestyle=':',
                              label=f'{tooth_num}Ω = {freq:.3f}', alpha=0.6)
                else:
                    ax2.axvline(x=freq, color='orange', linestyle=':', alpha=0.4)
                
                # Add a marker at the peak
                ax2.plot(freq, amp, 'o', color='orange', markersize=5)
    
    # Add legends
    ax1.legend(loc='upper right')
    ax2.legend(loc='upper right')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the figure if a path is provided
    if save_path:
        fig_filename = os.path.join(save_path, f"{save_prefix}_analysis.png")
        fig.savefig(fig_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return fig_filename
    
    # Show if requested (and return figure)
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig

def plot_log_comb_analysis(analysis, log_comb_analysis, 
                         plot_title='Logarithmic Frequency Comb Analysis',
                         show_plot=False, save_path=None, save_prefix='log_comb'):
    """
    Plot logarithmic frequency comb analysis, highlighting detected log-comb structures.
    """
    # Get frequency data
    pos_freqs = analysis.get('positive_frequencies', np.array([]))
    mx_fft_amp = analysis.get('mx_fft_pos', np.array([]))
    mz_fft_amp = analysis.get('mz_fft_pos', np.array([]))
    
    if pos_freqs.size == 0 or mx_fft_amp.size == 0 or mz_fft_amp.size == 0:
        print("Warning: Missing FFT data for plotting log-comb analysis.")
        return None
    
    # Create figure - with logarithmic x-axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot FFT for X component on log scale
    ax1.semilogx(pos_freqs[1:], mx_fft_amp[1:], 'r-', label='FFT(<X>)', alpha=0.5)  # Skip DC
    ax1.set_ylabel('|FFT(<X>)|')
    ax1.set_title(f'{plot_title} - X Component')
    ax1.grid(True, linestyle='--', alpha=0.6, which='both')
    
    # Plot FFT for Z component on log scale
    ax2.semilogx(pos_freqs[1:], mz_fft_amp[1:], 'b-', label='FFT(<Z>)', alpha=0.5)  # Skip DC
    ax2.set_xlabel('Frequency (log scale)')
    ax2.set_ylabel('|FFT(<Z>)|')
    ax2.set_title('Z Component')
    ax2.grid(True, linestyle='--', alpha=0.6, which='both')
    
    # Highlight detected logarithmic combs
    # X component log comb
    if log_comb_analysis.get('mx_log_comb_found', False):
        r_factor = log_comb_analysis.get('mx_best_r', 0)
        base_freq = log_comb_analysis.get('mx_base_freq', 0)
        teeth = log_comb_analysis.get('mx_log_comb_teeth', [])
        
        if r_factor > 0 and base_freq > 0 and teeth:
            # Mark base frequency
            ax1.axvline(x=base_freq, color='purple', linestyle='-.',
                       label=f'Base = {base_freq:.3f}, R = {r_factor:.3f}', alpha=0.7)
            
            # Mark each tooth with a vertical line
            for tooth in teeth:
                freq = tooth.get('actual_freq', 0)
                expected = tooth.get('expected_freq', 0)
                tooth_num = tooth.get('tooth_number', 0)
                
                if freq > 0:
                    if tooth_num <= 3:  # Label only first few teeth
                        ax1.axvline(x=freq, color='orange', linestyle=':',
                                  label=f'n={tooth_num}: {freq:.3f}', alpha=0.6)
                    else:
                        ax1.axvline(x=freq, color='orange', linestyle=':', alpha=0.4)
    
    # Z component log comb
    if log_comb_analysis.get('mz_log_comb_found', False):
        r_factor = log_comb_analysis.get('mz_best_r', 0)
        base_freq = log_comb_analysis.get('mz_base_freq', 0)
        teeth = log_comb_analysis.get('mz_log_comb_teeth', [])
        
        if r_factor > 0 and base_freq > 0 and teeth:
            # Mark base frequency
            ax2.axvline(x=base_freq, color='purple', linestyle='-.',
                       label=f'Base = {base_freq:.3f}, R = {r_factor:.3f}', alpha=0.7)
            
            # Mark each tooth with a vertical line
            for tooth in teeth:
                freq = tooth.get('actual_freq', 0)
                expected = tooth.get('expected_freq', 0)
                tooth_num = tooth.get('tooth_number', 0)
                
                if freq > 0:
                    if tooth_num <= 3:  # Label only first few teeth
                        ax2.axvline(x=freq, color='orange', linestyle=':',
                                  label=f'n={tooth_num}: {freq:.3f}', alpha=0.6)
                    else:
                        ax2.axvline(x=freq, color='orange', linestyle=':', alpha=0.4)
    
    # Add legends
    ax1.legend(loc='upper right')
    ax2.legend(loc='upper right')
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the figure if a path is provided
    if save_path:
        fig_filename = os.path.join(save_path, f"{save_prefix}_analysis.png")
        fig.savefig(fig_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return fig_filename
    
    # Show if requested (and return figure)
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig

def plot_circuit_diagram(circuit, time_value=None, circuit_type='', 
                       qubit_count=None, save_path=None):
    """
    Plot the quantum circuit diagram.
    """
    # Skip parameter binding - works with both old and new Qiskit versions
    # We'll just use the original circuit and add a note in the title
    bound_circuit = circuit
    
    # Create the figure and draw the circuit
    try:
        fig, ax = plt.subplots(figsize=(12, min(10, 1 + 0.7 * bound_circuit.num_qubits)))
        
        try:
            circuit_drawing = bound_circuit.draw(output='mpl', ax=ax)
        except Exception as draw_error:
            print(f"Warning: Could not draw circuit diagram: {draw_error}")
            # Create a simple text representation as fallback
            ax.text(0.5, 0.5, f"Circuit type: {circuit_type}\nQubits: {qubit_count}\nDepth: {circuit.depth()}", 
                   ha='center', va='center', fontsize=12)
            ax.axis('off')
        
        # Set title
        qubits_info = f" ({qubit_count} qubits)" if qubit_count else ""
        title = f"Circuit Diagram: {circuit_type}{qubits_info}"
        if time_value is not None:
            title += f" (t={time_value:.2f})"
        ax.set_title(title)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save if path provided
        if save_path:
            fig_filename = os.path.join(save_path, f"circuit_diagram_{circuit_type}.png")
            plt.savefig(fig_filename, dpi=150, bbox_inches='tight')
            plt.close(fig)
            return fig_filename
        
        # Display and return
        plt.show()
        return fig
    except Exception as e:
        print(f"Error plotting circuit diagram: {e}")
        return None
