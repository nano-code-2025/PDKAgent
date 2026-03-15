"""
Mode Overlap Analysis Script
Elliptical Gaussian beam coupling to TFLN waveguide at 780 nm.

Configurable for ridge or slab waveguides with width sweep and
optional alignment tolerance analysis. Generates a Markdown report.
"""

import os
from dataclasses import replace
from datetime import datetime

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

# Output directory for figures and report
OUTPUT_DIR = "results"


# =============================================================================
# Helpers
# =============================================================================

def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _output_path(filename: str) -> str:
    return os.path.join(OUTPUT_DIR, filename)


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
        print(f"Waveguide: type=slab, slab_t={cfg.slab_thickness:.3f} um, slab_w={sw} um")
    else:
        print(
            f"Waveguide: type=ridge, ridge_t={cfg.thickness:.3f} um, "
            f"slab_t={cfg.slab_thickness:.3f} um, slab_w={sw} um"
        )
    print(
        f"Simulation size: {cfg.sim_size_x:.1f} x {cfg.sim_size_y:.1f} um | "
        f"min_steps_per_wvl={cfg.min_steps_per_wvl}"
    )


def _preview_waveguide(calc, wg_config, w: float) -> str:
    """Plot waveguide cross-section. Returns saved figure path."""
    cfg = _vary_width(wg_config, w)
    solver = calc.create_mode_solver(cfg)
    solver.plot()
    plt.suptitle(f"Waveguide Cross Section - Width: {w:.2f} um", fontsize=14, y=0.98)
    plt.tight_layout()
    fig_path = _output_path(f"waveguide_cross_section_{w:.2f}um.png")
    plt.savefig(fig_path, dpi=150)
    plt.show()
    print(f"Waveguide width: {w:.2f} um")
    return fig_path


# =============================================================================
# Report Generator
# =============================================================================

def generate_report(
    material,
    wg_config,
    scan_config,
    width_list,
    losses,
    efficiencies,
    opt_idx,
    figure_paths,
):
    """Generate a Markdown report with all results and embedded figures."""
    opt_width = width_list[opt_idx]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    beam_str = f"{BEAM_DIAMETER_X:.2f} x {BEAM_DIAMETER_Y:.2f}"

    sw = "inf" if wg_config.slab_width is None else f"{wg_config.slab_width:.2f}"

    lines = [
        f"# Mode Overlap Analysis Report",
        f"",
        f"**Generated:** {timestamp}",
        f"",
        f"## 1. Configuration",
        f"",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Wavelength | {WAVELENGTH * 1000:.0f} nm |",
        f"| Material | {material.name} |",
        f"| n_ordinary | {material.n_ordinary:.6f} |",
        f"| n_extraordinary | {material.n_extraordinary:.6f} |",
        f"| n_cladding | {material.n_cladding:.6f} |",
        f"| Waveguide type | {wg_config.waveguide_type} |",
        f"| Thickness | {wg_config.thickness * 1000:.0f} nm |",
        f"| Slab thickness | {wg_config.slab_thickness * 1000:.0f} nm |",
        f"| Beam diameter | {beam_str} um (elliptical) |",
        f"| Width scan | {WIDTH_MIN:.1f} - {WIDTH_MAX:.1f} um, step {WIDTH_STEP:.1f} um |",
        f"| Simulation domain | {wg_config.sim_size_x:.1f} x {wg_config.sim_size_y:.1f} um |",
        f"| Grid resolution | {wg_config.min_steps_per_wvl} steps/wavelength |",
        f"",
        f"## 2. Gaussian Beam Profile",
        f"",
    ]

    if "beam" in figure_paths:
        lines.append(f"![Gaussian Beam]({os.path.basename(figure_paths['beam'])})")
        lines.append("")

    lines += [
        f"## 3. Coupling Results",
        f"",
        f"| Width (um) | Loss (dB) | Efficiency (%) |",
        f"|------------|-----------|----------------|",
    ]
    for w, loss, eff in zip(width_list, losses, efficiencies):
        marker = " **optimal**" if abs(w - opt_width) < 1e-6 else ""
        lines.append(f"| {w:.2f} | {loss:.2f} | {eff * 100:.2f}{marker} |")

    lines += [
        f"",
        f"### Optimal Design Point",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Optimal width | {opt_width:.2f} um |",
        f"| Coupling loss | {losses[opt_idx]:.2f} dB |",
        f"| Coupling efficiency | {efficiencies[opt_idx] * 100:.1f}% |",
        f"",
    ]

    if "coupling" in figure_paths:
        lines.append(f"![Coupling Loss vs Width]({os.path.basename(figure_paths['coupling'])})")
        lines.append("")

    if "alignment" in figure_paths:
        lines += [
            f"## 4. Alignment Tolerance",
            f"",
            f"![Alignment Tolerance]({os.path.basename(figure_paths['alignment'])})",
            f"",
        ]

    if "wg_first" in figure_paths:
        lines += [
            f"## Appendix: Waveguide Cross Sections",
            f"",
            f"![First width]({os.path.basename(figure_paths['wg_first'])})",
            f"",
        ]
    if "wg_last" in figure_paths:
        lines.append(f"![Last width]({os.path.basename(figure_paths['wg_last'])})")
        lines.append("")

    report_path = _output_path("analysis_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nReport saved: {report_path}")
    return report_path


