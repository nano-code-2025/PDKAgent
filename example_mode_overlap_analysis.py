"""
Example Script: Mode Overlap Analysis for TFLN Waveguide

This script demonstrates how to use the mode_overlap_calculator module
for analyzing fiber-to-chip coupling efficiency.

Usage:
    python example_mode_overlap_analysis.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from mode_overlap_calculator import (
    ModeOverlapCalculator,
    MaterialConfig,
    WaveguideConfig,
    GaussianBeamConfig,
    ScanConfig,
    quick_coupling_analysis,
)

# =============================================================================
# Configuration
# =============================================================================

# Load API key from .env file
load_dotenv()
API_KEY = os.environ.get("TIDY3D_API_KEY", "")

# Wavelength (μm)
WAVELENGTH = 0.78  # 780 nm

# =============================================================================
# Example 1: Basic Usage with Default Parameters
# =============================================================================

def example_basic_analysis():
    """
    Basic coupling analysis using default TFLN parameters.
    """
    print("\n" + "=" * 60)
    print("Example 1: Basic Coupling Analysis")
    print("=" * 60)
    
    # Initialize calculator
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH)
    
    # Configure API (uncomment when ready to run)
    # calc.configure_api(API_KEY)
    
    # Create standard Gaussian beams
    beams = calc.create_standard_beams(
        diameters=[1, 2, 3, 4],
        elliptical=[(1, 2)]  # 1x2 μm elliptical beam
    )
    
    print(f"Created {len(beams)} beam profiles:")
    for name in beams:
        print(f"  - {name}")
    
    # Define waveguide configuration
    wg_config = WaveguideConfig(
        thickness=0.12,  # 120 nm TFLN
        width=0.3,       # 300 nm waveguide width
    )
    
    print(f"\nWaveguide: {wg_config.thickness*1000:.0f} nm × {wg_config.width*1000:.0f} nm")
    
    return calc, beams, wg_config


# =============================================================================
# Example 2: Custom Material Configuration
# =============================================================================

def example_custom_material():
    """
    Analysis with custom material parameters (e.g., different wavelength).
    """
    print("\n" + "=" * 60)
    print("Example 2: Custom Material at 1550 nm")
    print("=" * 60)
    
    # Define custom material for 1550 nm
    material_1550nm = MaterialConfig(
        name="TFLN_1550nm",
        n_ordinary=2.211,      # LN ordinary index at 1550nm
        n_extraordinary=2.138, # LN extraordinary index at 1550nm
        n_cladding=1.444,      # SiO2 at 1550nm
        reference_wavelength=1.55,
    )
    
    # Initialize calculator with custom material
    calc = ModeOverlapCalculator(
        wavelength=1.55,
        material=material_1550nm
    )
    
    print(f"Material: {calc.material.name}")
    print(f"  no = {calc.material.n_ordinary}")
    print(f"  ne = {calc.material.n_extraordinary}")
    print(f"  nclad = {calc.material.n_cladding}")
    
    return calc


# =============================================================================
# Example 3: Width Scan Analysis
# =============================================================================

def example_width_scan():
    """
    Scan coupling efficiency vs waveguide width.
    """
    print("\n" + "=" * 60)
    print("Example 3: Waveguide Width Scan")
    print("=" * 60)
    
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH)
    
    # Define scan parameters
    scan_config = ScanConfig(
        width_min=0.15,    # 150 nm
        width_max=0.60,    # 600 nm
        width_step=0.05,   # 50 nm steps
    )
    
    print(f"Scanning width from {scan_config.width_min*1000:.0f} nm "
          f"to {scan_config.width_max*1000:.0f} nm")
    print(f"Step size: {scan_config.width_step*1000:.0f} nm")
    print(f"Total points: {len(scan_config.width_list)}")
    
    # Create beams for comparison
    beams = calc.create_standard_beams(diameters=[1, 2, 3, 4])
    
    # To run the actual simulation (requires API key):
    # calc.configure_api(API_KEY)
    # batch_results = calc.scan_waveguide_widths(scan_config)
    # loss_results = calc.scan_coupling_vs_width(batch_results, beams, scan_config)
    # fig = calc.plot_coupling_vs_width(loss_results, scan_config.width_list)
    # plt.show()
    
    return calc, scan_config, beams


# =============================================================================
# Example 4: Alignment Tolerance Analysis
# =============================================================================

def example_alignment_tolerance():
    """
    Analyze alignment tolerance by scanning position offsets.
    """
    print("\n" + "=" * 60)
    print("Example 4: Alignment Tolerance Analysis")
    print("=" * 60)
    
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH)
    
    # Define scan for alignment
    scan_config = ScanConfig(
        shift_x_range=(0, 3),  # 0 to 3 μm in x
        shift_y_range=(0, 3),  # 0 to 3 μm in y
        shift_points=21,       # 21 points per axis
    )
    
    print(f"Scanning alignment:")
    print(f"  X offset: {scan_config.shift_x_range[0]} to {scan_config.shift_x_range[1]} μm")
    print(f"  Y offset: {scan_config.shift_y_range[0]} to {scan_config.shift_y_range[1]} μm")
    print(f"  Grid: {scan_config.shift_points} × {scan_config.shift_points} points")
    
    # To run the actual analysis (requires solved mode):
    # mode_data = calc.solve_waveguide_mode(wg_config)
    # beam = calc.create_gaussian_beam(GaussianBeamConfig(waist_radius_x=1.5))
    # loss_map = calc.scan_alignment_tolerance(mode_data, beam, scan_config)
    # fig = calc.plot_alignment_tolerance(loss_map, scan_config, "3μm beam")
    # plt.show()
    
    return calc, scan_config


# =============================================================================
# Example 5: Complete Analysis Pipeline
# =============================================================================

def example_complete_analysis():
    """
    Complete analysis pipeline with all steps.
    
    Note: This requires a valid Tidy3D API key to run.
    """
    print("\n" + "=" * 60)
    print("Example 5: Complete Analysis Pipeline")
    print("=" * 60)
    
    # Uncomment to run with your API key:
    """
    results = quick_coupling_analysis(
        wavelength=0.78,
        wg_thickness=0.12,
        wg_width_range=(0.15, 0.6, 0.05),
        beam_diameters=[1, 2, 3, 4],
        api_key=API_KEY,
    )
    
    # Extract results
    calc = results['calculator']
    loss_results = results['loss_results']
    width_list = results['width_list']
    
    # Plot coupling vs width
    fig1 = calc.plot_coupling_vs_width(loss_results, width_list)
    plt.savefig('coupling_vs_width.png', dpi=150)
    plt.show()
    
    # Find optimal width for each beam
    for beam_name in ['1um', '2um', '3um', '4um']:
        losses = loss_results[f'{beam_name}_loss_db']
        opt_idx = np.argmin(losses)
        opt_width = width_list[opt_idx]
        min_loss = losses[opt_idx]
        print(f"{beam_name} beam: optimal width = {opt_width*1000:.0f} nm, loss = {min_loss:.2f} dB")
    """
    
    print("\nTo run this example, uncomment the code above and provide your API key.")


# =============================================================================
# Example 6: Parameter Study - Multiple Materials
# =============================================================================

def example_material_comparison():
    """
    Compare coupling for different materials.
    """
    print("\n" + "=" * 60)
    print("Example 6: Material Comparison")
    print("=" * 60)
    
    # Define materials at 780 nm
    materials = {
        "TFLN (LiNbO3)": MaterialConfig(
            name="TFLN",
            n_ordinary=2.172734,
            n_extraordinary=2.175714,
            n_cladding=1.4537,
        ),
        "LiTaO3": MaterialConfig(
            name="LiTaO3",
            n_ordinary=2.142,
            n_extraordinary=2.145,
            n_cladding=1.4537,
        ),
        "AlN on SiO2": MaterialConfig(
            name="AlN",
            n_ordinary=2.15,
            n_extraordinary=2.15,  # Isotropic approximation
            n_cladding=1.4537,
        ),
    }
    
    print("Materials defined:")
    for name, mat in materials.items():
        print(f"\n  {name}:")
        print(f"    no = {mat.n_ordinary:.4f}")
        print(f"    ne = {mat.n_extraordinary:.4f}")
        print(f"    Δn = {mat.n_extraordinary - mat.n_ordinary:.4f}")
    
    # Create calculators for each material
    calculators = {
        name: ModeOverlapCalculator(wavelength=0.78, material=mat)
        for name, mat in materials.items()
    }
    
    return calculators


# =============================================================================
# Example 7: Wavelength Sweep
# =============================================================================

def example_wavelength_sweep():
    """
    Analyze coupling across multiple wavelengths.
    """
    print("\n" + "=" * 60)
    print("Example 7: Wavelength Sweep Analysis")
    print("=" * 60)
    
    # Define wavelengths to analyze
    wavelengths = [0.78, 0.85, 1.0, 1.31, 1.55]
    
    # Material dispersion (simplified - use proper Sellmeier for real analysis)
    def get_ln_index(wavelength):
        """Simplified LN index vs wavelength."""
        # This is a rough approximation - use Sellmeier equation for accuracy
        n0 = 2.21
        return n0 - 0.01 * (wavelength - 0.78)
    
    print("Wavelength analysis:")
    for wl in wavelengths:
        n = get_ln_index(wl)
        material = MaterialConfig(
            name=f"TFLN_{int(wl*1000)}nm",
            n_ordinary=n,
            n_extraordinary=n + 0.003,
            n_cladding=1.45,
        )
        calc = ModeOverlapCalculator(wavelength=wl, material=material)
        print(f"  λ = {wl*1000:.0f} nm: no = {n:.4f}, f0 = {calc.freq0:.2e} Hz")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Mode Overlap Calculator - Usage Examples")
    print("=" * 60)
    
    # Run all examples
    example_basic_analysis()
    example_custom_material()
    example_width_scan()
    example_alignment_tolerance()
    example_complete_analysis()
    example_material_comparison()
    example_wavelength_sweep()
    
    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60)
    print("\nTo run actual simulations:")
    print("1. Replace API_KEY with your Tidy3D key")
    print("2. Uncomment the simulation code in example_complete_analysis()")
    print("3. Run: python example_mode_overlap_analysis.py")
