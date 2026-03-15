"""
材料色散模型和模式场可视化函数库

提供 LiTaO3、SiO2 和 SiN 的折射率色散查询函数，以及模式场可视化功能。
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
from scipy.interpolate import interp1d
from typing import Union, Dict, Optional, Tuple

# 获取当前文件所在目录，用于构建相对路径
_FUNC_DIR = os.path.dirname(os.path.abspath(__file__))
_MATERIAL_DIR = os.path.join(_FUNC_DIR, "material")

# 全局插值函数（延迟初始化）
_interp_ne: Optional[interp1d] = None
_interp_no: Optional[interp1d] = None
_interp_sio2: Optional[interp1d] = None
_interp_sin_n: Optional[interp1d] = None
_interp_sin_k: Optional[interp1d] = None


def load_litao3_dispersion(csv_path: Optional[str] = None) -> Tuple[interp1d, interp1d]:
    """
    读取LiTaO3色散表，并返回波长与折射率插值函数
    
    Parameters:
    -----------
    csv_path : str, optional
        CSV文件路径。如果为None，使用默认路径 "material/LiTaO3 300 nm ellipsometer data.csv"
    
    Returns:
    --------
    interp_ne : scipy.interpolate.interp1d
        非常折射率插值函数
    interp_no : scipy.interpolate.interp1d
        主折射率插值函数
    """
    if csv_path is None:
        csv_path = os.path.join(_MATERIAL_DIR, "LiTaO3 300 nm ellipsometer data.csv")
    else:
        # 如果是相对路径，相对于 func.py 所在目录
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(_FUNC_DIR, csv_path)
    
    df = pd.read_csv(csv_path)
    # 列名是'wavelength'，单位是nm，需要转换为um
    wl_nm = df["wavelength"].values
    wl_um = wl_nm / 1000.0  # 转换为微米
    ne = df["ne"].values
    no = df["no"].values
    interp_ne = interp1d(wl_um, ne, kind="linear", fill_value="extrapolate")
    interp_no = interp1d(wl_um, no, kind="linear", fill_value="extrapolate")
    return interp_ne, interp_no


def get_litao3_refractive_index(
    wavelength: Union[float, np.ndarray],
    interp_ne: Optional[interp1d] = None,
    interp_no: Optional[interp1d] = None
) -> Dict[str, Union[float, np.ndarray]]:
    """
    查询给定波长(um)时LiTaO3主、非常折射率
    
    Parameters:
    -----------
    wavelength : float or np.ndarray
        波长值，单位为微米(um)
    interp_ne : interp1d, optional
        非常折射率插值函数。如果为None，使用全局插值函数（需先调用 init_materials）
    interp_no : interp1d, optional
        主折射率插值函数。如果为None，使用全局插值函数（需先调用 init_materials）
    
    Returns:
    --------
    dict
        包含 'ne' 和 'no' 的字典，分别表示非常折射率和主折射率
    """
    global _interp_ne, _interp_no
    
    if interp_ne is None:
        if _interp_ne is None:
            raise RuntimeError("LiTaO3 dispersion not initialized. Call init_materials() first or pass interp_ne/interp_no.")
        interp_ne = _interp_ne
    
    if interp_no is None:
        if _interp_no is None:
            raise RuntimeError("LiTaO3 dispersion not initialized. Call init_materials() first or pass interp_ne/interp_no.")
        interp_no = _interp_no
    
    return {"ne": interp_ne(wavelength), "no": interp_no(wavelength)}


def load_sio2_dispersion(csv_path: Optional[str] = None) -> interp1d:
    """
    读取SiO2色散表，并返回插值函数
    
    Parameters:
    -----------
    csv_path : str, optional
        CSV文件路径。如果为None，使用默认路径 "material/SiO2 Malitson 1965.csv"
    
    Returns:
    --------
    interp_n : scipy.interpolate.interp1d
        SiO2折射率插值函数
    """
    if csv_path is None:
        csv_path = os.path.join(_MATERIAL_DIR, "SiO2 Malitson 1965.csv")
    else:
        # 如果是相对路径，相对于 func.py 所在目录
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(_FUNC_DIR, csv_path)
    
    df = pd.read_csv(csv_path)
    wl = df["wl"].values
    n = df["n"].values
    interp_n = interp1d(wl, n, kind="linear", fill_value="extrapolate")
    return interp_n


def get_sio2_refractive_index(
    wavelength: Union[float, np.ndarray],
    interp_n: Optional[interp1d] = None
) -> Union[float, np.ndarray]:
    """
    查询给定波长(um)时SiO2折射率
    
    Parameters:
    -----------
    wavelength : float or np.ndarray
        波长值，单位为微米(um)
    interp_n : interp1d, optional
        SiO2折射率插值函数。如果为None，使用全局插值函数（需先调用 init_materials）
    
    Returns:
    --------
    float or np.ndarray
        SiO2折射率值
    """
    global _interp_sio2
    
    if interp_n is None:
        if _interp_sio2 is None:
            raise RuntimeError("SiO2 dispersion not initialized. Call init_materials() first or pass interp_n.")
        interp_n = _interp_sio2
    
    return interp_n(wavelength)


def load_sin_dispersion(csv_path: Optional[str] = None) -> Tuple[interp1d, interp1d]:
    """
    读取SiN色散表，并返回波长与折射率(n)和消光系数(k)插值函数
    
    Parameters:
    -----------
    csv_path : str, optional
        CSV文件路径。如果为None，使用默认路径 "material/LPCVD_SiN_385nm.csv"
        如果CSV文件不存在，会自动从TXT文件转换
    
    Returns:
    --------
    interp_n : scipy.interpolate.interp1d
        折射率插值函数
    interp_k : scipy.interpolate.interp1d
        消光系数插值函数
    """
    if csv_path is None:
        csv_path = os.path.join(_MATERIAL_DIR, "LPCVD_SiN_385nm.csv")
    else:
        # 如果是相对路径，相对于 func.py 所在目录
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(_FUNC_DIR, csv_path)
    
    # 如果CSV文件不存在，尝试从TXT文件转换
    if not os.path.exists(csv_path):
        txt_path = os.path.join(_MATERIAL_DIR, "LPCVD_SiN_385nm.txt")
        if os.path.exists(txt_path):
            # 导入转换函数并执行转换
            import importlib.util
            convert_script = os.path.join(_MATERIAL_DIR, "convert_sin_txt_to_csv.py")
            if os.path.exists(convert_script):
                spec = importlib.util.spec_from_file_location("convert_sin", convert_script)
                convert_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(convert_module)
                convert_module.convert_sin_txt_to_csv(txt_path, csv_path)
            else:
                raise FileNotFoundError(
                    f"CSV文件不存在且无法自动转换: {csv_path}\n"
                    f"请运行 material/convert_sin_txt_to_csv.py 手动转换"
                )
        else:
            raise FileNotFoundError(f"SiN数据文件不存在: {csv_path} 或 {txt_path}")
    
    # 读取CSV文件
    df = pd.read_csv(csv_path)
    # 确保列名正确
    if 'wl' not in df.columns:
        raise ValueError(f"CSV文件格式错误：缺少 'wl' 列。文件: {csv_path}")
    if 'n' not in df.columns or 'k' not in df.columns:
        raise ValueError(f"CSV文件格式错误：缺少 'n' 或 'k' 列。文件: {csv_path}")
    
    wl_um = df["wl"].values
    n = df["n"].values
    k = df["k"].values
    
    interp_n = interp1d(wl_um, n, kind="linear", fill_value="extrapolate")
    interp_k = interp1d(wl_um, k, kind="linear", fill_value="extrapolate")
    return interp_n, interp_k


def get_sin_refractive_index(
    wavelength: Union[float, np.ndarray],
    interp_n: Optional[interp1d] = None,
    interp_k: Optional[interp1d] = None
) -> Dict[str, Union[float, np.ndarray]]:
    """
    查询给定波长(um)时SiN折射率和消光系数
    
    Parameters:
    -----------
    wavelength : float or np.ndarray
        波长值，单位为微米(um)
    interp_n : interp1d, optional
        折射率插值函数。如果为None，使用全局插值函数（需先调用 init_materials）
    interp_k : interp1d, optional
        消光系数插值函数。如果为None，使用全局插值函数（需先调用 init_materials）
    
    Returns:
    --------
    dict
        包含 'n' 和 'k' 的字典，分别表示折射率和消光系数
    """
    global _interp_sin_n, _interp_sin_k
    
    if interp_n is None:
        if _interp_sin_n is None:
            raise RuntimeError("SiN dispersion not initialized. Call init_materials() first or pass interp_n/interp_k.")
        interp_n = _interp_sin_n
    
    if interp_k is None:
        if _interp_sin_k is None:
            raise RuntimeError("SiN dispersion not initialized. Call init_materials() first or pass interp_n/interp_k.")
        interp_k = _interp_sin_k
    
    return {"n": interp_n(wavelength), "k": interp_k(wavelength)}


def init_materials(
    litao3_path: Optional[str] = None,
    sio2_path: Optional[str] = None,
    sin_path: Optional[str] = None
) -> None:
    """
    初始化全局材料色散插值函数
    
    建议在导入模块后调用此函数，以便后续直接使用便捷函数。
    
    Parameters:
    -----------
    litao3_path : str, optional
        LiTaO3色散数据CSV文件路径
    sio2_path : str, optional
        SiO2色散数据CSV文件路径
    sin_path : str, optional
        SiN色散数据CSV文件路径
    """
    global _interp_ne, _interp_no, _interp_sio2, _interp_sin_n, _interp_sin_k
    
    _interp_ne, _interp_no = load_litao3_dispersion(litao3_path)
    _interp_sio2 = load_sio2_dispersion(sio2_path)
    _interp_sin_n, _interp_sin_k = load_sin_dispersion(sin_path)


def plot_mode_field(mode_data, mode_index: int = 0, freq_index: int = 0) -> None:
    """
    绘制模式电场分布
    
    Parameters:
    -----------
    mode_data : tidy3d ModeData
        模式求解器返回的模式数据对象
    mode_index : int, optional
        要绘制的模式索引（默认：0）
    freq_index : int, optional
        要绘制的频率索引（默认：0）
    
    Returns:
    --------
    None
        matplotlib图形直接显示
    """
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

    # Calculate electric field and intensity data
    E_field = np.sqrt(
        np.abs(mode_data.Ex[0, :, :, freq_index, mode_index]) ** 2 +
        np.abs(mode_data.Ey[0, :, :, freq_index, mode_index]) ** 2 +
        np.abs(mode_data.Ez[0, :, :, freq_index, mode_index]) ** 2
    ).T
    E_norm = E_field / E_field.max()
    I_field = np.abs(E_field) ** 2
    I_norm = I_field / I_field.max()
    x_coords = E_field.y
    y_coords = E_field.z

    # Plot normalized electric field
    im1 = ax1.pcolormesh(x_coords, y_coords, I_norm, cmap='jet', shading='auto')
    plt.colorbar(im1, ax=ax1, label='Normalized Intensity')
    contours1 = ax1.contour(
        x_coords, y_coords, I_norm,
        levels=[1e-7, math.e ** -2],
        colors='black', alpha=0.5, linewidths=1
    )
    ax1.clabel(contours1, inline=True, fontsize=12)
    ax1.set_title('Normalized Intensity')

    # Plot log scale intensity
    I_norm_lg = np.log10(I_norm)
    im2 = ax2.pcolormesh(x_coords, y_coords, I_norm_lg, cmap='jet', shading='auto')
    plt.colorbar(im2, ax=ax2, label='Normalized Intensity (log10 scale)')
    contours2 = ax2.contour(
        x_coords, y_coords, I_norm_lg,
        levels=[-7],
        colors='black', alpha=0.5, linewidths=1
    )
    ax2.clabel(contours2, inline=True, fontsize=12)
    ax2.set_title('Log10 Scale Intensity')
    
    plt.show()

