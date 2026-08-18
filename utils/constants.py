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


# CJK 表意文字 Unicode 范围（含扩展 A/B 区，覆盖中日韩常用字与生僻字）
# - 基本区:        U+4E00 - U+9FFF        （约 2 万常用汉字）
# - 扩展 A 区:     U+3400 - U+4DBF        （罕见字、姓名用字）
# - 扩展 B 区:     U+20000 - U+2A6DF      （生僻字、古籍字）
# - 扩展 B 补遗:   U+2A6E0 - U+2B81F      （CJK Ext B 补充，含 U+2A6E6 等）
# - 扩展 C-F 区:   U+2A700 - U+2EBEF      （更生僻字）
# - 兼容表意文字:  U+F900 - U+FAFF
# 因 Python 字符串按码点迭代，U+20000 以上的字会作为单个 char 出现。
_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x20000, 0x2B81F),  # 扩展 B 区 + 补遗（合并相邻区段，简化判断）
    (0x2A700, 0x2EBEF),  # 扩展 C/D/E/F（与上面重叠无害，命中即返回）
    (0xF900, 0xFAFF),
)


def has_chinese(text: str) -> bool:
    """检查字符串中是否包含 CJK 表意文字（含基本区与扩展 A/B/C-F 区）。

    覆盖范围比 ``any('\\u4e00' <= c <= '\\u9fff' ...)`` 更广，
    能识别扩展区中的生僻字、姓名用字（如 𠮷、𫝆 等）。

    Args:
        text: 待检测字符串

    Returns:
        包含任意 CJK 字符返回 True；空字符串或无 CJK 字符返回 False
    """
    if not text:
        return False
    for char in text:
        code = ord(char)
        for low, high in _CJK_RANGES:
            if low <= code <= high:
                return True
    return False


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
