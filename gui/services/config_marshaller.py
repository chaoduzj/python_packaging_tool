"""
配置编组器 — 从 UI 控件读取打包配置并组装为 PackagingConfig 数据类。

从 MainWindow 中提取，减少 view 与配置格式之间的耦合。
所有参数都是简单值（str/bool/dict），不依赖 QWidget。
"""

import os
from typing import Any, Dict, List

from core.packaging.config import PackagingConfig


class ConfigMarshaller:
    """将 MainWindow 的 UI 控件状态编组为 PackagingConfig。"""

    def marshall(
        self,
        script_path_edit: str,
        output_dir_edit: str,
        icon_path_edit: str,
        program_name_edit: str,
        python_path_edit: str,
        gcc_path_edit: str,
        is_nuitka: bool,
        is_cx_freeze: bool = False,
        onefile: bool = True,
        console: bool = False,
        clean: bool = True,
        upx: bool = False,
        use_venv: bool = True,
        version_info: Dict[str, Any] = None,
        has_version_info: bool = False,
        nuitka_advanced_options: Dict[str, Any] = None,
        exclude_modules_text: str = "",
    ) -> PackagingConfig:
        """从 UI 控件值构建类型化的打包配置。"""
        script_path = os.path.abspath(script_path_edit.strip()) if script_path_edit.strip() else ""
        project_dir = os.path.dirname(script_path) if script_path else ""

        exclude_modules: List[str] = []
        if exclude_modules_text.strip():
            exclude_modules = [
                m.strip()
                for m in exclude_modules_text.split(",")
                if m.strip()
            ]

        # 确定打包工具
        if is_cx_freeze:
            tool = "cx_freeze"
        elif is_nuitka:
            tool = "nuitka"
        else:
            tool = "pyinstaller"

        return PackagingConfig(
            script_path=script_path,
            project_dir=project_dir,
            output_dir=output_dir_edit.strip() or None,
            icon_path=icon_path_edit.strip() or None,
            program_name=program_name_edit.strip() or None,
            python_path=python_path_edit.strip() or None,
            tool=tool,
            gcc_path=gcc_path_edit.strip() or None,
            onefile=onefile,
            console=console,
            clean=clean,
            upx=upx,
            use_venv=use_venv,
            lto=True,
            python_opt=True,
            exclude_modules=exclude_modules,
            nuitka_advanced_options=nuitka_advanced_options or {},
            version_info=version_info if has_version_info else {},
        )
