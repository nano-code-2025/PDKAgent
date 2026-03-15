"""
Mode Overlap Analysis: Ridge Waveguide with Multiple Beam Profiles
LiTaO3 ridge waveguide (300nm ridge + 120nm slab) at 780 nm.

Compares coupling efficiency for 5 beam profiles across a range of
waveguide widths, with alignment tolerance analysis at the optimal width.
"""

import os
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

WAVELENGTH = 0.78  # um

# Ridge waveguide geometry
RIDGE_THICKNESS = 0.30  # um
SLAB_THICKNESS = 0.12   # um

# Width scan
WIDTH_MIN = 0.5
WIDTH_MAX = 4.0
WIDTH_STEP = 0.5

PLANE_SIZE = 12.0

# Beam definitions: (name, diameter_x, diameter_y or None for circular)
BEAMS = [
    ("2um",           2.0, None),
    ("3um",           3.0, None),
    ("4um",           4.0, None),
    ("1.5x2.5um",     1.5, 2.5),
    ("1x2um",         1.0, 2.0),
]

# Alignment tolerance config
ALIGN_WIDTH = 2.50       # um, waveguide width for alignment scan
ALIGN_RANGE = (0, 1)     # um
ALIGN_POINTS = 11
ALIGN_BEAMS = ["2um", "1x2um"]  # beams to run alignment scan for

OUTPUT_DIR = "results_ridge"


# =============================================================================
# Helpers
# =============================================================================

def _ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def _out(filename):
    return os.path.join(OUTPUT_DIR, filename)


# =============================================================================
# Main
# =============================================================================

