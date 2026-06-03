"""
图标自动发现器 — 扫描项目目录，按优先级找到图标文件。

从 MainWindow 中提取。纯文件系统操作，无 Qt 依赖。
"""

import os
from typing import List, Optional, Tuple


class IconAutoLoader:
    """扫描项目目录，按优先级自动发现图标文件。"""

    # 支持的图标格式
    SUPPORTED_FORMATS: Tuple[str, ...] = (".ico", ".png", ".svg", ".bmp", ".jpg", ".jpeg")

    def find_icon(self, project_dir: str) -> Optional[str]:
        """在项目目录中按优先级扫描图标文件。

        优先级：
        1. 项目根目录下的特定文件名（icon.ico, app.ico, logo.ico...）
        2. 资源子目录下的特定文件名
        3. 项目根目录下任意 .ico 文件
        4. 项目根目录下任意 .png 文件
        5. 资源子目录下任意图标文件

        Returns:
            图标文件的绝对路径，未找到返回 None
        """
        if not os.path.isdir(project_dir):
            return None

        # 1. 精确文件名匹配（项目根目录）
        for name in ("icon.ico", "app.ico", "logo.ico",
                      "Icon.ico", "APP.ico", "LOGO.ico",
                      "icon.png", "app.png", "logo.png",
                      "Icon.png", "APP.png", "LOGO.png"):
            path = os.path.normpath(os.path.join(project_dir, name))
            if os.path.isfile(path):
                return path

        # 2. 精确文件名匹配（子目录）
        for subdir in ("resources/icons", "resources", "icons", "assets"):
            for name in ("icon.ico", "icon.png"):
                path = os.path.normpath(os.path.join(project_dir, subdir, name))
                if os.path.isfile(path):
                    return path

        # 3. 项目根目录中任意 .ico / .png
        found = self._find_any_in_dir(project_dir)
        if found:
            return found

        # 4. 子目录中任意图标
        for subdir in ("resources/icons", "resources", "icons", "assets"):
            sub_path = os.path.join(project_dir, subdir)
            if os.path.isdir(sub_path):
                found = self._find_any_in_dir(sub_path)
                if found:
                    return found

        return None

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    @classmethod
    def _find_any_in_dir(cls, directory: str) -> Optional[str]:
        """在目录中查找任意受支持的图标文件。

        按格式优先级: .ico > .png > .svg > .bmp > .jpg > .jpeg
        """
        by_ext: dict = {}
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item.lower())[1]
                    if ext in cls.SUPPORTED_FORMATS:
                        by_ext.setdefault(ext, []).append(item_path)
        except OSError:
            return None

        for ext in cls.SUPPORTED_FORMATS:
            if ext in by_ext and by_ext[ext]:
                return os.path.normpath(by_ext[ext][0])
        return None

    @staticmethod
    def get_relative_path(absolute_path: str, base_dir: str) -> str:
        """获取相对于项目目录的路径（用于日志显示）。"""
        try:
            return os.path.relpath(absolute_path, base_dir)
        except ValueError:
            return absolute_path
