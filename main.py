"""
Python打包工具 - 主入口

简单易用的Python脚本打包工具，支持PyInstaller和Nuitka两种打包方式。
"""

# Early startup error capture for compiled exe (console disabled mode)
import os
import sys

# 抑制第三方库（Pillow 等）在 import 扫描时产生的 UserWarning 噪声
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="PIL")

if getattr(sys, "frozen", False) or "__compiled__" in dir():
    import datetime

    _exe_dir = os.path.dirname(sys.executable)
    try:
        sys.stderr = open(os.path.join(_exe_dir, "error.log"), "w", encoding="utf-8")
        sys.stdout = sys.stderr
    except Exception:
        pass
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from utils.constants import get_nuitka_containing_dir, is_bundled, is_nuitka_compiled
from version import APP_TITLE


def _find_icon() -> Optional[str]:
    """
    查找应用程序图标路径。

    按优先级搜索：Nuitka onefile 解包目录 > PyInstaller临时目录 > exe目录 > 工作目录 > 开发目录
    """
    icon_name = "icon.ico"
    search_paths = []

    if is_bundled():
        # Nuitka onefile 会将数据文件解包到 __compiled__.containing_dir
        if is_nuitka_compiled():
            nuitka_dir = get_nuitka_containing_dir()
            if nuitka_dir:
                search_paths.extend(
                    [
                        os.path.join(nuitka_dir, icon_name),
                        os.path.join(nuitka_dir, "resources", "icons", icon_name),
                    ]
                )

        # PyInstaller 打包模式
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            search_paths.extend(
                [
                    os.path.join(meipass, icon_name),
                    os.path.join(meipass, "resources", "icons", icon_name),
                ]
            )

        search_paths.extend(
            [
                os.path.join(exe_dir, icon_name),
                os.path.join(exe_dir, "resources", "icons", icon_name),
                os.path.join(os.getcwd(), icon_name),
                os.path.join(os.getcwd(), "resources", "icons", icon_name),
            ]
        )
    else:
        # 开发模式
        project_root = os.path.dirname(os.path.abspath(__file__))
        search_paths.append(os.path.join(project_root, "resources", "icons", icon_name))

    for path in search_paths:
        if os.path.exists(path):
            return path
    return None


def _create_icon(icon_path: Optional[str]) -> Optional[QIcon]:
    """创建QIcon对象，路径无效时返回None"""
    if not icon_path:
        return None
    icon = QIcon(icon_path)
    return icon if not icon.isNull() else None


def main() -> None:
    """主程序入口"""
    try:
        app = QApplication(sys.argv)

        # 设置应用程序图标（窗口标题栏 + 任务栏）
        icon = _create_icon(_find_icon())
        if icon:
            app.setWindowIcon(icon)

        # 创建并显示主窗口
        window = MainWindow()
        window.setWindowTitle(APP_TITLE)
        if icon:
            window.setWindowIcon(icon)
        window.show()

        # Windows: 窗口 show 之后再次设置图标，确保任务栏按钮关联正确
        if icon and sys.platform == "win32":
            app.setWindowIcon(icon)
            window.setWindowIcon(icon)

        sys.exit(app.exec())

    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"程序发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