def run_analysis():
    _ensure_dir(OUTPUT_DIR)
    fig_paths = {}

    # 1. Material & calculator
    material = MaterialConfig.from_dispersion(WAVELENGTH)
    calc = ModeOverlapCalculator(wavelength=WAVELENGTH, material=material)
    calc.configure_api(API_KEY)

    print("=" * 55)
    print("Ridge Waveguide Multi-Beam Coupling Analysis")
    print("=" * 55)
    print(f"Wavelength: {WAVELENGTH * 1000:.0f} nm")
    print(f"Material: {material.name} (n_o={material.n_ordinary:.4f}, n_e={material.n_extraordinary:.4f})")
    print(f"Ridge: {RIDGE_THICKNESS * 1000:.0f} nm, Slab: {SLAB_THICKNESS * 1000:.0f} nm")

    # 2. Create all beams
    beams = {}
    for name, dx, dy in BEAMS:
        if dy is None:
            cfg = GaussianBeamConfig(
                waist_radius_x=dx / 2, pol_angle=np.pi / 2,
                plane_size=PLANE_SIZE, resolution=1000,
            )
        else:
            cfg = GaussianBeamConfig(
                waist_radius_x=dx / 2, waist_radius_y=dy / 2,
                pol_angle=np.pi / 2, plane_size=PLANE_SIZE, resolution=1000,
            )
        beams[name] = calc.create_gaussian_beam(cfg)
        print(f"  Beam: {name} {'(elliptical)' if dy else '(circular)'}")

    # 3. Waveguide config & scan
    wg_config = WaveguideConfig(
        thickness=RIDGE_THICKNESS,
        width=WIDTH_MIN,
        slab_thickness=SLAB_THICKNESS,
        waveguide_type="ridge",
        sim_size_x=8.0,
        sim_size_y=PLANE_SIZE,
        min_steps_per_wvl=35,
    )
    scan_config = ScanConfig(width_min=WIDTH_MIN, width_max=WIDTH_MAX, width_step=WIDTH_STEP)
    width_list = scan_config.width_list
    print(f"Width scan: {width_list} um ({len(width_list)} points)")

    # 4. Preview waveguide at first width
    preview_solver = calc.create_mode_solver(wg_config)
    preview_solver.plot()
    plt.suptitle(f"Ridge Waveguide - Width: {WIDTH_MIN:.2f} um", fontsize=14, y=0.98)
    plt.tight_layout()
    p = _out(f"waveguide_cross_section_{WIDTH_MIN:.2f}um.png")
    plt.savefig(p, dpi=150)
    fig_paths["wg_preview"] = p
    plt.show()

    user_ok = input("Check plot and continue? (y/N): ").strip().lower()
    if user_ok not in ("y", "yes"):
        print("Stopped by user.")
        return

    # 5. Batch mode solving
    print("\nRunning batch mode simulations...")
    batch_results = calc.scan_waveguide_widths(scan_config, wg_config)

    # 6. Compute coupling for all beams
    print("Computing coupling efficiencies...")
    loss_results = calc.scan_coupling_vs_width(batch_results, beams, scan_config)

    # 7. Print results table
    print("\n" + "=" * 70)
    print("Coupling Loss (dB) vs Waveguide Width")
    print("=" * 70)
    header = f"{'Width':>8}"
    for name, _, _ in BEAMS:
        header += f" {name:>12}"
    print(header)
    print("-" * len(header))

    best = {}  # name -> (opt_width, min_loss, max_eff)
    for name, _, _ in BEAMS:
        losses = loss_results[f"{name}_loss_db"]
        effs = loss_results[f"{name}_efficiency"]
        idx = np.argmin(losses)
        best[name] = (width_list[idx], losses[idx], effs[idx])

    for i, w in enumerate(width_list):
        row = f"{w:>8.2f}"
        for name, _, _ in BEAMS:
            loss = loss_results[f"{name}_loss_db"][i]
            row += f" {loss:>12.2f}"
        print(row)

    print("-" * len(header))
    for name, _, _ in BEAMS:
        ow, ml, me = best[name]
        print(f"  {name}: optimal width = {ow:.2f} um, loss = {ml:.2f} dB, eff = {me * 100:.1f}%")

    # 8. Plot coupling loss (all beams)
    try:
        import seaborn as sns
        palette = sns.color_palette("colorblind", len(BEAMS))
    except ImportError:
        palette = plt.cm.tab10.colors

    markers = ["o", "s", "D", "^", "v"]
    fig, ax = plt.subplots(figsize=(14, 7))
    for idx, (name, _, _) in enumerate(BEAMS):
        losses = loss_results[f"{name}_loss_db"]
        ax.plot(
            1e3 * width_list, losses,
            color=palette[idx], linewidth=2,
            marker=markers[idx % len(markers)], markersize=9,
            label=name, markerfacecolor="white", markeredgewidth=2,
        )
    ax.set_xlabel("Waveguide width (nm)", fontsize=14)
    ax.set_ylabel("Coupling loss (dB)", fontsize=14)
    ax.set_title("Coupling Loss: Ridge Waveguide vs Multiple Beam Profiles", fontsize=14)
    ax.set_ylim(-0.5, 12)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=12)
    plt.tight_layout()
    p = _out("coupling_loss_multibeam.png")
    plt.savefig(p, dpi=150)
    fig_paths["coupling"] = p
    plt.show()

    # 9. Alignment tolerance
    align_scan = ScanConfig(
        width_min=WIDTH_MIN, width_max=WIDTH_MAX, width_step=WIDTH_STEP,
        shift_x_range=ALIGN_RANGE, shift_y_range=ALIGN_RANGE,
        shift_points=ALIGN_POINTS,
    )
    optimal_mode = batch_results[f"w={ALIGN_WIDTH:.2f}"]

    for beam_name in ALIGN_BEAMS:
        print(f"\nAlignment tolerance scan: {beam_name} beam @ w={ALIGN_WIDTH:.2f} um...")
        tolerance_map = calc.scan_alignment_tolerance(optimal_mode, beams[beam_name], align_scan)

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.pcolormesh(
            align_scan.shift_x_list, align_scan.shift_y_list,
            tolerance_map, cmap="Spectral_r", shading="auto",
        )
        plt.colorbar(im, ax=ax, label="Loss (dB)")
        cs = ax.contour(
            align_scan.shift_x_list, align_scan.shift_y_list,
            tolerance_map, levels=[0.5, 1, 2, 3],
            colors="white", linewidths=1, linestyles="--",
        )
        ax.clabel(cs, inline=True, fontsize=10, fmt="%.1f dB")
        ax.set_xlabel("Shift in x (um)", fontsize=12)
        ax.set_ylabel("Shift in y (um)", fontsize=12)
        ax.set_title(f"Alignment Tolerance ({beam_name} beam, w={ALIGN_WIDTH:.2f} um)", fontsize=14)
        plt.tight_layout()
        safe_name = beam_name.replace(".", "d")
        p = _out(f"alignment_{safe_name}_w{ALIGN_WIDTH:.2f}um.png")
        plt.savefig(p, dpi=150)
        fig_paths[f"align_{beam_name}"] = p
        plt.show()

    # 10. Generate report
    _generate_report(material, wg_config, width_list, loss_results, best, fig_paths)

    return calc, batch_results, loss_results


