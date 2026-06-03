"""
GCC 编译器提供器 — 统一的编译器发现、验证和缓存管理。

从 NuitkaPackager 中提取。独立于具体打包工具，可被 GUI 和命令行流程共用。
"""

import os
import shutil
import subprocess
import sys
import zipfile
from typing import Callable, List, Optional, Tuple

from utils.constants import CREATE_NO_WINDOW


class CompilerProvider:
    """GCC/MinGW 编译器发现、验证和缓存管理。

    供 NuitkaPackager 和 GUI 的 GCC 配置流程共用。
    """

    def __init__(self, log: Callable = print):
        self.log = log

    # ------------------------------------------------------------------
    #  公共接口
    # ------------------------------------------------------------------

    def resolve(self, gcc_hint: Optional[str] = None) -> Optional[str]:
        """解析 GCC 可执行文件路径。

        优先级：
        1. gcc_hint（用户指定的路径）
        2. Nuitka 缓存中的 mingw64
        3. 系统 PATH 中的 gcc
        4. 常见 MinGW 安装位置

        Returns:
            gcc.exe 的完整路径，未找到返回 None
        """
        # 1. 用户指定
        if gcc_hint:
            resolved = self._resolve_executable(gcc_hint)
            if resolved and self.verify(resolved)[0]:
                return resolved

        # 2. Nuitka 缓存
        cached = self._find_cached()
        if cached:
            return cached

        # 3. 系统 PATH
        system_gcc = self._find_system()
        if system_gcc:
            return system_gcc

        return None

    def verify(self, gcc_path: str) -> Tuple[bool, str]:
        """验证 GCC 可执行文件是否可用。

        Returns:
            (是否可用, 版本字符串或错误信息)
        """
        try:
            result = subprocess.run(
                [gcc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return True, result.stdout.strip().split("\n")[0]
            return False, result.stderr
        except Exception as e:
            return False, str(e)

    def extract_zip(self, zip_path: str, extract_dir: str) -> Optional[str]:
        """解压 GCC 工具链 zip 包并返回 mingw64 目录路径。"""
        try:
            self.log(f"解压 GCC 工具链: {zip_path}")
            with zipfile.ZipFile(zip_path, "r") as zf:
                top_dirs = {name.split("/")[0] for name in zf.namelist() if name.split("/")[0]}
                zf.extractall(extract_dir)

            for top_dir in top_dirs:
                mingw_path = os.path.join(extract_dir, top_dir)
                if os.path.isdir(mingw_path):
                    gcc_exe = os.path.join(mingw_path, "bin", "gcc.exe")
                    if os.path.isfile(gcc_exe):
                        self.log(f"✓ GCC 工具链解压成功: {mingw_path}")
                        return mingw_path

            bin_path = os.path.join(extract_dir, "bin")
            if os.path.isdir(bin_path) and os.path.isfile(os.path.join(bin_path, "gcc.exe")):
                return extract_dir

            self.log("⚠️ 未找到 GCC 可执行文件")
            return None
        except Exception as e:
            self.log(f"⚠️ 解压 GCC 失败: {e}")
            return None

    @staticmethod
    def get_nuitka_cache_dir() -> str:
        """获取 Nuitka 缓存根目录。"""
        if sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local"))
            return os.path.join(local, "Nuitka", "Nuitka", "Cache")
        return os.path.join(os.path.expanduser("~"), ".cache", "Nuitka")

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _resolve_executable(self, gcc_path: str) -> Optional[str]:
        """解析 GCC 路径（目录 → 查找 gcc.exe；文件 → 直接返回）。"""
        if os.path.isfile(gcc_path):
            return gcc_path
        if os.path.isdir(gcc_path):
            for sub in ("bin/gcc.exe", "gcc.exe", "mingw64/bin/gcc.exe", "mingw32/bin/gcc.exe"):
                path = os.path.join(gcc_path, sub)
                if os.path.isfile(path):
                    return path
            for root, dirs, files in os.walk(gcc_path):
                if "gcc.exe" in files:
                    return os.path.join(root, "gcc.exe")
                if root[len(gcc_path):].count(os.sep) >= 3:
                    dirs[:] = []
        return None

    def _find_cached(self) -> Optional[str]:
        """在 Nuitka 缓存目录中搜索 mingw64。"""
        downloads_dir = os.path.join(self.get_nuitka_cache_dir(), "downloads")
        if not os.path.isdir(downloads_dir):
            return None

        for root, dirs, files in os.walk(downloads_dir):
            if "gcc.exe" in files:
                gcc_exe = os.path.join(root, "gcc.exe")
                is_valid, ver = self.verify(gcc_exe)
                if is_valid:
                    self.log(f"找到缓存的 GCC: {gcc_exe} ({ver})")
                    return gcc_exe

        return None

    @staticmethod
    def _find_system() -> Optional[str]:
        """在系统 PATH 和常见位置查找 GCC。"""
        result = shutil.which("gcc")
        if result:
            return result
        for path in (
            r"C:\mingw64\bin\gcc.exe",
            r"C:\mingw-w64\mingw64\bin\gcc.exe",
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\TDM-GCC-64\bin\gcc.exe",
        ):
            if os.path.exists(path):
                return path
        return None