# =============================================================================
# Main Analysis
# =============================================================================

def run_analysis():
    """Run mode overlap analysis with specified parameters."""
    _ensure_output_dir()
    figure_paths = {}

    # 1. Material & calculator
    material = MaterialConfig.from_dispersion(WAVELENGTH)
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH, material=material)
    calc.configure_api(API_KEY)

    print("\n" + "=" * 50)
    print("Config Summary")
    print("=" * 50)
    print(f"Wavelength: {WAVELENGTH:.3f} um")
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
    print(f"Beam: {BEAM_DIAMETER_X:.2f} x {BEAM_DIAMETER_Y:.2f} um (diameter, elliptical)")

    fig_beam = calc.plot_gaussian_beam(
        beam,
        title=f"Elliptical Gaussian Beam ({BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} um)",
    )
    fig_beam.tight_layout()
    beam_fig_path = _output_path(
        f"gaussian_beam_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png"
    )
    fig_beam.savefig(beam_fig_path, dpi=150)
    figure_paths["beam"] = beam_fig_path
    plt.show()

    # 3. Waveguide & scan config
    scan_config = ScanConfig(width_min=WIDTH_MIN, width_max=WIDTH_MAX, width_step=WIDTH_STEP)
    wg_config = _make_wg_config()

    print(f"Width scan: {scan_config.width_list} um")
    _print_wg_summary(wg_config)

    # 4. Preview first & last waveguide
    width_list = scan_config.width_list
    if width_list.size > 0:
        figure_paths["wg_first"] = _preview_waveguide(
            calc, wg_config, float(width_list[0])
        )
        figure_paths["wg_last"] = _preview_waveguide(
            calc, wg_config, float(width_list[-1])
        )

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
    print(f"{'Width (um)':<12} {'Loss (dB)':<12} {'Efficiency (%)':<15}")
    print("-" * 40)
    for w, loss, eff in zip(width_list, losses, efficiencies):
        print(f"{w:<12.1f} {loss:<12.2f} {eff * 100:<15.2f}")

    opt_idx = np.argmin(losses)
    opt_width = width_list[opt_idx]
    print("-" * 40)
    print(
        f"Optimal: width = {opt_width:.1f} um, "
        f"loss = {losses[opt_idx]:.2f} dB, "
        f"efficiency = {efficiencies[opt_idx] * 100:.1f}%"
    )

    # 8. Plot coupling loss
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(width_list, losses, "bo-", linewidth=2, markersize=8,
            markerfacecolor="white", markeredgewidth=2)
    ax.axvline(opt_width, color="r", linestyle="--", alpha=0.5,
               label=f"Optimal: {opt_width:.1f} um")
    ax.set_xlabel("Waveguide Width (um)", fontsize=14)
    ax.set_ylabel("Coupling Loss (dB)", fontsize=14)
    ax.set_title(
        f"Coupling Loss: {BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} um "
        f"Elliptical Beam -> TFLN Waveguide",
        fontsize=12,
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    coupling_fig_path = _output_path(
        f"coupling_loss_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png"
    )
    plt.savefig(coupling_fig_path, dpi=150)
    figure_paths["coupling"] = coupling_fig_path
    plt.show()

    # 9. Alignment tolerance (optional)
    user_align = input("Run alignment tolerance scan? (y/N): ").strip().lower()
    if user_align in ("y", "yes"):
        width_input = input(f"Use width (um) [default {opt_width:.2f}]: ").strip()
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
            f"{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f} um beam",
        )
        plt.tight_layout()
        align_fig_path = _output_path(
            f"alignment_tolerance_{BEAM_DIAMETER_X:.2f}x{BEAM_DIAMETER_Y:.2f}um.png"
        )
        plt.savefig(align_fig_path, dpi=150)
        figure_paths["alignment"] = align_fig_path
        plt.show()

    # 10. Generate report
    generate_report(
        material=material,
        wg_config=wg_config,
        scan_config=scan_config,
        width_list=width_list,
        losses=losses,
        efficiencies=efficiencies,
        opt_idx=opt_idx,
        figure_paths=figure_paths,
    )

    return calc, batch_results, loss_results, scan_config


if __name__ == "__main__":
    calc, batch_results, loss_results, scan_config = run_analysis()