def _generate_report(material, wg_config, width_list, loss_results, best, fig_paths):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Ridge Waveguide Multi-Beam Coupling Report",
        "",
        f"**Generated:** {timestamp}",
        "",
        "## 1. Configuration",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Wavelength | {WAVELENGTH * 1000:.0f} nm |",
        f"| Material | {material.name} |",
        f"| n_ordinary | {material.n_ordinary:.6f} |",
        f"| n_extraordinary | {material.n_extraordinary:.6f} |",
        f"| n_cladding | {material.n_cladding:.6f} |",
        f"| Waveguide type | ridge |",
        f"| Ridge thickness | {RIDGE_THICKNESS * 1000:.0f} nm |",
        f"| Slab thickness | {SLAB_THICKNESS * 1000:.0f} nm |",
        f"| Width scan | {WIDTH_MIN:.1f} - {WIDTH_MAX:.1f} um, step {WIDTH_STEP:.1f} um |",
        "",
        "### Beam Profiles",
        "",
        "| Beam | Diameter X (um) | Diameter Y (um) | Type |",
        "|------|-----------------|-----------------|------|",
    ]
    for name, dx, dy in BEAMS:
        btype = "Elliptical" if dy else "Circular"
        dy_str = f"{dy:.1f}" if dy else f"{dx:.1f}"
        lines.append(f"| {name} | {dx:.1f} | {dy_str} | {btype} |")

    if "wg_preview" in fig_paths:
        lines += [
            "",
            "## 2. Waveguide Cross Section",
            "",
            f"![Waveguide]({os.path.basename(fig_paths['wg_preview'])})",
        ]

    # Coupling results table
    lines += [
        "",
        "## 3. Coupling Results",
        "",
    ]
    # Build markdown table header
    hdr = "| Width (um) |"
    sep = "|------------|"
    for name, _, _ in BEAMS:
        hdr += f" {name} (dB) |"
        sep += "------------|"
    lines.append(hdr)
    lines.append(sep)

    for i, w in enumerate(width_list):
        row = f"| {w:.2f} |"
        for name, _, _ in BEAMS:
            loss = loss_results[f"{name}_loss_db"][i]
            row += f" {loss:.2f} |"
        lines.append(row)

    lines += [
        "",
        "### Optimal Design Points",
        "",
        "| Beam | Optimal Width (um) | Loss (dB) | Efficiency (%) |",
        "|------|--------------------|-----------|----------------|",
    ]
    for name, _, _ in BEAMS:
        ow, ml, me = best[name]
        lines.append(f"| {name} | {ow:.2f} | {ml:.2f} | {me * 100:.1f} |")

    if "coupling" in fig_paths:
        lines += [
            "",
            f"![Coupling Loss]({os.path.basename(fig_paths['coupling'])})",
        ]

    # Alignment tolerance
    align_figs = [(k, v) for k, v in fig_paths.items() if k.startswith("align_")]
    if align_figs:
        lines += [
            "",
            f"## 4. Alignment Tolerance (w = {ALIGN_WIDTH:.2f} um)",
            "",
        ]
        for key, path in align_figs:
            beam_name = key.replace("align_", "")
            lines += [
                f"### {beam_name} beam",
                "",
                f"![Alignment {beam_name}]({os.path.basename(path)})",
                "",
            ]

    report_path = _out("analysis_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    run_analysis()
