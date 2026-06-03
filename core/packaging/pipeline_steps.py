"""
打包流水线步骤 — 从 Packager.package() 12 步流程中提取的核心阶段。

每个 Step 遵循 PackagingStep 协议，通过委托 Packager 的已验证方法
保证与传统 package() 路径严格等价。
"""

from typing import Any, Dict

from core.packaging.pipeline import PackagingStep


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
            context["_halt"] = True
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

    委托 Packager._analyze_dependencies，与传统 package() 第 6 步使用
    相同的分析接口，保证 deps/hidden_imports/exclude_modules 计算严格一致。

    context 输入: python_path, config
    context 输出: dependencies, hidden_imports, exclude_modules
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        script_path = config["script_path"]
        project_dir = config.get("project_dir")
        python_path = context["python_path"]

        deps, hidden_imports, exclude_modules = self._packager._analyze_dependencies(
            script_path, project_dir, python_path, config
        )

        context["dependencies"] = deps
        context["hidden_imports"] = hidden_imports
        context["exclude_modules"] = exclude_modules
        return context


# =============================================================================
#  Step 7 — 安装项目依赖
# =============================================================================

class DependencyInstallStep(PackagingStep):
    """安装分析到的项目依赖。

    委托 Packager._install_dependencies，与传统 package() 第 7 步等价。

    context 输入: python_path, dependencies, config
    context 输出: (无新增字段)
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        python_path = context["python_path"]
        deps = context.get("dependencies", set())
        project_dir = config.get("project_dir")

        self._packager._install_dependencies(python_path, deps, project_dir)
        return context


# =============================================================================
#  Step 8 — 安装打包工具
# =============================================================================

class PackagingToolInstallStep(PackagingStep):
    """安装打包工具（nuitka / pyinstaller）。

    委托 dependency_installer.install_packaging_tool，
    与传统 package() 第 8 步等价。

    context 输入: python_path, config
    context 输出: (无新增字段)
    """

    def __init__(self, dependency_installer: Any):
        self._installer = dependency_installer

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        log = context.get("log", print)
        python_path = context["python_path"]
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

    委托 Packager._process_icon，与传统 package() 第 9 步等价
    （含警告处理、格式转换、路径返回逻辑）。

    context 输入: config, output_dir, python_path
    context 输出: icon_path
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        output_dir = context["output_dir"]
        python_path = context["python_path"]

        icon_path = self._packager._process_icon(config, output_dir, python_path)
        context["icon_path"] = icon_path
        return context


# =============================================================================
#  Step 10 — 版本信息准备
# =============================================================================

class VersionInfoStep(PackagingStep):
    """准备版本信息文件（PyInstaller --version-file）。

    委托 Packager._prepare_version_info，与传统 package() 第 10 步等价。

    context 输入: config, output_dir
    context 输出: version_file
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        output_dir = context["output_dir"]
        version_file = self._packager._prepare_version_info(config, output_dir)
        context["version_file"] = version_file
        return context


# =============================================================================
#  Step 11 — 运行时数据文件检测
# =============================================================================

class DataFileDetectStep(PackagingStep):
    """自动检测并包含运行时数据文件（config.env、icon.* 等）。

    委托 Packager._auto_detect_data_files，与传统 package() 第 11 步等价。

    context 输入: config
    context 输出: (无新增字段，副作用写入 config 的数据文件列表)
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        config = context["config"]
        project_dir = config.get("project_dir")
        script_path = config["script_path"]
        self._packager._auto_detect_data_files(config, project_dir, script_path)
        return context


# =============================================================================
#  Step 12a — 配置增强
# =============================================================================

class ConfigEnhanceStep(PackagingStep):
    """填充 qt_framework、GUI 框架标志、版本文件到打包配置。

    委托 Packager._build_pack_config，与传统 _do_package 第 1 关注点等价。

    context 输入: config, version_file
    context 输出: pack_config, tool
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._packager.log("\n" + "=" * 50)
        self._packager.log("第三阶段：打包")
        self._packager.log("=" * 50)

        config = context["config"]
        version_file = context.get("version_file")
        pack_config, tool = self._packager._build_pack_config(config, version_file)
        context["pack_config"] = pack_config
        context["tool"] = tool
        return context


# =============================================================================
#  Step 12b — 图标入口注入
# =============================================================================

class IconInjectStep(PackagingStep):
    """Nuitka 图标入口注入（仅 Nuitka + 图标 + 非自打包）。

    委托 Packager._inject_icon_entry，与传统 _do_package 第 2 关注点等价。

    context 输入: pack_config, tool, output_dir, icon_path
    context 输出: (副作用修改 pack_config 的 script_path)
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._packager._inject_icon_entry(
            context["pack_config"],
            context["tool"],
            context["output_dir"],
            context.get("icon_path"),
        )
        return context


# =============================================================================
#  Step 12c — 执行打包
# =============================================================================

class BuildExecuteStep(PackagingStep):
    """调用 nuitka/pyinstaller 打包器执行打包。

    委托 Packager._execute_build，与传统 _do_package 第 3 关注点等价。

    context 输入: python_path, config, pack_config, tool, output_dir,
                  hidden_imports, exclude_modules, icon_path
    context 输出: success, message
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        success, message = self._packager._execute_build(
            context["python_path"],
            context["config"],
            context["pack_config"],
            context["tool"],
            context["output_dir"],
            context.get("hidden_imports", []),
            context.get("exclude_modules", []),
            context.get("icon_path"),
        )
        context["success"] = success
        context["message"] = message
        return context


# =============================================================================
#  Step 12d — 版本信息后处理
# =============================================================================

class VersionPostProcessStep(PackagingStep):
    """中文版本信息的 rcedit 后处理（含 UPX/PyInstaller-onefile 跳过判定）。

    委托 Packager._post_process_version_info，与传统 _do_package 第 4 关注点等价。
    仅在打包成功时执行。

    context 输入: success, pack_config, tool
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if context.get("success"):
            self._packager._post_process_version_info(
                context["pack_config"], context["tool"]
            )
        return context


# =============================================================================
#  Step 12e — 临时文件清理
# =============================================================================

class TempCleanupStep(PackagingStep):
    """统一清理临时文件（version_info.txt / icon_converted.ico / _ppt_entry.py）。

    委托 Packager._cleanup_temp_files，与传统 _do_package 第 5 关注点等价。

    context 输入: pack_config, version_file, icon_path
    """

    def __init__(self, packager: Any):
        self._packager = packager

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._packager._cleanup_temp_files(
            context["pack_config"],
            context.get("version_file"),
            context.get("icon_path"),
        )
        return context
