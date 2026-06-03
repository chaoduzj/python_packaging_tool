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

    委托 Packager._get_python_path 以保证与传统 package() 路径逐字等价。

    context 输入: config
    context 输出: python_path（失败时设置 success=False / message）
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)

        base_python, error = self._packager._get_python_path(config)
        if not base_python:
            context["success"] = False
            context["message"] = error or "未找到 Python 环境"
            return context

        log(f"基础 Python: {base_python}")
        context["python_path"] = base_python
        return context


# =============================================================================
#  Step 2 — 虚拟环境搭建
# =============================================================================

class VenvSetupStep(PackagingStep):
    """创建/复用项目虚拟环境。

    委托 Packager._setup_venv_if_needed（其内部根据 use_venv 决策），
    与传统 package() 第 2 步无条件调用方式严格等价。

    context 输入: python_path, config
    context 输出: python_path (可能指向 venv)
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        base_python = context["python_path"]

        python_path = self._packager._setup_venv_if_needed(config, base_python)
        if python_path != base_python:
            log(f"使用虚拟环境 Python: {python_path}")
        context["python_path"] = python_path
        return context


# =============================================================================
#  Step 3 — 中文路径检查
# =============================================================================

class ChinesePathCheckStep(PackagingStep):
    """检查脚本/项目路径中的中文并发出警告。

    委托 Packager._check_chinese_paths，与传统 package() 第 3 步等价。

    context 输入: config
    context 输出: (无新增字段，仅产生警告日志)
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._packager._check_chinese_paths(context["config"])
        return context


# =============================================================================
#  Step 4 — 依赖分析
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
    """验证并准备输出目录（含安全检查与保守清理）。

    委托 Packager._prepare_output_dir，恢复 _is_safe_output_dir 安全检查
    （防止误删 C:\\ 等受保护目录）和构建产物清理，与传统 package() 第 4 步等价。

    context 输入: config
    context 输出: output_dir
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        log = context.get("log", print)
        output_dir = self._packager._prepare_output_dir(context["config"])
        log(f"输出目录: {output_dir}")
        context["output_dir"] = output_dir
        return context


# =============================================================================
#  Step — Qt 框架检测
# =============================================================================

class QtFrameworkDetectStep(PackagingStep):
    """检测项目主要 Qt 框架（PyQt5/6、PySide2/6）。

    委托 dependency_analyzer.detect_primary_qt_framework，
    与传统 package() 第 5 步等价。结果存于分析器实例，供后续打包步骤使用。

    context 输入: config
    context 输出: primary_qt（如检测到）
    """

    def __init__(self, dependency_analyzer: Any):
        self._analyzer = dependency_analyzer

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        primary_qt = self._analyzer.detect_primary_qt_framework(
            script_path, project_dir
        )
        if primary_qt:
            log(f"检测到GUI主要 Qt 框架: {primary_qt}")
            context["primary_qt"] = primary_qt
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
