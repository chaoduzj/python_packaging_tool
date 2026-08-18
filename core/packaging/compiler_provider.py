"""
GCC 编译器提供器 — 统一的编译器发现、验证和缓存管理。

从 NuitkaPackager 中提取。独立于具体打包工具，可被 GUI 和命令行流程共用。
"""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from typing import Callable, Dict, List, Optional, Tuple

from utils.constants import CREATE_NO_WINDOW


# 在目标 Python 环境中查询 Nuitka 期望的 GCC 下载信息。
# Nuitka >= 2.1 的 getCachedDownloadedMinGW64() 中硬编码了 winlibs 下载 URL，
# 通过 inspect 解析该 URL 可兼容不同 Nuitka 版本（版本号随 Nuitka 升级变化）。
_NUITKA_GCC_INFO_SNIPPET = r'''
import inspect, json, re, struct
result = {"url": None, "cache_dir": None, "arch": None}
try:
    from nuitka.utils.AppDirs import getCacheDir
    result["cache_dir"] = getCacheDir("downloads")
except Exception:
    pass
try:
    from nuitka.utils import Download
    func = getattr(Download, "getCachedDownloadedMinGW64", None)
    if func is not None:
        src = inspect.getsource(func)
        urls = list(dict.fromkeys(re.findall(
            r'"(https://github\.com/brechtsanders/winlibs_mingw/releases/download/[^"]+)"',
            src,
        )))
        is64 = struct.calcsize("P") == 8
        for u in urls:
            if is64 and "x86_64" in u:
                result["url"] = u
                result["arch"] = "x86_64"
                break
            if not is64 and "i686" in u:
                result["url"] = u
                result["arch"] = "x86"
                break
except Exception:
    pass
print("NUITKA_GCC_INFO=" + json.dumps(result))
'''


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

    def ensure_nuitka_gcc(
        self,
        python_path: str,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[str]:
        """确保 Nuitka 期望的精确版本 GCC 已就位（仅 Windows）。

        Nuitka >= 2.1 只接受位于其版本化缓存目录中的精确版本 GCC：
            <Cache>/downloads/gcc/<arch>/<release-tag>/mingw64/bin/gcc.exe
        其他位置（包括旧版平铺的 downloads/mingw64）一律被忽略，且 Nuitka
        自带下载器没有重试机制，zip 损坏会直接 FATAL（见日志
        "Problem with the downloaded zip file"）。

        此处提前用内置下载器（多线程 + 重试 + 完整性校验）将精确版本
        GCC 就位，Nuitka 检测到 gcc.exe 已存在后会完全跳过下载环节。

        Args:
            python_path: 目标 Python 解释器路径（需已安装 Nuitka）
            cancel_check: 取消检查回调

        Returns:
            可用的 gcc.exe 路径，失败或无需处理时返回 None
        """
        if sys.platform != "win32":
            return None

        info = self._query_nuitka_gcc_info(python_path)
        if not info:
            return None

        url = info.get("url")
        arch = info.get("arch")
        cache_dir = info.get("cache_dir") or os.path.join(self.get_nuitka_cache_dir(), "downloads")

        # arm64 或老版本 Nuitka（无精确版本要求）交由 Nuitka 自行处理
        if not url or not arch:
            return None

        # 与 Nuitka getCachedDownload() 的路径推导保持一致：
        # downloads/gcc/<arch>/<url倒数第二段 release-tag>/mingw64|mingw32/bin/gcc.exe
        tag = url.rsplit("/", 2)[1]
        mingw_name = "mingw64" if arch == "x86_64" else "mingw32"
        target_dir = os.path.join(cache_dir, "gcc", arch, tag)
        gcc_exe = os.path.join(target_dir, mingw_name, "bin", "gcc.exe")

        if os.path.isfile(gcc_exe):
            return gcc_exe

        # 清理残留的损坏 zip：Nuitka 发现 zip 存在但 gcc 缺失时会直接解压，
        # 一旦损坏即 FATAL 且不会重试
        zip_path = os.path.join(target_dir, os.path.basename(url))
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass

        self.log("正在预置 Nuitka 精确版本的 GCC 工具链（避免 Nuitka 自动下载失败）...")

        # 延迟导入，避免 requests 成为不必要的模块级依赖
        from utils.gcc_downloader import GCCDownloader

        downloader = GCCDownloader(
            log_callback=self.log,
            cancel_check=cancel_check or (lambda: False),
        )
        mingw_path = downloader.download_from_url(url, target_dir)

        if mingw_path and os.path.isfile(gcc_exe):
            self.log(f"✓ Nuitka 专用 GCC 已就位: {gcc_exe}")
            return gcc_exe

        self.log("⚠️ GCC 预置失败，将由 Nuitka 自行下载（网络不稳定时可能失败）")
        return None

    def _query_nuitka_gcc_info(self, python_path: str) -> Optional[Dict[str, Optional[str]]]:
        """从目标 Python 环境中查询 Nuitka 期望的 GCC 下载 URL 和缓存目录。

        Returns:
            {"url": ..., "cache_dir": ..., "arch": ...} 或 None
        """
        try:
            result = subprocess.run(
                [python_path, "-c", _NUITKA_GCC_INFO_SNIPPET],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            if line.startswith("NUITKA_GCC_INFO="):
                try:
                    return json.loads(line[len("NUITKA_GCC_INFO="):])
                except ValueError:
                    return None
        return None

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
