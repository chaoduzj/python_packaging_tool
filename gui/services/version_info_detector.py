"""
版本信息检测器 — 从项目源文件中自动检测版本号、版权、产品名等。

从 MainWindow 中提取，支持独立测试（输入文件内容字符串，输出 dict）。
"""

import datetime
import os
import re
from typing import Dict, List

from utils.constants import SKIP_DIRECTORIES


class VersionInfoDetector:
    """从项目目录/脚本中自动检测版本信息。"""

    @staticmethod
    def _make_skip_dirs() -> set:
        return set(SKIP_DIRECTORIES) | {".tox", ".pytest_cache", "egg-info", ".eggs"}

    def detect(
        self, project_dir: str, script_path: str
    ) -> Dict[str, str]:
        """从项目目录和脚本路径检测版本信息。

        Args:
            project_dir: 项目根目录路径（可为空字符串）
            script_path: 主脚本路径（可为空字符串）

        Returns:
            包含 product_name, version, copyright 等字段的字典
        """
        detected_info: Dict[str, str] = {
            "product_name": "",
            "product_name_en": "",
            "company_name": "",
            "file_description": "",
            "file_description_en": "",
            "copyright": "",
            "version": "",
        }

        files_to_search: List[str] = []
        skip_dirs = self._make_skip_dirs()

        # 1. 从项目目录查找 version.py / main.py
        if project_dir and os.path.isdir(project_dir):
            version_files: List[str] = []
            main_files: List[str] = []

            root_version = os.path.join(project_dir, "version.py")
            root_main = os.path.join(project_dir, "main.py")
            if os.path.exists(root_version):
                version_files.append(root_version)
            if os.path.exists(root_main):
                main_files.append(root_main)

            for root, dirs, files in os.walk(project_dir):
                dirs[:] = [
                    d for d in dirs
                    if d not in skip_dirs and not d.startswith(".")
                ]
                if "version.py" in files:
                    vf_path = os.path.join(root, "version.py")
                    if vf_path not in version_files:
                        version_files.append(vf_path)
                if "main.py" in files:
                    mf_path = os.path.join(root, "main.py")
                    if mf_path not in main_files:
                        main_files.append(mf_path)

            if version_files:
                files_to_search.extend(version_files)
            elif main_files:
                files_to_search.extend(main_files)

        # 2. 从脚本文件本身查找
        if not files_to_search and script_path and os.path.isfile(script_path):
            if script_path.lower().endswith((".py", ".pyw")):
                files_to_search.append(script_path)

        if not files_to_search:
            return detected_info

        # 从文件中提取
        for target_file in files_to_search:
            self._extract_from_file(target_file, detected_info)

        return detected_info

    # ------------------------------------------------------------------
    #  内部提取逻辑
    # ------------------------------------------------------------------

    def _extract_from_file(
        self, filepath: str, info: Dict[str, str]
    ) -> None:
        """从单个 Python 文件中提取版本信息字段。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        if not info["version"]:
            info["version"] = self._extract_version(content)

        if not info["copyright"]:
            info["copyright"] = self._extract_copyright(content)

        if not info["product_name"]:
            info["product_name"] = self._extract_app_name(content)

        if not info["product_name"] and not info["product_name_en"]:
            info["product_name_en"] = self._extract_app_name_en(content)

        if not info["file_description"]:
            info["file_description"] = self._extract_description(content)

        if not info["file_description"] and not info["file_description_en"]:
            info["file_description_en"] = self._extract_description_en(content)

        if not info["copyright"]:
            info["copyright"] = self._extract_copyright_from_author(content)

    @staticmethod
    def _extract_version(content: str) -> str:
        for var in ("VERSION", "__version__"):
            for quote in ('"', "'"):
                pattern = rf"{re.escape(var)}\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(1)
        return ""

    @staticmethod
    def _extract_copyright(content: str) -> str:
        for quote in ('"', "'"):
            # f-string 格式
            pattern = rf"COPYRIGHT\s*=\s*f{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                text = match.group(1)
                if "{AUTHOR}" in text:
                    author_match = re.search(
                        r'AUTHOR\s*=\s*["\']([^"\']+?)["\']', content
                    )
                    author = author_match.group(1) if author_match else ""
                    text = text.replace("{AUTHOR}", author)
                return text

            # 普通字符串
            pattern = rf"COPYRIGHT\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _extract_app_name(content: str) -> str:
        for quote in ('"', "'"):
            pattern = rf"APP_NAME\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _extract_app_name_en(content: str) -> str:
        for quote in ('"', "'"):
            pattern = rf"APP_NAME_EN\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _extract_description(content: str) -> str:
        for quote in ('"', "'"):
            pattern = rf"(?<!_)DESCRIPTION\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _extract_description_en(content: str) -> str:
        for quote in ('"', "'"):
            pattern = rf"DESCRIPTION_EN\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _extract_copyright_from_author(content: str) -> str:
        for quote in ('"', "'"):
            pattern = rf"AUTHOR\s*=\s*{re.escape(quote)}(.*?){re.escape(quote)}"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                author = match.group(1)
                year = datetime.datetime.now().year
                return f"Copyright © {year} {author}"
        return ""
