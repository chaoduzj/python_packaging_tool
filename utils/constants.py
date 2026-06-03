"""
项目级共享常量与工具函数模块

本模块定义了项目中多处使用的共享常量与运行时检测函数，
避免在多个文件中重复定义。
"""

import sys

# Windows 子进程隐藏控制台窗口标志
# 在 Windows 上运行子进程时使用此标志可以隐藏控制台窗口
# 在非 Windows 平台上为 0（无效果）
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 跳过扫描的目录集合（用于遍历项目文件时）
SKIP_DIRECTORIES = frozenset(
    {
        ".venv",
        "venv",
        ".env",
        "env",  # 虚拟环境
        "build",
        "dist",
        "output",  # 构建输出
        "__pycache__",
        ".pytest_cache",  # Python 缓存
        ".git",
        ".svn",
        ".hg",  # 版本控制
        "node_modules",  # Node.js
        "site-packages",  # 已安装包
        ".idea",
        ".vscode",
        ".zed",  # IDE 配置
        "eggs",
        "*.egg-info",  # Python 包元数据
    }
)

# 常见的虚拟环境目录名
VENV_DIRECTORY_NAMES = frozenset({".venv", "venv", ".env", "env"})


# ---------------------------------------------------------------------------
#  运行时环境检测
# ---------------------------------------------------------------------------


def is_nuitka_compiled() -> bool:
    """检测是否在 Nuitka 编译后的环境中运行。

    Nuitka 不设置 sys.frozen，只提供 __compiled__ 全局变量。
    参考: https://github.com/nuitka/nuitka/blob/develop/README.rst
    """
    return "__compiled__" in dir()


def is_pyinstaller_bundled() -> bool:
    """检测是否在 PyInstaller 打包后的环境中运行。"""
    return bool(getattr(sys, "frozen", False))


def is_bundled() -> bool:
    """检测是否在任意打包/编译环境中运行（Nuitka 或 PyInstaller）。"""
    return is_nuitka_compiled() or is_pyinstaller_bundled()


def get_nuitka_containing_dir() -> str:
    """获取 Nuitka onefile 解包后的临时目录路径。

    仅在 Nuitka 编译环境中有效，否则返回空字符串。

    Returns:
        Nuitka 解包目录路径，或空字符串
    """
    if not is_nuitka_compiled():
        return ""
    try:
        return __compiled__.containing_dir  # type: ignore[name-defined] # noqa: F821
    except Exception:
        return ""
