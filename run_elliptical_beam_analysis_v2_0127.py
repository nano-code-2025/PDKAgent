"""
Mode Overlap Analysis Script
Elliptical Gaussian beam coupling to TFLN waveguide at 780 nm.

Configurable for ridge or slab waveguides with width sweep and
optional alignment tolerance analysis.
"""

import os
from dataclasses import replace

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

load_dotenv()
API_KEY = os.environ.get("TIDY3D_API_KEY", "")

WAVELENGTH = 0.78  # μm

# Waveguide geometry
WAVEGUIDE_TYPE = "slab"    # "ridge" or "slab"
RIDGE_THICKNESS = 0.30     # μm, ridge core thickness (ridge only)
SLAB_THICKNESS = 0.12      # μm, slab thickness
SLAB_WIDTH = None           # μm, None = use sim_size_y

# Width scan range (μm)
WIDTH_MIN = 6.2
WIDTH_MAX = 8.6
WIDTH_STEP = 0.2

# Simulation plane size (μm)
PLANE_SIZE = 12.0

# Gaussian beam diameter (μm)
BEAM_DIAMETER_X = 1.4
BEAM_DIAMETER_Y = 6.7


# =============================================================================
# Helpers
# =============================================================================

def _make_wg_config() -> WaveguideConfig:
    """Build base waveguide config from global constants."""
    if WAVEGUIDE_TYPE == "slab":
        thickness = SLAB_THICKNESS
    elif WAVEGUIDE_TYPE == "ridge":
        thickness = RIDGE_THICKNESS
    else:
        raise ValueError("WAVEGUIDE_TYPE must be 'ridge' or 'slab'.")

    return WaveguideConfig(
        thickness=thickness,
        width=WIDTH_MIN,
        slab_thickness=SLAB_THICKNESS,
        slab_width=SLAB_WIDTH,
        waveguide_type=WAVEGUIDE_TYPE,
        sim_size_x=10.0,
        sim_size_y=PLANE_SIZE * 1.5,
        min_steps_per_wvl=35,
    )


def _vary_width(base: WaveguideConfig, w: float) -> WaveguideConfig:
    """Return a copy of *base* with the scan dimension set to *w*."""
    if base.waveguide_type == "slab":
        return replace(base, slab_width=w)
    return replace(base, width=w)


def _print_wg_summary(cfg: WaveguideConfig) -> None:
    sw = "inf" if cfg.slab_width is None else f"{cfg.slab_width:.2f}"
    if cfg.waveguide_type == "slab":
        print(f"Waveguide: type=slab, slab_t={cfg.slab_thickness:.3f} μm, slab_w={sw} μm")
    else:
        print(
            f"Waveguide: type=ridge, ridge_t={cfg.thickness:.3f} μm, "
            f"slab_t={cfg.slab_thickness:.3f} μm, slab_w={sw} μm"
        )
    print(
        f"Simulation size: {cfg.sim_size_x:.1f} x {cfg.sim_size_y:.1f} μm | "
        f"min_steps_per_wvl={cfg.min_steps_per_wvl}"
    )


def _preview_waveguide(calc, wg_config, w: float) -> None:
    """Plot waveguide cross-section for a given width."""
    cfg = _vary_width(wg_config, w)
    solver = calc.create_mode_solver(cfg)
    solver.plot()
    plt.suptitle(f"Waveguide Cross Section - Width: {w:.2f} μm", fontsize=14, y=0.98)
    plt.tight_layout()
    plt.savefig(f"waveguide_cross_section_{w:.2f}um.png", dpi=150)
    plt.show()
    print(f"Waveguide width: {w:.2f} μm")


# =============================================================================
# Main Analysis
# =============================================================================

