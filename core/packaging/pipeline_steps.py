"""
打包流水线步骤 — 从 Packager.package() 12 步流程中提取的核心阶段。

每个 Step 遵循 PackagingStep 协议，独立可测试。
"""

import os
import sys
from typing import TYPE_CHECKING, Any, Dict

from core.packaging.pipeline import PackagingStep

if TYPE_CHECKING:
    pass


# =============================================================================
#  Step 1 — Python 解释器发现
# =============================================================================

class PythonDiscoveryStep(PackagingStep):
    """发现基础 Python 解释器路径。

    优先级：用户指定 > 系统搜索 > 当前解释器。

    context 输入: config
    context 输出: python_path
    """

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)

        python_path = config.get("python_path") or config.get("python")
        if python_path and os.path.exists(python_path):
            log(f"使用指定 Python: {python_path}")
            context["python_path"] = python_path
            return context

        from utils.python_finder import PythonFinder

        if PythonFinder.is_bundled_environment():
            log("当前在打包环境中运行，搜索系统 Python...")
            finder = PythonFinder()
            system_python = finder.find_python()
            if system_python:
                log(f"✓ 找到系统 Python: {system_python}")
                context["python_path"] = system_python
                return context
            context["success"] = False
            context["message"] = "未找到系统 Python，请在界面中手动指定"
            return context

        context["python_path"] = sys.executable
        log(f"使用当前解释器: {sys.executable}")
        return context


# =============================================================================
#  Step 2 — 虚拟环境搭建
# =============================================================================

class VenvSetupStep(PackagingStep):
    """创建/复用项目虚拟环境。

    context 输入: python_path, config
    context 输出: python_path (可能指向 venv)
    """

    def __init__(self, setup_fn: Any):
        """setup_fn: callable(config, base_python_path) -> resulting python_path"""
        self._setup_fn = setup_fn

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        python_path = context.get("python_path", sys.executable)

        if config.get("use_venv", True):
            new_path = self._setup_fn(config, python_path)
            if new_path != python_path:
                log(f"使用虚拟环境 Python: {new_path}")
                context["python_path"] = new_path

        return context


# =============================================================================
#  Step 3 — 依赖分析
# =============================================================================

class DependencyAnalysisStep(PackagingStep):
    """分析项目依赖、隐藏导入、排除模块。

    context 输入: python_path, config
    context 输出: dependencies, hidden_imports, exclude_modules
    """

    def __init__(self, dependency_analyzer: Any):
        self._analyzer = dependency_analyzer

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        script_path = config["script_path"]
        project_dir = config.get("project_dir")
        python_path = context.get("python_path", sys.executable)

        log("\n分析项目依赖...")
        deps = self._analyzer.analyze(script_path, project_dir)
        log(f"检测到 {len(deps)} 个依赖")

        if config.get("trace_imports", False):
            log("\n追踪动态导入...")
            self._analyzer.trace_dynamic_imports(script_path, project_dir, python_path)

        hidden_imports = self._analyzer.get_hidden_imports(python_path)
        if hidden_imports:
            log(f"需要隐藏导入: {len(hidden_imports)} 个模块")

        exclude_modules = self._analyzer.get_exclude_modules()
        if exclude_modules:
            log(f"排除模块: {len(exclude_modules)} 个")

        context["dependencies"] = deps
        context["hidden_imports"] = hidden_imports
        context["exclude_modules"] = exclude_modules
        return context


# =============================================================================
#  Step 4 — 依赖安装
# =============================================================================

class DependencyInstallStep(PackagingStep):
    """安装分析到的项目依赖和打包工具。

    context 输入: python_path, dependencies, config
    context 输出: (无新增字段)
    """

    def __init__(self, dependency_installer: Any):
        self._installer = dependency_installer

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        python_path = context["python_path"]
        deps = context.get("dependencies", set())
        project_dir = config.get("project_dir")

        log("\n安装项目依赖...")
        self._installer.install_analyzed_dependencies(python_path, deps, project_dir)

        tool = config.get("tool", "pyinstaller")
        log(f"\n检查打包工具 {tool}...")
        self._installer.install_packaging_tool(python_path, tool)

        return context


# =============================================================================
#  Step 5 — 输出目录准备
# =============================================================================

class OutputDirStep(PackagingStep):
    """验证并准备输出目录。

    context 输入: config
    context 输出: output_dir
    """

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        output_dir = config.get("output_dir")
        if not output_dir:
            script_path = config["script_path"]
            output_dir = os.path.join(os.path.dirname(script_path), "build")
        os.makedirs(output_dir, exist_ok=True)
        context["output_dir"] = output_dir
        return context


# =============================================================================
#  Step 6 — 图标处理
# =============================================================================

class IconProcessingStep(PackagingStep):
    """验证并转换图标文件。

    context 输入: config, output_dir, python_path
    context 输出: icon_path
    """

    def __init__(self, icon_processor: Any):
        self._processor = icon_processor

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        output_dir = context["output_dir"]
        python_path = context["python_path"]

        icon_path = config.get("icon_path") or config.get("icon")
        if icon_path and os.path.exists(icon_path):
            log(f"\n处理图标文件: {icon_path}")
            processed, warnings = self._processor.process_icon_file(
                icon_path, output_dir, python_path
            )
            for w in warnings:
                log(f"  图标: {w}")
            context["icon_path"] = processed
        else:
            context["icon_path"] = None

        return context
