"""
UPX 压缩器提供器 — 统一的 UPX 发现、下载和缓存管理。

从 NuitkaPackager 中提取。独立于具体打包工具。
"""

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from typing import Callable, Optional


class CompressorProvider:
    """UPX 可执行文件的发现、下载和缓存管理。"""

    UPX_VERSION = "4.2.4"

    def __init__(self, log: Callable = print):
        self.log = log

    # ------------------------------------------------------------------
    #  公共接口
    # ------------------------------------------------------------------

    def resolve(self, python_path: Optional[str] = None) -> Optional[str]:
        """解析 UPX 可执行文件路径。

        优先级：
        1. 项目 tools/ 目录中的 upx.exe
        2. 系统 PATH 中的 upx
        3. 从 GitHub 下载到本地缓存

        Returns:
            upx.exe 完整路径，未找到返回 None
        """
        # 1. 项目 tools/ 目录
        tools_upx = self._find_in_tools_dir()
        if tools_upx:
            return tools_upx

        # 2. 系统 PATH
        system_upx = shutil.which("upx")
        if system_upx:
            return system_upx

        # 3. GitHub 下载
        self.log("  正在从 GitHub 下载 UPX...")
        return self._download()

    @staticmethod
    def get_cache_dir() -> str:
        """获取 UPX 缓存目录。"""
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else:
            base = os.environ.get("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache"))
        cache_dir = os.path.join(base, "python_packaging_tool", "upx")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _find_in_tools_dir() -> Optional[str]:
        """在项目 tools/ 目录中查找 upx.exe。"""
        try:
            src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            tools_dir = os.path.join(src_dir, "tools")
            upx = os.path.join(tools_dir, "upx.exe")
            if os.path.isfile(upx):
                return upx
        except Exception:
            pass

        # 打包后：_MEIPASS（PyInstaller）/ __compiled__（Nuitka）
        try:
            if getattr(sys, "_MEIPASS", None):
                upx = os.path.join(getattr(sys, "_MEIPASS"), "tools", "upx.exe")
                if os.path.isfile(upx):
                    return upx
        except Exception:
            pass

        try:
            _nc = __compiled__  # type: ignore[name-defined] # noqa: F821
            upx = os.path.join(_nc.containing_dir, "tools", "upx.exe")  # type: ignore[union-attr]
            if os.path.isfile(upx):
                return upx
        except Exception:
            pass

        return None

    @classmethod
    def _download(cls) -> Optional[str]:
        """从 GitHub 下载 UPX 到本地缓存。"""
        cache_dir = cls.get_cache_dir()
        upx_exe = os.path.join(cache_dir, "upx.exe")
        if os.path.isfile(upx_exe):
            return upx_exe

        url = (
            f"https://github.com/upx/upx/releases/download/"
            f"v{cls.UPX_VERSION}/upx-{cls.UPX_VERSION}-win64.zip"
        )

        try:
            tmp_zip = os.path.join(tempfile.gettempdir(), "upx_download.zip")
            urllib.request.urlretrieve(url, tmp_zip)

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("upx.exe"):
                        zf.extract(name, cache_dir)
                        extracted = os.path.join(cache_dir, name)
                        if os.path.abspath(extracted) != os.path.abspath(upx_exe):
                            shutil.move(extracted, upx_exe)
                        break

            try:
                os.remove(tmp_zip)
            except Exception:
                pass

            if os.path.isfile(upx_exe):
                return upx_exe
        except Exception:
            pass

        return None