def run_analysis():
    """Run mode overlap analysis with specified parameters."""
    # 1. Material & calculator
    material = MaterialConfig.from_dispersion(WAVELENGTH)
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

    # 2. Gaussian beam
    beam_config = GaussianBeamConfig(
        waist_radius_x=BEAM_DIAMETER_X / 2,
        waist_radius_y=BEAM_DIAMETER_Y / 2,
        pol_angle=np.pi / 2,
        plane_size=PLANE_SIZE,
        resolution=1000,
    )
    beam = calc.create_gaussian_beam(beam_config)
    print(f"Beam: {BEAM_DIAMETER_X:.2f} x {BEAM_DIAMETER_Y:.2f} μm (diameter, elliptical)")

    fig_beam = calc.plot_gaussian_beam(
        beam,
        title=f"Elliptical Gaussian Beam ({BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} μm)",
    )
    fig_beam.tight_layout()
    fig_beam.savefig(f"gaussian_beam_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png", dpi=150)
    plt.show()

    # 3. Waveguide & scan config
    scan_config = ScanConfig(width_min=WIDTH_MIN, width_max=WIDTH_MAX, width_step=WIDTH_STEP)
    wg_config = _make_wg_config()

    print(f"Width scan: {scan_config.width_list} μm")
    _print_wg_summary(wg_config)

    # 4. Preview first & last waveguide
    width_list = scan_config.width_list
    if width_list.size > 0:
        _preview_waveguide(calc, wg_config, float(width_list[0]))
        _preview_waveguide(calc, wg_config, float(width_list[-1]))

    user_ok = input("Check plots and continue? (y/N): ").strip().lower()
    if user_ok not in ("y", "yes"):
        print("Stopped by user.")
        return None, None, None, scan_config

    # 5. Batch mode solving
    print("\nRunning waveguide mode simulations...")
    batch_results = calc.scan_waveguide_widths(scan_config, wg_config)

    # 6. Coupling efficiency
    print("\nComputing coupling efficiencies...")
    beam_label = f"{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um_elliptical"
    loss_results = calc.scan_coupling_vs_width(batch_results, {beam_label: beam}, scan_config)

    losses = loss_results[f"{beam_label}_loss_db"]
    efficiencies = loss_results[f"{beam_label}_efficiency"]

    # 7. Print results
    print("\n" + "=" * 50)
    print("Results: Coupling Loss vs Waveguide Width")
    print("=" * 50)
    print(f"{'Width (μm)':<12} {'Loss (dB)':<12} {'Efficiency (%)':<15}")
    print("-" * 40)
    for w, loss, eff in zip(width_list, losses, efficiencies):
        print(f"{w:<12.1f} {loss:<12.2f} {eff * 100:<15.2f}")

    opt_idx = np.argmin(losses)
    opt_width = width_list[opt_idx]
    print("-" * 40)
    print(
        f"Optimal: width = {opt_width:.1f} μm, "
        f"loss = {losses[opt_idx]:.2f} dB, "
        f"η = {efficiencies[opt_idx] * 100:.1f}%"
    )

    # 8. Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(width_list, losses, "bo-", linewidth=2, markersize=8,
            markerfacecolor="white", markeredgewidth=2)
    ax.axvline(opt_width, color="r", linestyle="--", alpha=0.5,
               label=f"Optimal: {opt_width:.1f} μm")
    ax.set_xlabel("Waveguide Width (μm)", fontsize=14)
    ax.set_ylabel("Coupling Loss (dB)", fontsize=14)
    ax.set_title(
        f"Coupling Loss: {BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} μm "
        f"Elliptical Beam -> TFLN Waveguide",
        fontsize=12,
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(
        f"coupling_loss_elliptical_beam_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png",
        dpi=150,
    )
    plt.show()

    # 9. Alignment tolerance (optional)
    user_align = input("Run alignment tolerance scan? (y/N): ").strip().lower()
    if user_align in ("y", "yes"):
        width_input = input(f"Use width (μm) [default {opt_width:.2f}]: ").strip()
        align_width = opt_width if not width_input else float(width_input)

        align_scan_config = ScanConfig(
            width_min=WIDTH_MIN, width_max=WIDTH_MAX, width_step=WIDTH_STEP,
            shift_x_range=scan_config.shift_x_range,
            shift_y_range=scan_config.shift_y_range,
            shift_points=scan_config.shift_points,
        )

        optimal_mode = batch_results[f"w={align_width:.2f}"]
        tolerance_map = calc.scan_alignment_tolerance(optimal_mode, beam, align_scan_config)
        fig = calc.plot_alignment_tolerance(
            tolerance_map, align_scan_config,
            f"{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} μm beam",
        )
        plt.tight_layout()
        plt.savefig(
            f"alignment_tolerance_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png",
            dpi=150,
        )
        plt.show()

    return calc, batch_results, loss_results, scan_config


if __name__ == "__main__":
    calc, batch_results, loss_results, scan_config = run_analysis()
