"""
Mode Overlap Calculator for Thin-Film Lithium Niobate (TFLN) Waveguides

This module provides functions for calculating mode overlap between waveguide modes
and Gaussian beams using Tidy3D's mode solver. It supports various waveguide geometries
and beam profiles for fiber-to-chip coupling analysis.

Date: 2025-01-27
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any, Union

from func import init_materials, get_litao3_refractive_index, get_sio2_refractive_index

# Tidy3D imports
import tidy3d as td
from tidy3d.constants import C_0
import tidy3d.web as web
from tidy3d.plugins.mode import ModeSolver
from tidy3d.plugins.mode.web import run as run_mode_solver


# =============================================================================
# Data Classes for Configuration
# =============================================================================

@dataclass
class MaterialConfig:
    """Configuration for optical materials."""
    
    # Material name for identification
    name: str = "TFLN"
    
    # Refractive indices (at specified wavelength)
    n_ordinary: Optional[float] = None
    n_extraordinary: Optional[float] = None
    
    # Cladding refractive index
    n_cladding: Optional[float] = None
    
    # Reference wavelength (μm)
    reference_wavelength: float = 0.78
    
    @property
    def eps_ordinary(self) -> float:
        """Ordinary permittivity."""
        if self.n_ordinary is None:
            raise ValueError("n_ordinary is not set. Build from dispersion first.")
        return self.n_ordinary ** 2
    
    @property
    def eps_extraordinary(self) -> float:
        """Extraordinary permittivity."""
        if self.n_extraordinary is None:
            raise ValueError("n_extraordinary is not set. Build from dispersion first.")
        return self.n_extraordinary ** 2
    
    def get_tidy3d_medium(self, freq: float) -> td.AnisotropicMedium:
        """Create Tidy3D anisotropic medium object."""
        if self.n_ordinary is None or self.n_extraordinary is None:
            raise ValueError("Material indices are not set. Build from dispersion first.")
        return td.AnisotropicMedium(
            xx=td.Medium.from_nk(n=self.n_ordinary, k=0, freq=freq),
            yy=td.Medium.from_nk(n=self.n_extraordinary, k=0, freq=freq),
            zz=td.Medium.from_nk(n=self.n_ordinary, k=0, freq=freq),
        )
    
    def get_cladding_medium(self, freq: float) -> td.Medium:
        """Create Tidy3D medium for cladding."""
        if self.n_cladding is None:
            raise ValueError("n_cladding is not set. Build from dispersion first.")
        return td.Medium.from_nk(n=self.n_cladding, k=0, freq=freq)

    @classmethod
    def from_dispersion(cls, wavelength: float) -> "MaterialConfig":
        """Build material config from dispersive models at a wavelength."""
        init_materials()
        n_values = get_litao3_refractive_index(wavelength)
        n_sio2 = get_sio2_refractive_index(wavelength)
        return cls(
            name="LiTaO3",
            n_ordinary=float(n_values["no"]),
            n_extraordinary=float(n_values["ne"]),
            n_cladding=float(n_sio2),
            reference_wavelength=wavelength,
        )


@dataclass
class WaveguideConfig:
    """Configuration for waveguide geometry."""
    
    # Core dimensions
    thickness: float = 0.12            # Waveguide core thickness (μm)
    width: float = 0.3                 # Waveguide width (μm)
    slab_thickness: float = 0.0        # Slab thickness for ridge waveguide (μm)
    slab_width: Optional[float] = None  # Slab width in y (μm); None uses sim_size_y

    # Geometry type: "ridge" (ridge + optional slab) or "slab"
    waveguide_type: str = "ridge"
    
    # Geometry parameters
    sidewall_angle: float = 20.0       # Sidewall angle in degrees
    
    # Simulation domain
    sim_size_x: float = 8.0            # Simulation size in x (μm)
    sim_size_y: float = 12.0           # Simulation size in y (μm)
    
    # Grid resolution
    min_steps_per_wvl: int = 35        # Minimum grid steps per wavelength


@dataclass
class GaussianBeamConfig:
    """Configuration for Gaussian beam profile."""
    
    # Beam parameters
    waist_radius_x: float = 1.5        # Waist radius in x direction (μm)
    waist_radius_y: Optional[float] = None  # Waist radius in y (None = circular)
    
    # Polarization angle (rad)
    pol_angle: float = np.pi / 2       # π/2 for TE mode coupling
    
    # Profile plane size
    plane_size: float = 12.0           # Size of the profile plane (μm)
    
    # Resolution
    resolution: int = 1000             # Grid resolution for beam profile
    
    @property
    def is_astigmatic(self) -> bool:
        """Check if beam is astigmatic (elliptical)."""
        return self.waist_radius_y is not None and self.waist_radius_y != self.waist_radius_x
    
    @property
    def diameter(self) -> Union[float, Tuple[float, float]]:
        """Return beam diameter(s)."""
        if self.is_astigmatic:
            return (2 * self.waist_radius_x, 2 * self.waist_radius_y)
        return 2 * self.waist_radius_x


@dataclass  
class ScanConfig:
    """Configuration for parameter scanning."""
    
    # Waveguide width scan
    width_min: float = 0.15
    width_max: float = 0.6
    width_step: float = 0.05
    
    # Position alignment scan
    shift_x_range: Tuple[float, float] = (0, 3)
    shift_y_range: Tuple[float, float] = (0, 3)
    shift_points: int = 11
    
    @property
    def width_list(self) -> np.ndarray:
        """Generate list of waveguide widths to scan."""
        return np.arange(self.width_min, self.width_max, self.width_step)
    
    @property
    def shift_x_list(self) -> np.ndarray:
        """Generate list of x shifts."""
        return np.linspace(self.shift_x_range[0], self.shift_x_range[1], self.shift_points)
    
    @property
    def shift_y_list(self) -> np.ndarray:
        """Generate list of y shifts."""
        return np.linspace(self.shift_y_range[0], self.shift_y_range[1], self.shift_points)


# =============================================================================
# Main Calculator Class
# =============================================================================

class ModeOverlapCalculator:
    """
    Calculator for mode overlap between waveguide modes and Gaussian beams.
    
    This class provides methods for:
    - Creating Tidy3D mode solvers for waveguide structures
    - Generating Gaussian beam profiles (circular and elliptical)
    - Computing mode overlap integrals
    - Scanning coupling efficiency vs waveguide width
    - Analyzing alignment tolerance
    
    Example usage:
    -------------
    >>> calc = ModeOverlapCalculator(wavelength=0.78)
    >>> calc.configure_api("your_api_key")
    >>> 
    >>> # Set up waveguide and beam
    >>> wg_config = WaveguideConfig(thickness=0.12, width=0.3)
    >>> beam_config = GaussianBeamConfig(waist_radius_x=1.5)
    >>> 
    >>> # Run mode solver
    >>> mode_data = calc.solve_waveguide_mode(wg_config)
    >>> 
    >>> # Calculate overlap
    >>> overlap = calc.compute_overlap(mode_data, beam_config)
    """
    
    def __init__(
        self,
        wavelength: float = 0.78,
        material: Optional[MaterialConfig] = None,
    ):
        """
        Initialize the mode overlap calculator.
        
        Parameters
        ----------
        wavelength : float
            Operating wavelength in μm (default: 0.78)
        material : MaterialConfig, optional
            Material configuration (default: TFLN/LiTaO3)
        """
        self.wavelength = wavelength
        self.freq0 = C_0 / wavelength
        
        # Material configuration
        self.material = material or MaterialConfig.from_dispersion(wavelength)
        
        # Tidy3D objects
        self._core_medium = None
        self._cladding_medium = None
        
        # Cache for computed results
        self._mode_cache: Dict[str, Any] = {}
        self._beam_cache: Dict[str, Any] = {}
        
    def configure_api(self, api_key: Optional[str] = None) -> bool:
        """
        Configure Tidy3D API for cloud simulations.

        Parameters
        ----------
        api_key : str, optional
            Tidy3D API key. If None, reads from TIDY3D_API_KEY env var.

        Returns
        -------
        bool
            True if configuration successful
        """
        if api_key is None:
            api_key = os.environ.get("TIDY3D_API_KEY", "")
        if not api_key:
            print("Error: No API key provided. Set TIDY3D_API_KEY in .env or pass api_key.")
            return False
        try:
            web.configure(api_key)
            print("Tidy3D configured successfully for cloud simulations")
            return True
        except Exception as e:
            print(f"Error configuring Tidy3D: {e}")
            return False
    
    @property
    def core_medium(self) -> td.AnisotropicMedium:
        """Get or create the core waveguide medium."""
        if self._core_medium is None:
            self._core_medium = self.material.get_tidy3d_medium(self.freq0)
        return self._core_medium
    
    @property
    def cladding_medium(self) -> td.Medium:
        """Get or create the cladding medium."""
        if self._cladding_medium is None:
            self._cladding_medium = self.material.get_cladding_medium(self.freq0)
        return self._cladding_medium
    
    # -------------------------------------------------------------------------
    # Gaussian Beam Generation
    # -------------------------------------------------------------------------
    
    def create_gaussian_beam(
        self,
        config: GaussianBeamConfig,
    ) -> Union[td.GaussianBeamProfile, td.AstigmaticGaussianBeamProfile]:
        """
        Create a Gaussian beam profile.
        
        Parameters
        ----------
        config : GaussianBeamConfig
            Beam configuration
            
        Returns
        -------
        GaussianBeamProfile or AstigmaticGaussianBeamProfile
            Tidy3D beam profile object
        """
        cache_key = f"beam_{config.waist_radius_x}_{config.waist_radius_y}_{config.pol_angle}"
        
        if cache_key in self._beam_cache:
            return self._beam_cache[cache_key]
        
        if config.is_astigmatic:
            beam = td.AstigmaticGaussianBeamProfile(
                waist_sizes=(config.waist_radius_x, config.waist_radius_y),
                pol_angle=config.pol_angle,
                size=(config.plane_size, config.plane_size, 0),
                resolution=config.resolution,
                freqs=[self.freq0],
            )
        else:
            beam = td.GaussianBeamProfile(
                waist_radius=config.waist_radius_x,
                pol_angle=config.pol_angle,
                size=(config.plane_size, config.plane_size, 0),
                resolution=config.resolution,
                freqs=[self.freq0],
            )
        
        self._beam_cache[cache_key] = beam
        return beam
    
    def create_standard_beams(
        self,
        diameters: List[float] = [1, 2, 3, 4],
        elliptical: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a set of standard Gaussian beams for comparison.
        
        Parameters
        ----------
        diameters : list of float
            List of beam diameters in μm
        elliptical : list of tuples, optional
            List of (diameter_x, diameter_y) for elliptical beams
            
        Returns
        -------
        dict
            Dictionary of beam profiles keyed by description
        """
        beams = {}
        
        for d in diameters:
            config = GaussianBeamConfig(waist_radius_x=d/2)
            beams[f"{d}um"] = self.create_gaussian_beam(config)
        
        if elliptical:
            for dx, dy in elliptical:
                config = GaussianBeamConfig(waist_radius_x=dx/2, waist_radius_y=dy/2)
                beams[f"{dx}x{dy}um"] = self.create_gaussian_beam(config)
        
        return beams
    
    # -------------------------------------------------------------------------
    # Mode Solver
    # -------------------------------------------------------------------------
    
    def create_mode_solver(
        self,
        wg_config: WaveguideConfig,
    ) -> ModeSolver:
        """
        Create a mode solver for the specified waveguide configuration.
        
        Parameters
        ----------
        wg_config : WaveguideConfig
            Waveguide geometry configuration
            
        Returns
        -------
        ModeSolver
            Tidy3D mode solver object
        """
        # Create waveguide structures
        # Note: For TFLN, light propagates along z, waveguide cross-section in xy plane.
        # Ridge + slab definition follows the notebook convention.
        structures: List[td.Structure] = []
        slab_thickness = wg_config.slab_thickness or wg_config.thickness
        slab_width = wg_config.slab_width
        use_inf_y = slab_width is None or slab_width >= wg_config.sim_size_y
        slab_size_y = td.inf if use_inf_y else slab_width
        slab_center_x = wg_config.thickness / 2 - slab_thickness / 2

        slab = td.Structure(
            geometry=td.Box(
                center=(slab_center_x, 0, 0),
                size=(slab_thickness, slab_size_y, td.inf),
            ),
            medium=self.core_medium,
        )

        if wg_config.waveguide_type == "ridge":
            waveguide = td.Structure(
                geometry=td.Box(
                    center=(0, 0, 0),
                    size=(wg_config.thickness, wg_config.width, td.inf),
                ),
                medium=self.core_medium,
            )
            structures = [waveguide, slab]
        elif wg_config.waveguide_type == "slab":
            structures = [slab]
        else:
            raise ValueError("waveguide_type must be 'ridge' or 'slab'.")
        
        # Create simulation
        sim = td.Simulation(
            center=(0, 0, 0),
            size=(wg_config.sim_size_x, wg_config.sim_size_y, 1),
            grid_spec=td.GridSpec.auto(
                min_steps_per_wvl=wg_config.min_steps_per_wvl,
                wavelength=self.wavelength
            ),
            structures=structures,
            run_time=1e-12,
            medium=self.cladding_medium,
        )
        
        # Create mode solver
        mode_spec = td.ModeSpec(
            num_modes=1,
            target_neff=self.material.n_ordinary
        )
        
        mode_solver = ModeSolver(
            simulation=sim,
            plane=td.Box(
                center=(0, 0, 0),
                size=(wg_config.sim_size_x, wg_config.sim_size_y, 0)
            ),
            mode_spec=mode_spec,
            freqs=[self.freq0],
        )
        
        return mode_solver
    
    def solve_waveguide_mode(
        self,
        wg_config: WaveguideConfig,
        run_on_cloud: bool = True,
    ) -> Any:
        """
        Solve for the waveguide mode.
        
        Parameters
        ----------
        wg_config : WaveguideConfig
            Waveguide configuration
        run_on_cloud : bool
            Whether to run on Flexcompute cloud
            
        Returns
        -------
        ModeData
            Solved mode data
        """
        mode_solver = self.create_mode_solver(wg_config)
        
        if run_on_cloud:
            mode_data = run_mode_solver(mode_solver)
        else:
            mode_data = mode_solver.solve()
        
        return mode_data
    
    def scan_waveguide_widths(
        self,
        scan_config: ScanConfig,
        wg_base_config: Optional[WaveguideConfig] = None,
        data_dir: str = "data",
    ) -> Dict[str, Any]:
        """
        Run batch mode solving for multiple waveguide widths.
        
        Parameters
        ----------
        scan_config : ScanConfig
            Scan configuration
        wg_base_config : WaveguideConfig, optional
            Base waveguide configuration (width will be overridden)
        data_dir : str
            Directory to store results
            
        Returns
        -------
        dict
            Dictionary of mode results keyed by width
        """
        wg_base = wg_base_config or WaveguideConfig()
        
        mode_solvers = {}
        for w in scan_config.width_list:
            if wg_base.waveguide_type == "slab":
                wg_config = WaveguideConfig(
                    thickness=wg_base.thickness,
                    width=wg_base.width,
                    slab_thickness=wg_base.slab_thickness,
                    slab_width=w,
                    waveguide_type=wg_base.waveguide_type,
                    sidewall_angle=wg_base.sidewall_angle,
                    sim_size_x=wg_base.sim_size_x,
                    sim_size_y=wg_base.sim_size_y,
                    min_steps_per_wvl=wg_base.min_steps_per_wvl,
                )
            else:
                wg_config = WaveguideConfig(
                    thickness=wg_base.thickness,
                    width=w,
                    slab_thickness=wg_base.slab_thickness,
                    slab_width=wg_base.slab_width,
                    waveguide_type=wg_base.waveguide_type,
                    sidewall_angle=wg_base.sidewall_angle,
                    sim_size_x=wg_base.sim_size_x,
                    sim_size_y=wg_base.sim_size_y,
                    min_steps_per_wvl=wg_base.min_steps_per_wvl,
                )
            mode_solvers[f"w={w:.2f}"] = self.create_mode_solver(wg_config)
        
        # Run batch on cloud
        batch = web.Batch(simulations=mode_solvers, verbose=True)
        batch_results = batch.run(path_dir=data_dir)
        
        return batch_results
    
    # -------------------------------------------------------------------------
    # Overlap Calculation
    # -------------------------------------------------------------------------
    
    def compute_overlap(
        self,
        mode_data: Any,
        beam: Any,
    ) -> complex:
        """
        Compute the mode overlap integral between waveguide mode and Gaussian beam.
        
        Parameters
        ----------
        mode_data : ModeData
            Waveguide mode data from mode solver
        beam : GaussianBeamProfile
            Gaussian beam profile
            
        Returns
        -------
        complex
            Complex overlap integral
        """
        overlap = mode_data.outer_dot(beam.field_data).values.squeeze()
        return overlap
    
    def compute_coupling_efficiency(
        self,
        mode_data: Any,
        beam: Any,
    ) -> float:
        """
        Compute coupling efficiency (|overlap|^2).
        
        Parameters
        ----------
        mode_data : ModeData
            Waveguide mode data
        beam : GaussianBeamProfile
            Gaussian beam profile
            
        Returns
        -------
        float
            Coupling efficiency (0 to 1)
        """
        overlap = self.compute_overlap(mode_data, beam)
        return np.abs(overlap) ** 2
    
    def compute_coupling_loss_db(
        self,
        mode_data: Any,
        beam: Any,
    ) -> float:
        """
        Compute coupling loss in dB.
        
        Parameters
        ----------
        mode_data : ModeData
            Waveguide mode data
        beam : GaussianBeamProfile
            Gaussian beam profile
            
        Returns
        -------
        float
            Coupling loss in dB
        """
        eta = self.compute_coupling_efficiency(mode_data, beam)
        return -10 * np.log10(eta + 1e-15)  # Avoid log(0)
    
    def scan_coupling_vs_width(
        self,
        batch_results: Dict[str, Any],
        beams: Dict[str, Any],
        scan_config: ScanConfig,
    ) -> Dict[str, np.ndarray]:
        """
        Calculate coupling efficiency vs waveguide width for multiple beams.
        
        Parameters
        ----------
        batch_results : dict
            Mode solver results from scan_waveguide_widths
        beams : dict
            Dictionary of beam profiles
        scan_config : ScanConfig
            Scan configuration
            
        Returns
        -------
        dict
            Dictionary with coupling losses in dB for each beam
        """
        results = {name: [] for name in beams}
        
        for w in scan_config.width_list:
            mode_result = batch_results[f"w={w:.2f}"]
            for name, beam in beams.items():
                overlap = self.compute_overlap(mode_result, beam)
                results[name].append(overlap)
        
        # Convert to arrays and compute losses
        loss_results = {}
        for name, overlaps in results.items():
            eta = np.abs(np.array(overlaps)) ** 2
            loss_results[f"{name}_loss_db"] = -10 * np.log10(eta + 1e-15)
            loss_results[f"{name}_efficiency"] = eta
        
        return loss_results
    
    def scan_alignment_tolerance(
        self,
        mode_data: Any,
        beam: Any,
        scan_config: ScanConfig,
    ) -> np.ndarray:
        """
        Scan alignment tolerance by shifting mode relative to beam.
        
        Parameters
        ----------
        mode_data : ModeData
            Waveguide mode data
        beam : GaussianBeamProfile
            Gaussian beam profile
        scan_config : ScanConfig
            Scan configuration
            
        Returns
        -------
        np.ndarray
            2D array of coupling losses in dB
        """
        shift_x_list = scan_config.shift_x_list
        shift_y_list = scan_config.shift_y_list
        
        shifted_overlap = np.array([
            [
                mode_data.translated_copy(vector=(shift_x, shift_y, 0))
                .outer_dot(beam.field_data)
                .values.squeeze()
                for shift_x in shift_x_list
            ]
            for shift_y in shift_y_list
        ])
        
        coupling_eff = np.abs(shifted_overlap) ** 2
        coupling_loss_db = -10 * np.log10(coupling_eff + 1e-15)
        
        return coupling_loss_db
    
    # -------------------------------------------------------------------------
    # Visualization
    # -------------------------------------------------------------------------
    
    def plot_gaussian_beam(
        self,
        beam: Any,
        title: str = "Gaussian Beam",
        vmin: float = 0.135,
        ax: Optional[plt.Axes] = None,
    ) -> plt.Figure:
        """
        Plot Gaussian beam intensity profile.
        
        Parameters
        ----------
        beam : GaussianBeamProfile
            Beam to plot
        title : str
            Plot title
        vmin : float
            Minimum value for colormap
        ax : plt.Axes, optional
            Axes to plot on
            
        Returns
        -------
        plt.Figure
            Matplotlib figure
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.figure
        
        E_field = np.sqrt(
            np.abs(beam.field_data.Ex)**2 +
            np.abs(beam.field_data.Ey)**2 +
            np.abs(beam.field_data.Ez)**2
        ).T
        I_norm = (E_field / E_field.max()) ** 2
        
        if hasattr(I_norm, 'plot'):
            I_norm.plot(ax=ax, cmap="Spectral_r", vmin=vmin)
        else:
            im = ax.imshow(I_norm, cmap="Spectral_r", vmin=vmin)
            plt.colorbar(im, ax=ax)
        
        ax.set_title(title)
        return fig
    
    def plot_mode_field(
        self,
        mode_data: Any,
        mode_index: int = 0,
        freq_index: int = 0,
        figsize: Tuple[float, float] = (15, 5),
    ) -> plt.Figure:
        """
        Plot waveguide mode electric field distribution.
        
        Parameters
        ----------
        mode_data : ModeData
            Mode data from solver
        mode_index : int
            Mode index to plot
        freq_index : int
            Frequency index to plot
        figsize : tuple
            Figure size
            
        Returns
        -------
        plt.Figure
            Matplotlib figure
        """
        import math
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Calculate field intensity
        E_field = np.sqrt(
            np.abs(mode_data.Ex[0, :, :, freq_index, mode_index])**2 +
            np.abs(mode_data.Ey[0, :, :, freq_index, mode_index])**2 +
            np.abs(mode_data.Ez[0, :, :, freq_index, mode_index])**2
        ).T
        
        I_field = np.abs(E_field)**2
        I_norm = I_field / I_field.max()
        
        x_coords = E_field.y
        y_coords = E_field.z
        
        # Linear scale plot
        im1 = ax1.pcolormesh(x_coords, y_coords, I_norm, cmap='jet', shading='auto')
        plt.colorbar(im1, ax=ax1, label='Normalized Intensity')
        contours1 = ax1.contour(
            x_coords, y_coords, I_norm,
            levels=[1e-7, math.e**-2],
            colors='black', alpha=0.5, linewidths=1
        )
        ax1.clabel(contours1, inline=True, fontsize=12)
        ax1.set_title('Normalized Intensity')
        ax1.set_xlabel('y (μm)')
        ax1.set_ylabel('z (μm)')
        
        # Log scale plot
        I_norm_lg = np.log10(I_norm + 1e-15)
        im2 = ax2.pcolormesh(x_coords, y_coords, I_norm_lg, cmap='jet', shading='auto')
        plt.colorbar(im2, ax=ax2, label='Normalized Intensity (log10)')
        contours2 = ax2.contour(
            x_coords, y_coords, I_norm_lg,
            levels=[-7],
            colors='black', alpha=0.5, linewidths=1
        )
        ax2.clabel(contours2, inline=True, fontsize=12)
        ax2.set_title('Log10 Scale Intensity')
        ax2.set_xlabel('y (μm)')
        ax2.set_ylabel('z (μm)')
        
        plt.tight_layout()
        return fig
    
    def plot_coupling_vs_width(
        self,
        loss_results: Dict[str, np.ndarray],
        width_list: np.ndarray,
        figsize: Tuple[float, float] = (14, 7),
        show_efficiency: bool = False,
    ) -> plt.Figure:
        """
        Plot coupling loss vs waveguide width for multiple beams.
        
        Parameters
        ----------
        loss_results : dict
            Results from scan_coupling_vs_width
        width_list : np.ndarray
            Array of waveguide widths
        figsize : tuple
            Figure size
        show_efficiency : bool
            If True, also show efficiency subplot
            
        Returns
        -------
        plt.Figure
            Matplotlib figure
        """
        try:
            import seaborn as sns
            palette = sns.color_palette("colorblind", 10)
        except ImportError:
            palette = plt.cm.tab10.colors
        
        fig, ax = plt.subplots(figsize=figsize)
        
        markers = ['o', 's', 'D', '^', 'v', '<', '>', 'p', '*', 'h']
        
        loss_keys = [k for k in loss_results.keys() if k.endswith('_loss_db')]
        
        for idx, key in enumerate(loss_keys):
            label = key.replace('_loss_db', '')
            ax.plot(
                1e3 * width_list, loss_results[key],
                color=palette[idx % len(palette)],
                linewidth=2,
                marker=markers[idx % len(markers)],
                markersize=9,
                label=label,
                markerfacecolor='white',
                markeredgewidth=2
            )
        
        ax.set_xlabel("Waveguide width (nm)", fontsize=14)
        ax.set_ylabel("Coupling loss (dB)", fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=12)
        
        plt.tight_layout()
        return fig
    
    def plot_alignment_tolerance(
        self,
        coupling_loss_db: np.ndarray,
        scan_config: ScanConfig,
        beam_name: str = "Gaussian beam",
        figsize: Tuple[float, float] = (8, 6),
    ) -> plt.Figure:
        """
        Plot alignment tolerance map.
        
        Parameters
        ----------
        coupling_loss_db : np.ndarray
            2D array of coupling losses from scan_alignment_tolerance
        scan_config : ScanConfig
            Scan configuration
        beam_name : str
            Beam name for title
        figsize : tuple
            Figure size
            
        Returns
        -------
        plt.Figure
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        im = ax.pcolormesh(
            scan_config.shift_x_list,
            scan_config.shift_y_list,
            coupling_loss_db,
            cmap="Spectral_r",
            shading='auto'
        )
        
        plt.colorbar(im, ax=ax, label="Loss (dB)")
        ax.set_xlabel("Shift in x (μm)", fontsize=12)
        ax.set_ylabel("Shift in y (μm)", fontsize=12)
        ax.set_title(f"Coupling Loss ({beam_name})", fontsize=14)
        
        # Add contour lines
        contour_levels = [0.5, 1, 2, 3]
        cs = ax.contour(
            scan_config.shift_x_list,
            scan_config.shift_y_list,
            coupling_loss_db,
            levels=contour_levels,
            colors='white',
            linewidths=1,
            linestyles='--'
        )
        ax.clabel(cs, inline=True, fontsize=10, fmt='%.1f dB')
        
        plt.tight_layout()
        return fig


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_coupling_analysis(
    wavelength: float = 0.78,
    wg_thickness: float = 0.12,
    wg_width_range: Tuple[float, float, float] = (0.15, 0.6, 0.05),
    beam_diameters: List[float] = [1, 2, 3, 4],
    api_key: Optional[str] = None,
    material: Optional[MaterialConfig] = None,
) -> Dict[str, Any]:
    """
    Quick coupling analysis with default parameters.
    
    Parameters
    ----------
    wavelength : float
        Operating wavelength in μm
    wg_thickness : float
        Waveguide thickness in μm
    wg_width_range : tuple
        (min, max, step) for waveguide width scan in μm
    beam_diameters : list
        List of beam diameters to analyze in μm
    api_key : str, optional
        Tidy3D API key
    material : MaterialConfig, optional
        Material configuration
        
    Returns
    -------
    dict
        Dictionary with all results and configurations
    """
    # Initialize calculator
    calc = ModeOverlapCalculator(wavelength=wavelength, material=material)
    
    if api_key:
        calc.configure_api(api_key)
    
    # Create configurations
    scan_config = ScanConfig(
        width_min=wg_width_range[0],
        width_max=wg_width_range[1],
        width_step=wg_width_range[2],
    )
    
    wg_config = WaveguideConfig(thickness=wg_thickness)
    
    # Create beams
    beams = calc.create_standard_beams(diameters=beam_diameters)
    
    # Run width scan
    print("Running waveguide mode simulations...")
    batch_results = calc.scan_waveguide_widths(scan_config, wg_config)
    
    # Calculate coupling
    print("Computing coupling efficiencies...")
    loss_results = calc.scan_coupling_vs_width(batch_results, beams, scan_config)
    
    return {
        'calculator': calc,
        'scan_config': scan_config,
        'wg_config': wg_config,
        'beams': beams,
        'batch_results': batch_results,
        'loss_results': loss_results,
        'width_list': scan_config.width_list,
    }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example: Show how to use the module
    print("Mode Overlap Calculator for TFLN Waveguides")
    print("=" * 50)
    
    # Create calculator instance
    calc = ModeOverlapCalculator(wavelength=0.78)
    
    # Show material properties
    print(f"\nMaterial: {calc.material.name}")
    print(f"  n_ordinary: {calc.material.n_ordinary}")
    print(f"  n_extraordinary: {calc.material.n_extraordinary}")
    print(f"  n_cladding: {calc.material.n_cladding}")
    
    # Show example configurations
    print("\nExample Waveguide Configuration:")
    wg = WaveguideConfig()
    print(f"  Thickness: {wg.thickness} μm")
    print(f"  Width: {wg.width} μm")
    print(f"  Simulation size: {wg.sim_size_x} × {wg.sim_size_y} μm")
    
    print("\nExample Gaussian Beam Configuration:")
    beam = GaussianBeamConfig(waist_radius_x=1.5)
    print(f"  Waist radius: {beam.waist_radius_x} μm")
    print(f"  Diameter: {beam.diameter} μm")
    print(f"  Polarization: {'TE' if beam.pol_angle == np.pi/2 else 'TM'}")
    
    print("\nExample Scan Configuration:")
    scan = ScanConfig()
    print(f"  Width range: {scan.width_min} - {scan.width_max} μm")
    print(f"  Width step: {scan.width_step} μm")
    print(f"  Alignment scan: ±{scan.shift_x_range[1]} μm")
    
    print("\n" + "=" * 50)
    print("To run simulations, use:")
    print("  calc.configure_api('your_api_key')")
    print("  results = quick_coupling_analysis(api_key='your_key')")
