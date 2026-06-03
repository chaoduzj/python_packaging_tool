"""
打包器协调模块

本模块作为打包流程的顶层协调器，负责：
- 协调各个子模块完成打包任务
- 管理打包流程的整体逻辑
- 提供统一的打包接口

子模块：
- analyzer: 依赖分析
- packaging: 打包相关工具（虚拟环境、依赖安装、图标处理、打包器等）
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.dependency_analyzer import DependencyAnalyzer
from core.packaging.config import PackagingConfig
from core.packaging.dependency_installer import DependencyInstaller
from core.packaging.icon_processor import IconProcessor
from core.packaging.network_utils import NetworkUtils
from core.packaging.nuitka_packager import NuitkaPackager
from core.packaging.pipeline import PackagingPipeline
from core.packaging.pipeline_steps import (
    BuildExecuteStep,
    ChinesePathCheckStep,
    ConfigEnhanceStep,
    DataFileDetectStep,
    DependencyAnalysisStep,
    DependencyInstallStep,
    IconInjectStep,
    IconProcessingStep,
    OutputDirStep,
    PackagingToolInstallStep,
    PythonDiscoveryStep,
    QtFrameworkDetectStep,
    TempCleanupStep,
    VenvSetupStep,
    VersionInfoStep,
    VersionPostProcessStep,
)
from core.packaging.pyinstaller_packager import PyInstallerPackager
from core.packaging.venv_manager import VenvManager
from core.version_info import RceditHandler, VersionInfoHandler, WindowsResourceHandler
from utils.dependency_manager import DependencyManager
from utils.python_finder import PythonFinder


class Packager:
    """
    打包器协调类

    作为高层协调器，将具体任务委托给各个子模块处理。
    保持与原有接口兼容。
    """

    def __init__(self):
        """初始化打包器及所有子模块"""
        # 工具类
        self.python_finder = PythonFinder()
        self.dependency_manager = DependencyManager()

        # 分析器
        self.dependency_analyzer = DependencyAnalyzer()

        # 打包子模块
        self.venv_manager = VenvManager()
        self.dependency_installer = DependencyInstaller()
        self.icon_processor = IconProcessor()
        self.network_utils = NetworkUtils()
        self.version_info_handler = VersionInfoHandler()
        self.windows_resource_handler = WindowsResourceHandler()
        self.rcedit_handler = RceditHandler()
        self.pyinstaller_packager = PyInstallerPackager()
        self.nuitka_packager = NuitkaPackager()

        # 回调函数
        self.log: Callable = print
        self.cancel_flag: Optional[Callable] = None
        self.process_callback: Optional[Callable] = None

        # 状态
        self._last_exe_path: Optional[str] = None

    # ------------------------------------------------------------------
    #  Pipeline 构建（新架构 — 渐进迁移中）
    # ------------------------------------------------------------------

    def build_pipeline(self) -> PackagingPipeline:
        """构建完整打包流水线（与传统 package() 严格等价）。

        16 个 Step 对应 package() 的 12 步 + _do_package 的 5 个后处理关注点。
        每个 Step 委托 Packager 的已验证方法，行为与传统路径一致。
        """
        return PackagingPipeline(
            [
                # package() 步骤 1-11
                PythonDiscoveryStep(self),
                VenvSetupStep(self),
                ChinesePathCheckStep(self),
                OutputDirStep(self),
                QtFrameworkDetectStep(self.dependency_analyzer),
                DependencyAnalysisStep(self),
                DependencyInstallStep(self),
                PackagingToolInstallStep(self.dependency_installer),
                IconProcessingStep(self),
                VersionInfoStep(self),
                DataFileDetectStep(self),
                # package() 步骤 12（_do_package 拆解为 5 个后处理 Step）
                ConfigEnhanceStep(self),
                IconInjectStep(self),
                BuildExecuteStep(self),
                VersionPostProcessStep(self),
                TempCleanupStep(self),
            ]
        )

    def package_via_pipeline(
        self,
        config: Dict,
        log_callback: Optional[Callable] = None,
        cancel_flag: Optional[Callable] = None,
        process_callback: Optional[Callable] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """通过完整 Pipeline 执行打包（新架构主入口）。

        运行 build_pipeline() 的 16 个 Step，与传统 package() 严格等价。
        各 Step 委托 Packager 的已验证方法，行为一致。
        """
        if log_callback:
            self._set_log_callback(log_callback)
        if cancel_flag:
            self._set_cancel_flag(cancel_flag)
        if process_callback:
            self._set_process_callback(process_callback)

        try:
            # 规范化配置（与旧 package() 一致：PackagingConfig → dict）
            if isinstance(config, PackagingConfig):
                config = config.as_dict()

            pipeline = self.build_pipeline()
            context: Dict[str, Any] = {
                "config": config,
                "log": self.log,
                "cancelled": self._is_cancelled,
            }
            result = pipeline.run(context)

            success = result.get("success", False)
            message = result.get("message", "")
            return success, message, self._last_exe_path
        except Exception as e:
            self.log(f"打包异常: {e}")
            import traceback

            self.log(traceback.format_exc())
            return False, f"打包过程出错: {str(e)}", None

    def _set_log_callback(self, callback: Callable) -> None:
        """设置日志回调到所有子模块"""
        self.log = callback
        self.dependency_analyzer.log = callback
        self.dependency_manager.log = callback
        self.venv_manager.set_log_callback(callback)
        self.dependency_installer.set_log_callback(callback)
        self.icon_processor.set_log_callback(callback)
        self.network_utils.set_log_callback(callback)
        self.version_info_handler.log = callback
        self.windows_resource_handler.log = callback
        self.rcedit_handler.log = callback
        self.pyinstaller_packager.set_log_callback(callback)
        self.nuitka_packager.set_log_callback(callback)

    def _set_cancel_flag(self, cancel_flag: Callable) -> None:
        """设置取消标志到所有子模块"""
        self.cancel_flag = cancel_flag
        self.dependency_installer.set_cancel_flag(cancel_flag)
        self.pyinstaller_packager.set_cancel_flag(cancel_flag)
        self.nuitka_packager.set_cancel_flag(cancel_flag)

    def _set_process_callback(self, callback: Callable) -> None:
        """设置进程回调到所有子模块"""
        self.process_callback = callback
        self.pyinstaller_packager.set_process_callback(callback)
        self.nuitka_packager.set_process_callback(callback)

    def _get_python_path(self, config: Dict) -> Tuple[Optional[str], str]:
        """
        获取 Python 解释器路径（不处理虚拟环境，仅获取基础解释器）

        优先级：
        1. 用户在配置中手动指定的路径（经过有效性校验）
        2. 当前运行的解释器（仅在非打包环境下）
        3. 通过 PythonFinder 在系统中搜索

        Returns:
            (python_path, error_message) 元组。
            成功时 python_path 为有效路径、error_message 为空字符串；
            失败时 python_path 为 None、error_message 为描述性错误信息。
        """
        # 1. 优先使用配置指定的解释器
        python_path = config.get("python_path") or config.get("python")
        if python_path and os.path.exists(python_path):
            # 即使用户手动指定，也要验证它不是打包环境中的临时文件
            if PythonFinder.is_valid_python_interpreter(python_path):
                return python_path, ""
            else:
                self.log(f"警告: 指定的 Python 路径不是有效的解释器: {python_path}")

        # 2. 检测是否处于 PyInstaller/Nuitka 打包后的环境中
        if PythonFinder.is_bundled_environment():
            # self.log(
            #     "检测到当前运行在打包环境中，sys.executable 不可用于创建虚拟环境"
            # )
            # self.log(f"  sys.executable = {sys.executable}")
            self.log("正在搜索系统中安装的 Python 解释器...")

            finder = PythonFinder()
            system_python = finder.find_python()
            if system_python:
                self.log(f"✓ 找到系统 Python: {system_python}")
                return system_python, ""
            else:
                error_msg = (
                    "未在系统中找到可用的 Python 解释器。\n\n"
                    "请在工具界面的「Python路径」中手动指定系统安装的 Python 解释器路径\n"
                    "（例如 C:\\Python311\\python.exe）。\n\n"
                    "如果尚未安装 Python，请先从 https://www.python.org 下载安装，\n"
                    "安装时请勾选「Add Python to PATH」。"
                )
                self.log("错误: 未在系统中找到可用的 Python 解释器")
                self.log("请在工具界面中手动指定 Python 路径")
                return None, error_msg

        # 3. 非打包环境，使用当前解释器
        return sys.executable, ""

    def _setup_venv_if_needed(
        self,
        config: Dict,
        base_python_path: str,
    ) -> str:
        """
        根据配置设置虚拟环境

        如果 use_venv 为 True：
        1. 检查项目目录下是否存在虚拟环境（.venv/venv）
        2. 如果不存在则创建
        3. 安装依赖（从 requirements.txt 或分析项目）

        Args:
            config: 打包配置
            base_python_path: 基础 Python 解释器路径

        Returns:
            最终使用的 Python 解释器路径
        """
        use_venv = config.get("use_venv", False)

        if not use_venv:
            self.log("未启用虚拟环境，使用指定的 Python 解释器")
            # 验证基础 Python 解释器是否存在
            if not os.path.exists(base_python_path):
                self.log(f"错误: 指定的 Python 解释器不存在: {base_python_path}")
                raise FileNotFoundError(f"Python 解释器不存在: {base_python_path}")
            return base_python_path

        project_dir = config.get("project_dir")
        if not project_dir:
            script_path = config.get("script_path", "")
            project_dir = os.path.dirname(script_path) if script_path else None

        if not project_dir or not os.path.isdir(project_dir):
            self.log("警告: 无法确定项目目录，跳过虚拟环境设置")
            return base_python_path

        self.log("\n" + "=" * 50)
        self.log("虚拟环境设置")
        self.log("=" * 50)

        # 验证基础 Python 解释器路径
        if not os.path.exists(base_python_path):
            self.log(f"错误: 基础 Python 解释器不存在: {base_python_path}")
            self.log("将无法创建虚拟环境，请检查 Python 安装")
            raise FileNotFoundError(f"Python 解释器不存在: {base_python_path}")

        self.log(f"基础 Python 解释器: {base_python_path}")

        # 1. 检查是否存在虚拟环境
        existing_venv = self.venv_manager.check_existing_venv(project_dir)
        venv_python: Optional[str] = None
        active_venv_path: Optional[str] = None

        if existing_venv:
            self.log(f"✓ 检测到现有虚拟环境: {existing_venv}")
            venv_python = self.venv_manager.get_venv_python(existing_venv)
            active_venv_path = existing_venv

            # 验证现有虚拟环境的有效性
            if not os.path.exists(venv_python):
                self.log(f"警告: 现有虚拟环境的 Python 解释器不存在: {venv_python}")
                self.log("尝试验证虚拟环境...")
                if not self.venv_manager.validate_venv(existing_venv, verbose=True):
                    self.log("现有虚拟环境无效，将创建新的虚拟环境")
                    existing_venv = None
                    venv_python = None
                    active_venv_path = None

        if not existing_venv:
            # 创建新的虚拟环境
            self.log("未检测到有效的虚拟环境，正在创建...")
            venv_path = self.venv_manager.setup_venv(
                project_dir, base_python_path, venv_name=".venv"
            )

            if not venv_path:
                self.log("警告: 虚拟环境创建失败，使用原始 Python 解释器")
                return base_python_path

            self.log(f"✓ 虚拟环境创建成功: {venv_path}")
            venv_python = self.venv_manager.get_venv_python(venv_path)
            active_venv_path = venv_path

            # 再次验证虚拟环境是否真的可用
            if not os.path.exists(venv_python):
                self.log(f"错误: 虚拟环境创建后 Python 解释器仍不存在: {venv_python}")
                self.log("虚拟环境创建失败，使用原始 Python 解释器")
                return base_python_path

            # 升级 pip
            if not self.venv_manager.upgrade_pip(venv_path):
                self.log("警告: pip 升级失败，但将继续使用虚拟环境")

        # 最终验证
        if not venv_python or not os.path.exists(venv_python):
            self.log(f"错误: 虚拟环境 Python 解释器不存在: {venv_python}")
            self.log("详细诊断信息:")
            if active_venv_path:
                self.venv_manager.get_venv_python(active_venv_path, verify=True)
            self.log("回退到使用原始 Python 解释器")
            return base_python_path

        self.log(f"✓ 将使用虚拟环境 Python: {venv_python}")

        # 2. 安装依赖
        self._install_venv_dependencies(project_dir, venv_python, config)

        return venv_python

    def _install_venv_dependencies(
        self,
        project_dir: str,
        venv_python: str,
        config: Dict,
    ) -> None:
        """
        在虚拟环境中安装依赖

        优先使用 requirements.txt，否则从项目中分析提取依赖

        Args:
            project_dir: 项目目录
            venv_python: 虚拟环境 Python 解释器路径
            config: 打包配置
        """
        requirements_file = os.path.join(project_dir, "requirements.txt")

        if os.path.exists(requirements_file):
            # 使用 requirements.txt 安装依赖
            self.log("检测到 requirements.txt，正在安装依赖...")
            self._install_from_requirements(venv_python, requirements_file)
        else:
            # 从项目中分析依赖
            self.log("未检测到 requirements.txt，正在分析项目依赖...")
            script_path = config.get("script_path", "")
            if script_path:
                deps = self.dependency_analyzer.analyze(script_path, project_dir)
                if deps:
                    self.log(f"检测到 {len(deps)} 个第三方依赖，正在安装...")
                    self._install_analyzed_dependencies(venv_python, deps, project_dir)
                else:
                    self.log("未检测到需要安装的第三方依赖")

    def _install_from_requirements(
        self,
        python_path: str,
        requirements_file: str,
    ) -> bool:
        """
        从 requirements.txt 安装依赖

        Args:
            python_path: Python 解释器路径
            requirements_file: requirements.txt 文件路径

        Returns:
            是否成功
        """
        import subprocess

        from utils.constants import CREATE_NO_WINDOW

        try:
            # 使用镜像源安装
            mirrors = [
                ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
                ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
                ("默认源", None),
            ]

            for mirror_name, mirror_url in mirrors:
                self.log(f"  尝试使用 {mirror_name} 安装依赖...")

                cmd = [
                    python_path,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    requirements_file,
                    "--quiet",
                ]

                if mirror_url:
                    cmd.extend(
                        [
                            "-i",
                            mirror_url,
                            "--trusted-host",
                            mirror_url.split("//")[1].split("/")[0],
                        ]
                    )

                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        creationflags=CREATE_NO_WINDOW,
                    )

                    if result.returncode == 0:
                        self.log(f"✓ 依赖安装成功（使用 {mirror_name}）")
                        return True
                    else:
                        self.log(f"  {mirror_name} 安装失败，尝试下一个镜像源...")

                except subprocess.TimeoutExpired:
                    self.log(f"  {mirror_name} 安装超时，尝试下一个镜像源...")

            self.log("警告: 所有镜像源均安装失败")
            return False

        except Exception as e:
            self.log(f"安装依赖时出错: {e}")
            return False

    def _install_analyzed_dependencies(
        self,
        python_path: str,
        deps: set,
        project_dir: str,
    ) -> bool:
        """
        安装分析到的依赖

        Args:
            python_path: Python 解释器路径
            deps: 依赖集合
            project_dir: 项目目录

        Returns:
            是否成功
        """
        # 获取内部模块信息
        internal_modules = getattr(
            self.dependency_analyzer, "_project_internal_modules", set()
        )
        is_stdlib = self.dependency_analyzer._is_stdlib
        is_internal = getattr(self.dependency_analyzer, "_is_internal_module", None)

        result = self.dependency_installer.install_dependencies(
            python_path,
            deps,
            project_dir,
            internal_modules,
            is_stdlib,
            is_internal,
        )
        return result if result is not None else True

    def _is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.cancel_flag is not None and self.cancel_flag()

    def _has_chinese(self, text: str) -> bool:
        """检查字符串中是否包含中文字符"""
        if not text:
            return False
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _check_chinese_paths(self, config: Dict) -> None:
        """检查路径中是否包含中文字符并发出警告"""
        script_path = config.get("script_path")
        project_dir = config.get("project_dir")

        paths_to_check = {
            "脚本路径": script_path,
            "项目目录": project_dir,
        }

        chinese_paths = []
        for path_name, path_value in paths_to_check.items():
            if path_value and self._has_chinese(path_value):
                chinese_paths.append(f"{path_name}: {path_value}")

        if chinese_paths:
            self.log("\n" + "!" * 50)
            self.log("警告: 检测到路径中包含中文字符")
            self.log("!" * 50)
            for path_info in chinese_paths:
                self.log(f"  {path_info}")
            self.log("")
            self.log("中文路径可能导致以下问题：")
            self.log("  1. PyInstaller/Nuitka 在处理某些依赖时可能出现编码错误")
            self.log("  2. 虚拟环境创建可能失败")
            self.log("  3. Qt 插件目录识别可能出现问题")
            self.log("")
            self.log("建议:")
            self.log("  - 将项目移动到纯英文路径下（如 C:/Projects/myapp）")
            self.log("")
            self.log("打包将继续尝试，但可能会遇到问题...")
            self.log("!" * 50 + "\n")

    @staticmethod
    def _get_protected_dirs() -> List[str]:
        """
        获取受保护的系统目录列表

        这些目录中的内容不得被自动清空，以防止误删用户重要文件。
        返回的路径均经过规范化处理，大小写不敏感比较时应注意平台差异。

        Returns:
            受保护目录的绝对路径列表
        """
        protected = []
        home = os.path.expanduser("~")

        # Windows 特殊目录
        if sys.platform == "win32":
            # 桌面
            desktop = os.path.join(home, "Desktop")
            if os.path.exists(desktop):
                protected.append(os.path.normpath(desktop))

            # 用户主目录本身
            protected.append(os.path.normpath(home))

            # 系统盘根目录
            system_drive = os.environ.get("SystemDrive", "C:")
            protected.append(os.path.normpath(system_drive + os.sep))

            # 常见用户目录
            for folder in [
                "Downloads",
                "Documents",
                "Pictures",
                "Videos",
                "Music",
                "OneDrive",
                "AppData",
                ".ssh",
                ".git",
            ]:
                path = os.path.join(home, folder)
                if os.path.exists(path):
                    protected.append(os.path.normpath(path))

            # Windows 系统目录
            windir = os.environ.get("WINDIR", "C:\\Windows")
            if os.path.exists(windir):
                protected.append(os.path.normpath(windir))

            # Program Files 目录
            for pf in ["Program Files", "Program Files (x86)"]:
                pf_path = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, pf)
                if os.path.exists(pf_path):
                    protected.append(os.path.normpath(pf_path))
        else:
            # Linux / macOS 系统目录
            protected.append(os.path.normpath(home))
            for folder in [
                "Desktop",
                "Downloads",
                "Documents",
                "Pictures",
                "/",
                "/etc",
                "/usr",
                "/bin",
                "/sbin",
                "/var",
                "/tmp",
            ]:
                path = folder if folder.startswith("/") else os.path.join(home, folder)
                if os.path.exists(path):
                    protected.append(os.path.normpath(path))

        return protected

    @staticmethod
    def _is_protected_dir(dir_path: str) -> Tuple[bool, str]:
        """
        检查目录是否为受保护的系统目录

        Args:
            dir_path: 要检查的目录路径

        Returns:
            (是否为受保护目录, 匹配到的受保护目录路径)
        """
        normalized = os.path.normpath(os.path.abspath(dir_path)).rstrip(os.sep)
        normalized_lower = normalized.lower()

        for protected in Packager._get_protected_dirs():
            protected_norm = os.path.normpath(protected).rstrip(os.sep)
            if normalized_lower == protected_norm.lower():
                return True, protected_norm

        return False, ""

    @staticmethod
    def _is_safe_output_dir(
        output_dir: str, script_path: str, project_dir: Optional[str]
    ) -> Tuple[bool, str]:
        """
        检查输出目录是否安全（不会被误删重要文件）

        Args:
            output_dir: 输出目录路径
            script_path: 脚本路径
            project_dir: 项目目录

        Returns:
            (是否安全, 错误信息/空字符串表示安全)
        """
        normalized = os.path.normpath(os.path.abspath(output_dir))

        # 1. 检查是否直接是受保护目录
        is_protected, matched = Packager._is_protected_dir(normalized)
        if is_protected:
            return False, (
                f"输出目录 '{output_dir}' 是受保护的系统目录 "
                f"({matched})。\n"
                f"请选择一个项目子目录或专门的构建输出目录，"
                f"以避免误删重要文件。"
            )

        # 2. 检查输出目录是否在受保护目录的父级中
        #    (防止 output_dir = C:\ 这种根目录情况)
        normalized_lower = normalized.lower()
        for protected in Packager._get_protected_dirs():
            protected_norm = os.path.normpath(protected).rstrip(os.sep).lower()
            # 如果输出目录是受保护目录的祖先（受保护目录在输出目录内部），
            # 且输出目录层级较浅（如根目录），则也认为是危险的
            if (
                protected_norm.startswith(normalized_lower + os.sep)
                and normalized_lower.count(os.sep) <= 1
            ):
                return False, (
                    f"输出目录 '{output_dir}' 层级过浅，"
                    f"且包含了系统目录 '{protected}'。\n"
                    f"请选择一个更具体的子目录（如项目下的 build 目录），"
                    f"以确保不会误删重要文件。"
                )

        # 3. 如果 output_dir 的目录名不是 "build" 或类似构建目录名，发出提醒
        #    (这只是一个宽松的检查，不宜过于严格)
        dir_basename = os.path.basename(normalized.rstrip(os.sep)).lower()
        script_dir = os.path.normpath(os.path.dirname(os.path.abspath(script_path)))
        project_root = (
            os.path.normpath(os.path.abspath(project_dir))
            if project_dir
            else script_dir
        )

        # 如果输出目录不在脚本目录或项目目录下，且不是 build/dist/out 等构建目录
        build_like_names = {
            "build",
            "dist",
            "output",
            "out",
            "target",
            "bin",
            "__pycache__",
            ".build",
            ".dist",
        }
        if dir_basename not in build_like_names:
            # 检查是否在项目目录范围内
            if (
                not normalized_lower.startswith(project_root.lower() + os.sep)
                and normalized_lower != project_root.lower()
            ):
                # 不在项目目录下，给出警告但仍允许使用
                # (不阻止，因为用户可能有合理的自定义输出目位置)
                pass

        return True, ""

    def _prepare_output_dir(self, config: Dict) -> str:
        """准备输出目录"""
        script_path = config["script_path"]
        project_dir = config.get("project_dir")
        output_dir = config.get("output_dir")

        if not output_dir:
            if project_dir:
                output_dir = os.path.join(project_dir, "build")
            else:
                output_dir = os.path.join(os.path.dirname(script_path), "build")

        # 安全校验：防止输出目录为受保护的系统目录
        is_safe, error_msg = self._is_safe_output_dir(
            output_dir, script_path, project_dir
        )
        if not is_safe:
            raise ValueError(error_msg)

        # 精准清理与本次构建相关的旧产物
        if os.path.exists(output_dir):
            self.log(f"\n检测到已存在的输出目录: {output_dir}")
            try:
                # 推导本次构建涉及的名称
                script_stem = Path(script_path).stem
                program_name = (
                    config.get("program_name")
                    or (os.path.basename(project_dir) if project_dir else None)
                    or script_stem
                )

                # 构建需要清理的精准模式
                # 1. Nuitka 以入口脚本名命名的中间目录
                target_dirs = [
                    f"{script_stem}.build",
                    f"{script_stem}.dist",
                    f"{script_stem}.onefile-build",
                ]
                # 如果 program_name 与 script_stem 不同，也清理以 program_name 命名的目录
                if program_name and program_name != script_stem:
                    target_dirs += [
                        f"{program_name}.build",
                        f"{program_name}.dist",
                        f"{program_name}.onefile-build",
                    ]

                # 2. 上次输出的 exe
                target_files = []
                if program_name:
                    target_files.append(f"{program_name}.exe")
                target_files.append(f"{script_stem}.exe")

                # 3. 构建日志和临时图标
                target_files += [
                    "build.log",
                    "icon_converted.ico",
                ]

                cleaned = 0
                for name in target_dirs:
                    path = os.path.join(output_dir, name)
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        self.log(f"  已清理: {name}/")
                        cleaned += 1

                for name in set(target_files):  # set 去重
                    path = os.path.join(output_dir, name)
                    if os.path.isfile(path):
                        os.unlink(path)
                        self.log(f"  已清理: {name}")
                        cleaned += 1

                if cleaned:
                    self.log(f"✓ 旧构建文件已清理（共 {cleaned} 项）")
                else:
                    self.log("✓ 无需清理")

            except Exception as e:
                self.log(f"警告：清理输出目录时出错: {str(e)}")

        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _analyze_dependencies(
        self,
        script_path: str,
        project_dir: Optional[str],
        python_path: str,
        config: Dict,
    ) -> Tuple[set, List[str], List[str]]:
        """
        分析项目依赖

        Returns:
            (dependencies, hidden_imports, exclude_modules)
        """
        self.log("\n" + "=" * 50)
        self.log("第一阶段：依赖分析")
        self.log("=" * 50)

        # 静态分析
        self.log("执行静态依赖分析...")
        deps = self.dependency_analyzer.analyze(script_path, project_dir)
        self.log(f"静态分析检测到 {len(deps)} 个第三方依赖")
        if deps:
            # 显示具体的依赖名称
            deps_list = sorted(deps)
            self.log(f"  依赖列表: {', '.join(deps_list)}")

        # 动态追踪（非 GUI 项目）
        self.log("执行动态导入追踪...")
        success_trace, traced = self.dependency_analyzer.trace_dynamic_imports(
            script_path, python_path, project_dir
        )
        if success_trace:
            self.log(f"动态追踪捕获到 {len(traced)} 个导入")

        # 自动分析第三方库的子模块（未命中加速缓存的库）
        self.dependency_analyzer.collect_third_party_submodules(python_path)

        # 获取优化建议并自动应用到配置
        exclude_modules, hidden_imports, _ = (
            self.dependency_analyzer.get_optimization_suggestions(python_path)
        )

        # 自动合并到配置中的 hidden_imports / exclude_modules（去重保序）
        config_hidden = config.get("hidden_imports", []) or []
        config_exclude = config.get("exclude_modules", []) or []

        merged_hidden = list(dict.fromkeys(config_hidden + hidden_imports))
        merged_exclude = list(dict.fromkeys(config_exclude + exclude_modules))

        config["hidden_imports"] = merged_hidden
        config["exclude_modules"] = merged_exclude

        applied_hidden_count = max(0, len(merged_hidden) - len(config_hidden))
        applied_exclude_count = max(0, len(merged_exclude) - len(config_exclude))

        self.log(
            f"已自动应用隐藏导入: +{applied_hidden_count} 个（当前共 {len(merged_hidden)} 个）"
        )
        self.log(
            f"已自动应用排除模块: +{applied_exclude_count} 个（当前共 {len(merged_exclude)} 个）"
        )

        return deps, merged_hidden, merged_exclude

    def _install_dependencies(
        self,
        python_path: str,
        deps: set,
        project_dir: Optional[str],
    ) -> bool:
        """安装项目依赖"""
        self.log("\n" + "=" * 50)
        self.log("第二阶段：依赖安装")
        self.log("=" * 50)

        # 获取内部模块信息
        internal_modules = getattr(
            self.dependency_analyzer, "_project_internal_modules", set()
        )
        is_stdlib = self.dependency_analyzer._is_stdlib
        is_internal = getattr(self.dependency_analyzer, "_is_internal_module", None)

        self.dependency_installer.install_dependencies(
            python_path,
            deps,
            project_dir,
            internal_modules,
            is_stdlib,
            is_internal,
        )
        return True

    def _process_icon(
        self,
        config: Dict,
        output_dir: str,
        python_path: str,
    ) -> Optional[str]:
        """处理图标文件"""
        # 同时支持 "icon" 和 "icon_path" 两个键名（兼容GUI和其他调用方式）
        icon_path = config.get("icon") or config.get("icon_path")
        if not icon_path:
            self.log("\n未指定程序图标，将使用默认图标")
            return None

        self.log("\n处理图标文件...")
        self.log(f"  用户指定的图标路径: {icon_path}")

        # 验证图标文件是否存在
        if not os.path.exists(icon_path):
            self.log(f"  ⚠️ 警告: 图标文件不存在: {icon_path}")
            return None

        # 输出图标文件信息
        try:
            icon_size = os.path.getsize(icon_path)
            icon_ext = os.path.splitext(icon_path)[1].lower()
            self.log(f"  图标文件大小: {icon_size} 字节, 格式: {icon_ext}")
        except Exception as e:
            self.log(f"  无法获取图标文件信息: {e}")

        processed_icon, warnings = self.icon_processor.process_icon_file(
            icon_path, output_dir, python_path
        )

        for warning in warnings:
            self.log(f"  图标: {warning}")

        if processed_icon:
            self.log(f"  最终使用的图标文件: {processed_icon}")
        else:
            self.log("  图标处理失败，将使用默认图标")

        return processed_icon

    def _prepare_version_info(self, config: Dict, output_dir: str) -> Optional[str]:
        """准备版本信息"""
        # 检查是否有版本信息配置
        # GUI 将版本信息存储在 config["version_info"] 嵌套字典中
        version_info = config.get("version_info")
        if version_info:
            self.log(f"\n检测到版本信息配置: {list(version_info.keys())}")
            has_version_info = any(
                [
                    version_info.get("version"),
                    version_info.get("company_name"),
                    version_info.get("file_description"),
                    version_info.get("copyright"),
                    version_info.get("product_name"),
                ]
            )
        else:
            self.log("\n未检测到 config['version_info'] 嵌套字典，尝试检查顶层键...")
            # 兼容：也检查顶层键（以防其他调用方式）
            has_version_info = any(
                [
                    config.get("version"),
                    config.get("company_name"),
                    config.get("file_description"),
                    config.get("copyright"),
                ]
            )

        if not has_version_info:
            self.log("未找到任何版本信息字段，跳过版本信息处理")
            return None

        self.log("\n准备版本信息...")
        version_file = self._create_version_info_file(config, output_dir)
        if version_file:
            self.log(f"  版本信息文件已创建: {version_file}")
            pending = self.version_info_handler.get_pending_version_info()
            if pending:
                self.log(
                    f"  已注册待处理版本信息 (rcedit 后处理): {list(pending.keys())}"
                )
            else:
                self.log("  ⚠️ 待处理版本信息未注册，rcedit 后处理将不会执行")
        else:
            self.log("  ⚠️ 版本信息文件创建失败")
        return version_file

    def _create_version_info_file(self, config: Dict, output_dir: str) -> Optional[str]:
        """创建 PyInstaller 版本信息文件"""
        version_info = config.get("version_info")
        if not version_info:
            return None

        version_str = version_info.get("version", "1.0.0")
        product_name = config.get("program_name", "Application")
        company_name = version_info.get("company_name", "")
        file_description = version_info.get("file_description", product_name)
        copyright_text = version_info.get("copyright", "")

        # 设置待处理版本信息，以便后续使用 rcedit 进行修复
        # PyInstaller 生成的版本信息有时会有乱码或不显示，特别是中文
        pending_info = {
            "version": version_str,
            "product_name": product_name,
            "company_name": company_name,
            "file_description": file_description,
            "copyright": copyright_text,
        }
        self.version_info_handler.set_pending_version_info(pending_info)

        windows_version = self.version_info_handler.convert_version_to_windows_format(
            version_str
        )
        version_parts = windows_version.split(".")

        version_file_content = f"""# UTF-8
