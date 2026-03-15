"""
Mode Overlap Analysis Script
Elliptical Gaussian beam (1.4 x 6.7 μm) coupling to TFLN waveguide

Parameters:
- Beam waist: 1.4 μm × 6.7 μm (elliptical/astigmatic)
- Waveguide width scan: 6.0 - 7.4 μm, step 0.2 μm
- Waveguide thickness: 0.12 μm
- Wavelength: 780 nm
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from mode_overlap_calculator import (
    ModeOverlapCalculator,
    WaveguideConfig,
    GaussianBeamConfig,
    ScanConfig,
    MaterialConfig,
)

# =============================================================================
# Configuration
# =============================================================================

# Load API key from .env file
load_dotenv()
API_KEY = os.environ.get("TIDY3D_API_KEY", "")

# Wavelength
WAVELENGTH = 0.78  # μm

# Waveguide geometry
# Example (ridge): WAVEGUIDE_TYPE="ridge", RIDGE_THICKNESS=0.30, SLAB_THICKNESS=0.12
# Example (slab):  WAVEGUIDE_TYPE="slab",  SLAB_THICKNESS=0.12
WAVEGUIDE_TYPE = "slab"   # "ridge" or "slab"
RIDGE_THICKNESS = 0.30     # μm, ridge core thickness (ridge only)
SLAB_THICKNESS = 0.12      # μm, slab thickness (ridge/slab)
SLAB_WIDTH = None          # μm, None uses sim_size_y

width_min = 6.2
width_max = 8.6
width_step = 0.2

plane_size = 12.0 # plane size for the beam profile

# Gaussian beam size (diameter in μm)
BEAM_DIAMETER_X = 1.4
BEAM_DIAMETER_Y = 6.7

# =============================================================================
# Main Analysis
# =============================================================================
def run_analysis():
    """Run mode overlap analysis with specified parameters."""
    # Initialize dispersive material models (LiTaO3 / SiO2)
    material = MaterialConfig.from_dispersion(WAVELENGTH)

    # 1. Initialize calculator
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH, material=material)
    calc.configure_api(API_KEY)

    print("\n" + "=" * 50)
    print("Config Summary")
    print("=" * 50)
    print(f"Wavelength: {WAVELENGTH:.3f} μm")
    print(
        f"Material: {material.name} | "
        f"n_o={material.n_ordinary:.6f}, "
        f"n_e={material.n_extraordinary:.6f}, "
        f"n_clad={material.n_cladding:.6f}"
    )
    
    # 2. Create elliptical Gaussian beam
    beam_config = GaussianBeamConfig(
        waist_radius_x=BEAM_DIAMETER_X / 2,    # waist in x direction (μm)
        waist_radius_y=BEAM_DIAMETER_Y / 2,    # waist in y direction (μm)
        pol_angle=np.pi / 2,   # TE polarization
        plane_size=plane_size,       # 增大平面尺寸以容纳大光斑
        resolution=1000,
    )
    beam = calc.create_gaussian_beam(beam_config)
    print(
        "Created elliptical beam: "
        f"{BEAM_DIAMETER_X:.2f} × {BEAM_DIAMETER_Y:.2f} μm (diameter)"
    )

    # Plot Gaussian beam intensity profile
    fig_beam = calc.plot_gaussian_beam(
        beam,
        title=f"Elliptical Gaussian Beam ({BEAM_DIAMETER_X:.2f}×{BEAM_DIAMETER_Y:.2f} μm diameter)",
    )
    fig_beam.tight_layout()
    fig_beam.savefig(f"gaussian_beam_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png", dpi=150)
    plt.show()
    
    # 3. Define waveguide scan configuration
    scan_config = ScanConfig(
        width_min=width_min,      # 6.0 μm
        width_max=width_max,      # 7.6 μm (exclusive, so last point is 7.4)
        width_step=width_step,     # 0.2 μm step
    )
    print(f"Width scan: {scan_config.width_list} μm")
    print(f"Beam diameter: {BEAM_DIAMETER_X:.2f} × {BEAM_DIAMETER_Y:.2f} μm")
    
    # 4. Define base waveguide configuration
    if WAVEGUIDE_TYPE == "slab":
        if SLAB_THICKNESS <= 0:
            raise ValueError("SLAB_THICKNESS must be > 0 for slab waveguide.")
        wg_config = WaveguideConfig(
            thickness=SLAB_THICKNESS,
            width=6.0,              # unused in slab-only, kept for consistency
            slab_thickness=SLAB_THICKNESS,
            slab_width=SLAB_WIDTH,
            waveguide_type=WAVEGUIDE_TYPE,
            sim_size_x=10.0,        # 增大仿真域以适应宽波导
            sim_size_y=plane_size*1.5,        # 增大y方向以容纳大模场
            min_steps_per_wvl=35,
        )
    elif WAVEGUIDE_TYPE == "ridge":
        if RIDGE_THICKNESS <= 0 or SLAB_THICKNESS <= 0:
            raise ValueError("RIDGE_THICKNESS and SLAB_THICKNESS must be > 0 for ridge waveguide.")
        wg_config = WaveguideConfig(
            thickness=RIDGE_THICKNESS,
            width=6.0,              # will be overridden in scan
            slab_thickness=SLAB_THICKNESS,
            slab_width=SLAB_WIDTH,
            waveguide_type=WAVEGUIDE_TYPE,
            sim_size_x=10.0,        # 增大仿真域以适应宽波导
            sim_size_y=plane_size*1.5,        # 增大y方向以容纳大模场
            min_steps_per_wvl=35,
        )
    else:
        raise ValueError("WAVEGUIDE_TYPE must be 'ridge' or 'slab'.")

    slab_width_text = "inf" if wg_config.slab_width is None else f"{wg_config.slab_width:.2f}"
    if wg_config.waveguide_type == "slab":
        print(
            "Waveguide: "
            f"type=slab, "
            f"slab_t={wg_config.slab_thickness:.3f} μm, "
            f"slab_w={slab_width_text} μm"
        )
    else:
        print(
            "Waveguide: "
            f"type=ridge, "
            f"ridge_t={wg_config.thickness:.3f} μm, "
            f"slab_t={wg_config.slab_thickness:.3f} μm, "
            f"slab_w={slab_width_text} μm"
        )
    print(
        f"Simulation size: {wg_config.sim_size_x:.1f} × {wg_config.sim_size_y:.1f} μm | "
        f"min_steps_per_wvl={wg_config.min_steps_per_wvl}"
    )

    # Plot waveguide structure using mode solver preview (c.plot style)
    # preview_solver = calc.create_mode_solver(wg_config)
    # preview_solver.plot()
    # plt.tight_layout()
    # plt.savefig("waveguide_cross_section.png", dpi=150)
    # plt.show()

    # Plot first/last waveguide in the scan
    width_list = scan_config.width_list
    if width_list.size > 0:
        first_w = float(width_list[0])
        last_w = float(width_list[-1])
        if wg_config.waveguide_type == "slab":
            first_cfg = WaveguideConfig(
                thickness=wg_config.thickness,
                width=wg_config.width,
                slab_thickness=wg_config.slab_thickness,
                slab_width=first_w,
                waveguide_type=wg_config.waveguide_type,
                sim_size_x=wg_config.sim_size_x,
                sim_size_y=wg_config.sim_size_y,
                min_steps_per_wvl=wg_config.min_steps_per_wvl,
            )
            last_cfg = WaveguideConfig(
                thickness=wg_config.thickness,
                width=wg_config.width,
                slab_thickness=wg_config.slab_thickness,
                slab_width=last_w,
                waveguide_type=wg_config.waveguide_type,
                sim_size_x=wg_config.sim_size_x,
                sim_size_y=wg_config.sim_size_y,
                min_steps_per_wvl=wg_config.min_steps_per_wvl,
            )
        else:
            first_cfg = WaveguideConfig(
                thickness=wg_config.thickness,
                width=first_w,
                slab_thickness=wg_config.slab_thickness,
                slab_width=wg_config.slab_width,
                waveguide_type=wg_config.waveguide_type,
                sim_size_x=wg_config.sim_size_x,
                sim_size_y=wg_config.sim_size_y,
                min_steps_per_wvl=wg_config.min_steps_per_wvl,
            )
            last_cfg = WaveguideConfig(
                thickness=wg_config.thickness,
                width=last_w,
                slab_thickness=wg_config.slab_thickness,
                slab_width=wg_config.slab_width,
                waveguide_type=wg_config.waveguide_type,
                sim_size_x=wg_config.sim_size_x,
                sim_size_y=wg_config.sim_size_y,
                min_steps_per_wvl=wg_config.min_steps_per_wvl,
            )

        first_solver = calc.create_mode_solver(first_cfg)
        first_solver.plot()
        plt.suptitle(f"Waveguide Cross Section - Width: {first_w:.2f} μm", fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(f"waveguide_cross_section_first_{first_w:.2f}um.png", dpi=150)
        plt.show()
        print(f"First waveguide width: {first_w:.2f} μm")

        last_solver = calc.create_mode_solver(last_cfg)
        last_solver.plot()
        plt.suptitle(f"Waveguide Cross Section - Width: {last_w:.2f} μm", fontsize=14, y=0.98)
        plt.tight_layout()
        plt.savefig(f"waveguide_cross_section_last_{last_w:.2f}um.png", dpi=150)
        plt.show()
        print(f"Last waveguide width: {last_w:.2f} μm")

    user_ok = input("Check plots and continue? (y/N): ").strip().lower()
    if user_ok not in ("y", "yes"):
        print("Stopped by user. Update geometry/beam and run again.")
        return None, None, None, scan_config
    
    # 5. Run batch mode solving
    print("\nRunning waveguide mode simulations...")
    batch_results = calc.scan_waveguide_widths(scan_config, wg_config)
    
    # 6. Calculate coupling for the elliptical beam
    print("\nComputing coupling efficiencies...")
    beam_label = f"{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um_elliptical"
    beams = {beam_label: beam}
    loss_results = calc.scan_coupling_vs_width(batch_results, beams, scan_config)
    
    # 7. Print results
    print("\n" + "=" * 50)
    print("Results: Coupling Loss vs Waveguide Width")
    print("=" * 50)
    print(f"{'Width (μm)':<12} {'Loss (dB)':<12} {'Efficiency (%)':<15}")
    print("-" * 40)
    
    losses = loss_results[f"{beam_label}_loss_db"]
    efficiencies = loss_results[f"{beam_label}_efficiency"]
    
    for w, loss, eff in zip(scan_config.width_list, losses, efficiencies):
        print(f"{w:<12.1f} {loss:<12.2f} {eff*100:<15.2f}")
    
    # Find optimal
    opt_idx = np.argmin(losses)
    opt_width = scan_config.width_list[opt_idx]
    min_loss = losses[opt_idx]
    max_eff = efficiencies[opt_idx]
    
    print("-" * 40)
    print(
        f"Optimal: width = {opt_width:.1f} μm, loss = {min_loss:.2f} dB, "
        f"η = {max_eff*100:.1f}% (beam {BEAM_DIAMETER_X:.2f}×{BEAM_DIAMETER_Y:.2f} μm)"
    )
        # 8. Plot results
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(scan_config.width_list, losses, 'bo-', linewidth=2, markersize=8,
            markerfacecolor='white', markeredgewidth=2)
    ax.axvline(opt_width, color='r', linestyle='--', alpha=0.5, label=f'Optimal: {opt_width:.1f} μm')
    ax.set_xlabel("Waveguide Width (μm)", fontsize=14)
    ax.set_ylabel("Coupling Loss (dB)", fontsize=14)
    ax.set_title(
        f"Coupling Loss: {BEAM_DIAMETER_X:.2f}×{BEAM_DIAMETER_Y:.2f} μm "
        f"Elliptical Beam → TFLN Waveguide",
        fontsize=12,
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"coupling_loss_elliptical_beam_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png", dpi=150)
    plt.show()
    
    # 8. Calculate alignment tolerance (optional)
    user_align = input("Run alignment tolerance scan? (y/N): ").strip().lower()
    if user_align in ("y", "yes"):
        width_input = input(f"Use width (μm) [default {opt_width:.2f}]: ").strip()
        align_width = opt_width if width_input == "" else float(width_input)

        shift_x_input = input(
            f"Shift x range (start,end) μm [default {scan_config.shift_x_range[0]},{scan_config.shift_x_range[1]}]: "
        ).strip()
        shift_y_input = input(
            f"Shift y range (start,end) μm [default {scan_config.shift_y_range[0]},{scan_config.shift_y_range[1]}]: "
        ).strip()
        shift_points_input = input(
            f"Shift points [default {scan_config.shift_points}]: "
        ).strip()

        shift_x_range = scan_config.shift_x_range
        if shift_x_input:
            start, end = shift_x_input.split(",")
            shift_x_range = (float(start), float(end))

        shift_y_range = scan_config.shift_y_range
        if shift_y_input:
            start, end = shift_y_input.split(",")
            shift_y_range = (float(start), float(end))

        shift_points = scan_config.shift_points if shift_points_input == "" else int(shift_points_input)

        align_scan_config = ScanConfig(
            width_min=scan_config.width_min,
            width_max=scan_config.width_max,
            width_step=scan_config.width_step,
            shift_x_range=shift_x_range,
            shift_y_range=shift_y_range,
            shift_points=shift_points,
        )

        optimal_mode = batch_results[f"w={align_width:.2f}"]
        alignment_tolerance = calc.scan_alignment_tolerance(optimal_mode, beam, align_scan_config)
        fig = calc.plot_alignment_tolerance(
            alignment_tolerance,
            align_scan_config,
            f"{BEAM_DIAMETER_X:.2f}×{BEAM_DIAMETER_Y:.2f} μm beam",
        )
        plt.tight_layout()
        plt.savefig(
            f"alignment_tolerance_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png",
            dpi=150,
        )
        plt.show()


    
    return calc, batch_results, loss_results, scan_config


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    calc, batch_results, loss_results, scan_config = run_analysis()