#
# PyInstaller version file — Chinese Simplified (0804) + Unicode (1200)
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    prodvers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404B0',
          [
            StringStruct(u'CompanyName', u'{company_name}'),
            StringStruct(u'FileDescription', u'{file_description}'),
            StringStruct(u'FileVersion', u'{windows_version}'),
            StringStruct(u'InternalName', u'{product_name}'),
            StringStruct(u'LegalCopyright', u'{copyright_text}'),
            StringStruct(u'OriginalFilename', u'{product_name}.exe'),
            StringStruct(u'ProductName', u'{product_name}'),
            StringStruct(u'ProductVersion', u'{windows_version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
"""
        try:
            version_file_path = os.path.join(output_dir, "version_info.txt")
            with open(version_file_path, "w", encoding="utf-8") as f:
                f.write(version_file_content)
            self.log(f"  已创建版本信息文件: {version_file_path}")
            return version_file_path
        except Exception as e:
            self.log(f"  创建版本信息文件失败: {str(e)}")
            return None

    def _do_package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str],
        version_file: Optional[str],
    ) -> Tuple[bool, str]:
        """执行实际打包（编排 5 个后处理关注点）。

        拆分为 5 个独立私有方法以解耦 rcedit/UPX/清理逻辑，
        便于扩展维护，并供 Pipeline 的后处理 Step 各自委托。
        """
        self.log("\n" + "=" * 50)
        self.log("第三阶段：打包")
        self.log("=" * 50)

        # 1. 配置增强：填充 qt_framework / GUI 框架标志 / 版本文件
        pack_config, tool = self._build_pack_config(config, version_file)

        # 2. 图标入口注入（仅 Nuitka + 图标 + 非自打包）
        self._inject_icon_entry(pack_config, tool, output_dir, icon_path)

        # 3. 执行打包
        success, message = self._execute_build(
            python_path, config, pack_config, tool,
            output_dir, hidden_imports, exclude_modules, icon_path,
        )

        # 4. 版本信息后处理（rcedit）
        if success:
            self._post_process_version_info(pack_config, tool)

        # 5. 清理临时文件
        self._cleanup_temp_files(pack_config, version_file, icon_path)

        return success, message

    def _build_pack_config(
        self, config: Dict, version_file: Optional[str]
    ) -> Tuple[Dict, str]:
        """后处理关注点 1：配置增强。

        填充 qt_framework、检测到的 GUI 框架标志、版本文件，
        返回 (旧格式 dict 配置, 打包工具名)。
        """
        pkg_config = (
            PackagingConfig.from_dict(config) if isinstance(config, dict) else config
        )

        tool = pkg_config.tool
        self.log(f"使用打包工具: {tool.upper()}")

        qt_framework = self.dependency_analyzer.primary_qt_framework
        pkg_config.qt_framework = qt_framework

        gui_frameworks = self.dependency_analyzer.get_detected_gui_frameworks()
        deps = getattr(self.dependency_analyzer, "dependencies", set())
        all_imports = getattr(self.dependency_analyzer, "all_imports", set())

        pkg_config.detected_gui_frameworks = gui_frameworks
        pkg_config.uses_tkinter = (
            "Tkinter" in gui_frameworks
            or "CustomTkinter" in gui_frameworks
            or "tkinter" in all_imports
            or "customtkinter" in all_imports
        )
        pkg_config.uses_numpy = "numpy" in deps or "numpy" in all_imports
        pkg_config.uses_matplotlib = "matplotlib" in deps or "matplotlib" in all_imports

        if version_file:
            pkg_config.version_file = version_file

        # 中文版本信息 + UPX 不兼容：UPX 压缩后 rcedit 无法修改 PE 资源段。
        # 自动禁用 UPX，确保 rcedit 后处理能修复 Nuitka temp 文件名和中文乱码。
        version_info = pkg_config.version_info or {}
        has_chinese = any(
            "\u4e00" <= c <= "\u9fff"
            for v in version_info.values()
            for c in str(v)
        ) if version_info else False
        if has_chinese and pkg_config.upx and pkg_config.tool == "nuitka":
            self.log("\n⚠️ 检测到中文版本信息，自动禁用 UPX 压缩")
            self.log("  UPX 压缩后 rcedit 无法修复 PE 资源中的中文和文件名")
            pkg_config.upx = False

        return pkg_config.as_dict(), tool

    def _inject_icon_entry(
        self, pack_config: Dict, tool: str, output_dir: str, icon_path: Optional[str]
    ) -> None:
        """后处理关注点 2：图标入口注入（Nuitka + PyInstaller）。

        Nuitka 不设置 sys.frozen，PyInstaller 设置但用户代码可能遗漏 setWindowIcon。
        注入 _ppt_entry.py 确保窗口标题栏图标由 QApplication 构造时自动设置。
        自打包时跳过（打包工具自身的 main.py 已有正确检测）。
        """
        is_self_packaging = os.path.abspath(pack_config["script_path"]) == os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        )
        if icon_path and not is_self_packaging:
            wrapper_path = self._create_icon_entry_wrapper(
                output_dir, pack_config["script_path"], icon_path
            )
            if wrapper_path:
                pack_config["script_path"] = wrapper_path
                self.log("  已注入图标入口代码（自动设置窗口图标）")

    def _execute_build(
        self,
        python_path: str,
        config: Dict,
        pack_config: Dict,
        tool: str,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str],
    ) -> Tuple[bool, str]:
        """后处理关注点 3：调用打包器执行打包。"""
        if tool == "nuitka":
            packager = self.nuitka_packager
            gcc_path = config.get("gcc_path")
            success, message = packager.package(
                python_path,
                pack_config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path=icon_path,
                gcc_path=gcc_path,
            )
        else:
            packager = self.pyinstaller_packager
            success, message = packager.package(
                python_path,
                pack_config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path=icon_path,
            )

        if success:
            self._last_exe_path = packager.get_last_exe_path()
            self.log(f"\n打包成功，exe 路径: {self._last_exe_path}")

        return success, message

    def _post_process_version_info(self, pack_config: Dict, tool: str) -> None:
        """后处理关注点 4：中文版本信息的 rcedit 后处理。

        - PyInstaller 通过 --version-file 正确嵌入中文，无需 rcedit
        - Nuitka + MinGW windres 无法正确处理 UTF-8 中文，需要 rcedit
        - UPX 已在 _build_pack_config 中自动禁用（中文+UPX 不兼容）
        """
        version_info = (
            pack_config.get("version_info", {})
            if isinstance(pack_config, dict)
            else getattr(pack_config, "version_info", {})
        )
        has_chinese = (
            any(
                "\u4e00" <= c <= "\u9fff"
                for v in version_info.values()
                for c in str(v)
            )
            if version_info
            else False
        )

        if has_chinese and self._last_exe_path:
            if tool != "nuitka":
                self.log("\n✅ PyInstaller 已通过 --version-file 嵌入中文版本信息，无需 rcedit")
            else:
                self.log("\n检测到中文版本信息，使用 rcedit 后处理...")
                rcedit_success = self.rcedit_handler.post_process_add_version_info(
                    self._last_exe_path, version_info
                )
                if rcedit_success:
                    self.log("  ✓ rcedit 后处理完成，中文版本信息已嵌入")
                else:
                    self.log("  ⚠️ rcedit 后处理失败，中文版本信息可能不完整")

        self.nuitka_packager.clear_pending_version_info()
        self.version_info_handler.clear_pending_version_info()

    def _cleanup_temp_files(
        self, pack_config: Dict, version_file: Optional[str], icon_path: Optional[str]
    ) -> None:
        """后处理关注点 5：统一清理临时文件。

        清理版本信息文件、临时转换图标 (icon_converted.ico)、注入脚本 (_ppt_entry.py)。
        """
        if version_file and os.path.exists(version_file):
            try:
                os.remove(version_file)
                self.log(f"已清理临时版本信息文件: {version_file}")
            except Exception:
                pass

        if (
            icon_path
            and "icon_converted.ico" in icon_path
            and os.path.exists(icon_path)
        ):
            try:
                os.remove(icon_path)
                self.log(f"已清理临时图标文件: {icon_path}")
            except Exception:
                pass

        # 清理临时注入脚本（_ppt_entry.py）
        entry_script = pack_config.get("script_path", "")
        if entry_script.endswith("_ppt_entry.py") and os.path.exists(entry_script):
            try:
                os.remove(entry_script)
                self.log(f"已清理临时注入脚本: {entry_script}")
            except Exception:
                pass

    def package(
        self,
        config: Union[Dict, PackagingConfig],
        log_callback: Optional[Callable] = None,
        cancel_flag: Optional[Callable] = None,
        process_callback: Optional[Callable] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        [DEPRECATED] 传统打包入口 — 已由 package_via_pipeline() 取代。

        保留此方法用于回退验证，新调用方请使用 package_via_pipeline()。
        计划在下一阶段（删死代码 + 大文件简化）中移除。
        """
        # 规范化配置：将 PackagingConfig 转为 dict（内部方法仍用 dict）
        if isinstance(config, PackagingConfig):
            config = config.as_dict()

        # 设置回调
        if log_callback:
            self._set_log_callback(log_callback)
        if cancel_flag:
            self._set_cancel_flag(cancel_flag)
        if process_callback:
            self._set_process_callback(process_callback)

        try:
            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 1. 获取基础 Python 路径
            base_python_path, python_error = self._get_python_path(config)
            if not base_python_path:
                return False, python_error or "未找到 Python 环境", None

            self.log(f"基础 Python: {base_python_path}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 2. 设置虚拟环境（如果启用）
            python_path = self._setup_venv_if_needed(config, base_python_path)
            if python_path != base_python_path:
                self.log(f"使用虚拟环境 Python: {python_path}")

            # 3. 检查中文路径警告
            self._check_chinese_paths(config)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 4. 准备输出目录
            script_path = config["script_path"]
            project_dir = config.get("project_dir")
            output_dir = self._prepare_output_dir(config)
            self.log(f"输出目录: {output_dir}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 5. 检测 Qt 框架
            primary_qt = self.dependency_analyzer.detect_primary_qt_framework(
                script_path, project_dir
            )
            if primary_qt:
                self.log(f"检测到GUI主要 Qt 框架: {primary_qt}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 6. 分析依赖
            deps, hidden_imports, exclude_modules = self._analyze_dependencies(
                script_path, project_dir, python_path, config
            )

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 7. 安装依赖（补充安装分析到的额外依赖）
            self._install_dependencies(python_path, deps, project_dir)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 8. 安装打包工具
            tool = config.get("tool", "pyinstaller")
            self.log(f"\n检查打包工具 {tool}...")
            self.dependency_installer.install_packaging_tool(python_path, tool)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 9. 处理图标
            icon_path = self._process_icon(config, output_dir, python_path)

            # 10. 准备版本信息
            version_file = self._prepare_version_info(config, output_dir)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 11. 自动检测并包含运行时数据文件（config.env、icon.* 等）
            self._auto_detect_data_files(config, project_dir, script_path)

            # 12. 执行打包
            success, message = self._do_package(
                python_path,
                config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path,
                version_file,
            )

            return success, message, self._last_exe_path

        except Exception as e:
            self.log(f"打包异常: {e}")
            import traceback

            self.log(traceback.format_exc())
            return False, f"打包过程出错: {str(e)}", None

    @staticmethod
    def _create_icon_entry_wrapper(
        output_dir: str, user_script: str, icon_path: str
    ) -> Optional[str]:
        """为 Nuitka 打包生成带图标注入的入口脚本副本。

        将图标查找+QApplication补丁代码前置插入到用户脚本开头，
        生成副本作为 Nuitka 入口点。Nuitka 可直接分析副本中的所有 import。

        Args:
            output_dir: 输出目录
            user_script: 用户原始脚本路径
            icon_path: 图标文件路径

        Returns:
            注入后的脚本路径，失败返回 None
        """
        try:
            # 读取用户原始脚本
            with open(user_script, "r", encoding="utf-8") as f:
                user_code = f.read()

            # 前置注入代码
            injected = (
                '# -*- coding: utf-8 -*-\n'
                '# Icon injector - auto-generated by Python Packaging Tool\n'
                'import os, sys\n'
                '\n'
                '# Ensure Nuitka onefile extraction dir is in sys.path\n'
                'try:\n'
                '    if "__compiled__" in dir():\n'
                '        d = __compiled__.containing_dir\n'
                '        if d not in sys.path:\n'
                '            sys.path.insert(0, d)\n'
                'except Exception:\n'
                '    pass\n'
                '\n'
                '# Set sys.frozen for PyInstaller-compatible user code\n'
                'if not getattr(sys, "frozen", False):\n'
                '    sys.frozen = True\n'
                '\n'
                'def _ppt_find_icon():\n'
                '    names = ("icon.ico", "app.ico", "icon.png", "app.png")\n'
                '    subdirs = ("", "resources/icons", "resources", "icons")\n'
                '    bases = []\n'
                '    try:\n'
                '        if "__compiled__" in dir():\n'
                '            bases.append(__compiled__.containing_dir)\n'
                '    except Exception:\n'
                '        pass\n'
                '    bases.append(os.path.dirname(sys.executable))\n'
                '    bases.append(os.getcwd())\n'
                '    if hasattr(sys, "_MEIPASS"):\n'
                '        bases.append(sys._MEIPASS)\n'
                '    for b in bases:\n'
                '        for s in subdirs:\n'
                '            for n in names:\n'
                '                p = os.path.join(b, s, n) if s else os.path.join(b, n)\n'
                '                if os.path.isfile(p):\n'
                '                    return p\n'
                '    return None\n'
                '\n'
                '# Patch PyQt6/PyQt5/wxPython to auto-set window icon\n'
                'def _ppt_patch_qt(cls, icon_cls, icon_path):\n'
                '    _orig = cls.__init__\n'
                '    def _new_init(self, *a, **kw):\n'
                '        _orig(self, *a, **kw)\n'
                '        try:\n'
                '            ic = icon_cls(icon_path)\n'
                '            if not ic.isNull():\n'
                '                self.setWindowIcon(ic)\n'
                '        except Exception:\n'
                '            pass\n'
                '    cls.__init__ = _new_init\n'
                '\n'
                'def _ppt_patch_wx(icon_path):\n'
                '    """Patch wx.Frame to auto-set window icon."""\n'
                '    import wx\n'
                '    _orig_frame_init = wx.Frame.__init__\n'
                '    def _new_frame_init(self, *a, **kw):\n'
                '        _orig_frame_init(self, *a, **kw)\n'
                '        try:\n'
                '            ib = wx.IconBundle(icon_path)\n'
                '            self.SetIcons(ib)\n'
                '        except Exception:\n'
                '            try:\n'
                '                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)\n'
                '                if icon.IsOk():\n'
                '                    self.SetIcon(icon)\n'
                '            except Exception:\n'
                '                pass\n'
                '    wx.Frame.__init__ = _new_frame_init\n'
                '\n'
                '_icon = _ppt_find_icon()\n'
                'if _icon:\n'
                '    try:\n'
                '        import PyQt6.QtWidgets, PyQt6.QtGui\n'
                '        _ppt_patch_qt(PyQt6.QtWidgets.QApplication, PyQt6.QtGui.QIcon, _icon)\n'
                '    except ImportError:\n'
                '        pass\n'
                '    try:\n'
                '        import PyQt5.QtWidgets, PyQt5.QtGui\n'
                '        _ppt_patch_qt(PyQt5.QtWidgets.QApplication, PyQt5.QtGui.QIcon, _icon)\n'
                '    except ImportError:\n'
                '        pass\n'
                '    try:\n'
                '        _ppt_patch_wx(_icon)\n'
                '    except ImportError:\n'
                '        pass\n'
                '\n'
                '# ---- original user script follows ----\n\n'
            )

            # 写入到用户脚本同目录，确保 Nuitka 能解析用户项目的本地模块
            wrapper_path = os.path.join(os.path.dirname(user_script), "_ppt_entry.py")
            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(injected)
                f.write(user_code)

            return wrapper_path
        except Exception:
            return None

    def _auto_detect_data_files(
        self,
        config: Dict,
        project_dir: Optional[str],
        script_path: str,
    ) -> None:
        """
        自动检测项目中需要打包的运行时数据文件

        扫描项目目录，查找常见的配置文件和资源文件：
        - config.env / .env 配置文件
        - icon.* 图标文件
        - *.gif / *.png 等资源文件
        - 加载动画 (loading.gif)

        自动添加到 extra_data 配置中，确保打包时被包含。
        """
        scan_dir = project_dir if project_dir else os.path.dirname(script_path)
        if not scan_dir or not os.path.isdir(scan_dir):
            return

        self.log("\n自动检测运行时数据文件...")

        # 配置文件匹配模式
        config_patterns = [
            "config.env",
            ".env",
            "settings.ini",
            "settings.conf",
            "config.ini",
            "config.json",
            "config.yaml",
            "config.yml",
            "config.toml",
        ]

        # 资源文件匹配模式（除了图标已在 _process_icon 中处理）
        resource_patterns = [
            "loading.gif",
            "loading.png",
            "splash.png",
            "splash.jpg",
        ]

        extra_data: list = config.get("extra_data", []) or []
        existing_basenames = {os.path.basename(p) for p in extra_data}
        newly_detected: list = []

        # 扫描项目根目录下的配置文件
        for pattern in config_patterns:
            candidate = os.path.join(scan_dir, pattern)
            if (
                os.path.isfile(candidate)
                and os.path.basename(candidate) not in existing_basenames
            ):
                extra_data.append(candidate)
                existing_basenames.add(os.path.basename(candidate))
                newly_detected.append(candidate)
                self.log(f"  检测到配置文件: {os.path.basename(candidate)}")

        # 扫描 resources 子目录
        resources_dir = os.path.join(scan_dir, "resources")
        if os.path.isdir(resources_dir):
            for pattern in resource_patterns:
                candidate = os.path.join(resources_dir, pattern)
                if (
                    os.path.isfile(candidate)
                    and os.path.basename(candidate) not in existing_basenames
                ):
                    extra_data.append(candidate)
                    existing_basenames.add(os.path.basename(candidate))
                    newly_detected.append(candidate)
                    self.log(
                        f"  检测到资源文件: resources/{os.path.basename(candidate)}"
                    )

        # 扫描项目根目录下的资源文件
        for pattern in resource_patterns:
            candidate = os.path.join(scan_dir, pattern)
            if (
                os.path.isfile(candidate)
                and os.path.basename(candidate) not in existing_basenames
            ):
                extra_data.append(candidate)
                existing_basenames.add(os.path.basename(candidate))
                newly_detected.append(candidate)
                self.log(f"  检测到资源文件: {os.path.basename(candidate)}")

        if newly_detected:
            config["extra_data"] = extra_data
            self.log(f"  共自动检测到 {len(newly_detected)} 个数据文件")
        else:
            self.log("  未检测到额外的数据文件")

        # 自动收集打包工具自身的 tools/ 目录（包含 upx.exe 等工具）
        # 确保打包成 exe 后这些工具仍可用
        self._auto_include_tools_dir(config, scan_dir)

    def _auto_include_tools_dir(
        self,
        config: Dict,
        project_dir: str,
    ) -> None:
        """
        自动将项目自身的 tools/ 目录（如 upx.exe、rcedit.exe）加入打包。

        确保 python_packaging_tool 打包成 exe 后，内嵌的 upx.exe
        能被 _get_tools_dir() 正确找到。
        """
        tools_dir = os.path.join(project_dir, "tools")
        if not os.path.isdir(tools_dir):
            return

        extra_data: list = config.get("extra_data", []) or []
        if tools_dir not in extra_data:
            extra_data.append(tools_dir)
            config["extra_data"] = extra_data
            self.log(f"  自动包含工具目录: tools/")

    # ========== 兼容性方法（保持原有接口）==========

    def check_windows_sdk_support(self) -> Tuple[bool, str]:
        """检查 Windows SDK 支持（委托给 windows_resource_handler）"""
        return self.windows_resource_handler.check_windows_sdk_support()
