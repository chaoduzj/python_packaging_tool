"""
Nuitka 打包器模块

本模块负责使用 Nuitka 进行打包，包括：
- 构建 Nuitka 命令行参数
- 处理隐藏导入和排除模块
- 处理 GCC 编译器配置
- 执行打包过程

功能：
- 支持单文件和目录模式
- 支持 GUI 和控制台模式
- 支持图标和版本信息
- 支持 GCC/MinGW 编译器
- 支持中文路径和中文版本信息处理
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.analyzer_constants import (
    FRAMEWORKS_WITH_DATA_FILES,
    NUITKA_FRAMEWORK_OPTIONS,
    NUITKA_OFFICIAL_PLUGINS,
)
from core.packaging.base import CREATE_NO_WINDOW, BasePackager, verify_tool
from core.packaging.compiler_provider import CompilerProvider
from core.packaging.compressor_provider import CompressorProvider
from utils.constants import has_chinese


class NuitkaPackager(BasePackager):
    """Nuitka 打包器"""

    def __init__(self):
        """初始化 Nuitka 打包器"""
        super().__init__()
        self._pending_version_info: Optional[Dict] = None
        self._compiler_provider = CompilerProvider(log=self.log)
        self._compressor_provider = CompressorProvider(log=self.log)

    # region 版本信息管理

    def get_pending_version_info(self) -> Optional[Dict]:
        """获取待处理的版本信息"""
        return self._pending_version_info

    def set_pending_version_info(self, version_info: Dict) -> None:
        """设置待处理的版本信息"""
        self._pending_version_info = version_info

    def clear_pending_version_info(self) -> None:
        """清除待处理的版本信息"""
        self._pending_version_info = None

    # endregion

    def verify_nuitka(self, python_path: str) -> Tuple[bool, str]:
        """验证 Nuitka 是否可用"""
        return verify_tool(python_path, "nuitka")

    def build_command(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        script_name: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
        gcc_path: Optional[str] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        构建 Nuitka 命令行参数

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            script_name: 脚本名称
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径
            gcc_path: GCC 编译器路径

        Returns:
            (命令行参数列表, 环境变量字典)
        """
        script_path = config["script_path"]

        cmd = [
            python_path,
            "-m",
            "nuitka",
            "--standalone",
            f"--output-dir={output_dir}",
            f"--output-filename={script_name}.exe",
        ]

        # 单文件模式
        if config.get("onefile", True):
            cmd.append("--onefile")

        # 控制台模式
        if not config.get("console", False):
            cmd.append("--windows-console-mode=disable")

        # 图标
        if icon_path and os.path.exists(icon_path):
            cmd.append(f"--windows-icon-from-ico={icon_path}")

        # 自动包含原始图标文件，确保运行时可用
        # 同时嵌入到多个路径，覆盖各种图标查找模式：
        #   1. icon.ico — 根目录（最常见的查找位置）
        #   2. resources/icons/icon.ico — 子目录查找模式
        original_icon = config.get("icon_path") or config.get("icon")
        if original_icon and os.path.exists(original_icon):
            basename = os.path.basename(original_icon)

            # 如果 icon_path 是转换后的 icon_converted.ico 且不同于原始图标，
            # 则只包含转换后的版本（作为 icon.ico），避免重复
            if icon_path and icon_path != original_icon and icon_path.endswith(".ico"):
                if "icon_converted.ico" in os.path.basename(icon_path):
                    cmd.append(f"--include-data-file={icon_path}=icon.ico")
                    cmd.append(f"--include-data-file={icon_path}=resources/icons/icon.ico")
                    self.log("  已自动包含图标资源: icon.ico (转换后)")
                else:
                    cmd.append(f"--include-data-file={original_icon}={basename}")
                    cmd.append(f"--include-data-file={original_icon}=resources/icons/{basename}")
                    self.log(f"  已自动包含图标资源: {basename}")
            else:
                cmd.append(f"--include-data-file={original_icon}={basename}")
                cmd.append(f"--include-data-file={original_icon}=resources/icons/{basename}")
                self.log(f"  已自动包含图标资源: {basename}")
                ext = os.path.splitext(original_icon)[1]
                std_name = f"icon{ext}"
                if basename.lower() != std_name.lower():
                    cmd.append(f"--include-data-file={original_icon}={std_name}")
                    cmd.append(f"--include-data-file={original_icon}=resources/icons/{std_name}")

        # 自动包含目标项目的 resources/ 目录（如果存在）
        # 注意：这是目标项目的 resources/，不是打包工具自身的 resources/
        project_dir = config.get("project_dir", "")
        if project_dir:
            target_resources = os.path.join(project_dir, "resources")
            if os.path.isdir(target_resources):
                data_arg = f"--include-data-dir={target_resources}=resources"
                if data_arg not in cmd:
                    cmd.append(data_arg)
                    self.log("  已包含目标项目资源目录: resources/")

        # 隐藏导入（使用 --include-module）
        for hidden in hidden_imports:
            # 检查是否是包还是模块
            if "." in hidden:
                cmd.append(f"--include-module={hidden}")
            else:
                cmd.append(f"--include-package={hidden}")

        # 排除模块
        for exclude in exclude_modules:
            cmd.append(f"--nofollow-import-to={exclude}")

        # 启用插件（根据检测到的框架）
        qt_framework = config.get("qt_framework")
        if qt_framework:
            qt_lower = qt_framework.lower()
            if qt_lower in NUITKA_OFFICIAL_PLUGINS:
                cmd.append(f"--enable-plugin={NUITKA_OFFICIAL_PLUGINS[qt_lower]}")
            # 显式包含 Qt 插件，确保运行时所需的平台插件（platforms/qwindows.dll）
            # 等被一并打包。Qt 框架启动时必须找到 platforms 插件，否则会报
            # "no Qt platform plugin could be initialized"。
            # "sensible" 已涵盖 platforms/iconengines/imageformats 等，此处显式声明
            # 以避免不同 Nuitka 版本默认行为差异导致平台插件缺失。
            if qt_lower in ("pyqt6", "pyqt5", "pyside6", "pyside2"):
                cmd.append("--include-qt-plugins=sensible,styles")

        if config.get("uses_tkinter"):
            cmd.append("--enable-plugin=tk-inter")

        if config.get("uses_numpy"):
            cmd.append("--enable-plugin=numpy")

        if config.get("uses_matplotlib"):
            cmd.append("--enable-plugin=matplotlib")

        # UPX 压缩（Nuitka 默认不开启 UPX，需通过插件显式启用）
        # Nuitka 的 UPX 插件会压缩 exe 中的 DLL 和二进制资源，
        # 可显著减小 onefile 的最终体积（通常 20-40% 缩小）
        enable_upx = config.get("upx", False)
        is_onefile = config.get("onefile", True)
        if enable_upx:
            upx_exe = self._ensure_upx_available(python_path)
            if upx_exe:
                self.log(f"  UPX 可用: {upx_exe}")
                # 显式指定 UPX 路径，避免 Nuitka 在 PATH 中找不到而报 FATAL
                cmd.append(f"--upx-binary={upx_exe}")
                cmd.append("--enable-plugin=upx")
                if is_onefile:
                    # 禁用 onefile 自带 zlib 压缩，让 UPX 独立压缩 exe
                    # Nuitka 默认 onefile 已压缩，UPX 无法对已压缩数据再压缩，
                    # 必须禁用内置压缩才能让 UPX 生效
                    cmd.append("--onefile-no-compression")
            else:
                self.log("  UPX 压缩: 未找到 UPX 且自动安装失败，已跳过")
                self.log("  可手动执行 pip install upx 或从 https://upx.github.io/ 下载并加入 PATH")

        # 通用 GUI 框架选项（自动检测并应用）
        detected_gui_frameworks = config.get("detected_gui_frameworks", set())
        applied_frameworks: set = set()
        for fw_name in detected_gui_frameworks:
            fw_lower = fw_name.lower()
            if fw_lower in NUITKA_FRAMEWORK_OPTIONS:
                for arg in NUITKA_FRAMEWORK_OPTIONS[fw_lower]:
                    if arg not in cmd:
                        cmd.append(arg)
                applied_frameworks.add(fw_name)
        if applied_frameworks:
            self.log(f"  已为框架自动添加 Nuitka 选项: {', '.join(sorted(applied_frameworks))}")

        # 自动添加框架数据文件（--include-data-dir）
        # 源路径可能是相对路径（如 wx/locale），此时需要基于 Python 的
        # site-packages 目录解析，因为项目根目录下通常不存在这些目录。
        for fw_name in detected_gui_frameworks:
            fw_lower = fw_name.lower()
            if fw_lower in FRAMEWORKS_WITH_DATA_FILES:
                for src_pattern, dest_name in FRAMEWORKS_WITH_DATA_FILES[fw_lower]:
                    resolved_src = self._resolve_framework_data_path(src_pattern, python_path)
                    if not resolved_src or not os.path.exists(resolved_src):
                        self.log(f"  跳过框架数据目录（不存在）: {src_pattern}")
                        continue
                    data_arg = f"--include-data-dir={resolved_src}={dest_name}"
                    if data_arg not in cmd:
                        cmd.append(data_arg)
                        self.log(f"  已添加框架数据目录: {resolved_src} -> {dest_name}")

        # 版本信息
        version_info = config.get("version_info", {})
        if version_info:
            self.log(f"检测到版本信息配置: {list(version_info.keys())}")
            self._add_version_info_to_cmd(cmd, version_info, config)
        else:
            self.log("未检测到版本信息配置")

        # 额外数据文件
        extra_data = config.get("extra_data", [])
        for data in extra_data:
            if os.path.isdir(data):
                cmd.append(f"--include-data-dir={data}={os.path.basename(data)}")
            elif os.path.isfile(data):
                cmd.append(f"--include-data-file={data}={os.path.basename(data)}")

        # Nuitka 高级选项
        nuitka_adv = config.get("nuitka_advanced_options", {})
        if nuitka_adv:
            # 自动下载（默认开启，避免非交互式环境下 Dependency Walker 下载失败）
            if nuitka_adv.get("assume_yes_downloads", True):
                cmd.append("--assume-yes-for-downloads")

            # 编译优化
            if nuitka_adv.get("lto", True):
                cmd.append("--lto=yes")
            else:
                cmd.append("--lto=no")

            if nuitka_adv.get("low_memory", False):
                cmd.append("--low-memory")

            jobs = nuitka_adv.get("jobs")
            if jobs is not None and jobs > 0:
                cmd.append(f"--jobs={jobs}")

            # 显示选项
            if nuitka_adv.get("show_progress", True):
                cmd.append("--show-progress")
            if nuitka_adv.get("show_memory", True):
                cmd.append("--show-memory")
            if nuitka_adv.get("show_scons", False):
                cmd.append("--show-scons")

            # Python 标志
            if nuitka_adv.get("python_no_docstrings", True):
                cmd.append("--python-flag=no_docstrings")
            if nuitka_adv.get("python_no_asserts", True):
                cmd.append("--python-flag=no_asserts")
            if nuitka_adv.get("python_no_warnings", False):
                cmd.append("--python-flag=no_warnings")
            if nuitka_adv.get("python_no_annotations", False):
                cmd.append("--python-flag=no_annotations")

            # Anti-bloat
            if nuitka_adv.get("noinclude_pytest", True):
                cmd.append("--noinclude-pytest-mode=nofollow")
            if nuitka_adv.get("noinclude_setuptools", True):
                cmd.append("--noinclude-setuptools-mode=nofollow")
            if nuitka_adv.get("noinclude_unittest", True):
                cmd.append("--noinclude-unittest-mode=nofollow")
            if nuitka_adv.get("noinclude_ipython", True):
                cmd.append("--noinclude-IPython-mode=nofollow")
            if nuitka_adv.get("noinclude_dask", True):
                cmd.append("--noinclude-dask-mode=nofollow")

            # 部署模式
            if nuitka_adv.get("deployment", False):
                cmd.append("--deployment")

            # Onefile 临时目录
            tempdir_spec = nuitka_adv.get("onefile_tempdir_spec", "")
            if tempdir_spec:
                # 检查 spec 中是否包含需要 metadata 的占位符
                metadata_placeholders = {"{COMPANY}", "{PRODUCT}", "{VERSION}"}
                used_placeholders = {p for p in metadata_placeholders if p in tempdir_spec}

                if used_placeholders:
                    # 从 version_info 获取对应的 metadata
                    version_info = config.get("version_info") or {}
                    company = version_info.get("company_name", "").strip()
                    product = version_info.get("product_name", "").strip()
                    version = version_info.get("version", "").strip()

                    # 为缺少的占位符提供默认安全属性，避免 Nuitka FATAL 错误
                    if "{COMPANY}" in used_placeholders:
                        safe_company = company or "MyCompany"
                        cmd.append(f"--company-name={safe_company}")
                        if not company:
                            self.log("  警告: tempdir_spec 包含 {COMPANY} 但未配置公司名，使用默认属性 'MyCompany'")

                    if "{PRODUCT}" in used_placeholders:
                        safe_product = product or "MyProduct"
                        cmd.append(f"--product-name={safe_product}")
                        if not product:
                            self.log("  警告: tempdir_spec 包含 {PRODUCT} 但未配置产品名，使用默认属性 'MyProduct'")

                    if "{VERSION}" in used_placeholders:
                        safe_version = version or "1.0.0"
                        cmd.append(f"--file-version={safe_version}")
                        if not version:
                            self.log("  警告: tempdir_spec 包含 {VERSION} 但未配置版本号，使用默认属性 '1.0.0'")

                cmd.append(f"--onefile-tempdir-spec={tempdir_spec}")

            # 编译报告
            if nuitka_adv.get("generate_report", False):
                report_path = nuitka_adv.get("report_path", "") or "compilation-report.xml"
                cmd.append(f"--report={report_path}")

            # 用户包配置文件
            user_config = nuitka_adv.get("user_package_config", "")
            if user_config:
                cmd.append(f"--user-package-configuration-file={user_config}")
        else:
            # nuitka_advanced_options 未配置时，默认开启自动下载，
            # 避免非交互式环境下 Dependency Walker 提示失败
            cmd.append("--assume-yes-for-downloads")

        # 添加脚本路径
        cmd.append(script_path)

        # 环境变量
        env = os.environ.copy()

        # 设置 GCC 编译器（委托给 CompilerProvider）
        if gcc_path:
            actual_gcc_path = self._compiler_provider._resolve_executable(gcc_path)
            if actual_gcc_path:
                gcc_dir = os.path.dirname(actual_gcc_path)
                env["CC"] = actual_gcc_path
                env["PATH"] = gcc_dir + os.pathsep + env.get("PATH", "")
                cmd.append("--mingw64")

                cache_downloads = os.path.join(self._compiler_provider.get_nuitka_cache_dir(), "downloads")
                if actual_gcc_path.startswith(cache_downloads):
                    env.setdefault("NUITKA_CACHE_DIR_DOWNLOADS", cache_downloads)

        return cmd, env

    def _resolve_gcc_executable(self, gcc_path: str) -> Optional[str]:
        """解析 GCC 可执行文件路径（委托给 CompilerProvider）。"""
        return self._compiler_provider._resolve_executable(gcc_path)

    def _is_gcc_download_failure(self) -> bool:
        """判断 Nuitka 失败是否由 GCC 工具链下载/解压损坏引起。

        匹配 Nuitka getCachedDownload() 在 zip 损坏时输出的特征消息：
        - "Problem with the downloaded zip file, deleting it."
        - "Error, need 'mingw64\\bin\\gcc.exe' as extracted from ..."
        """
        tail = "\n".join(self._output_tail)
        return (
            "Problem with the downloaded zip file" in tail
            or "need 'mingw64\\bin\\gcc.exe'" in tail
            or "need 'mingw32\\bin\\gcc.exe'" in tail
        )

    def _add_version_info_to_cmd(
        self,
        cmd: List[str],
        version_info: Dict,
        config: Dict,
    ) -> None:
        """
        添加版本信息到 Nuitka 命令行。

        Windows 下 subprocess.Popen 使用 CreateProcessW 传递宽字符参数，
        Nuitka 能正确处理 UTF-8 中文版本信息。日志中显示的 `????` 仅是
        控制台回显的编码问题，不影响实际传参。

        standalone 模式额外通过 rcedit 后处理确保中文版本信息完全正确。
        """
        # 复用 utils.constants.has_chinese（覆盖基本区 + CJK 扩展区）
        has_chinese_info = any(has_chinese(str(v)) for v in version_info.values())

        # 始终将非空字段传给 Nuitka（CreateProcessW 正确处理 UTF-8）
        ver = version_info.get("version") or version_info.get("file_version", "")
        if ver:
            cmd.append(f"--file-version={ver}")
            cmd.append(f"--product-version={ver}")

        if version_info.get("product_name"):
            cmd.append(f"--product-name={version_info['product_name']}")

        if version_info.get("company_name"):
            cmd.append(f"--company-name={version_info['company_name']}")

        if version_info.get("file_description"):
            cmd.append(f"--file-description={version_info['file_description']}")

        if version_info.get("copyright"):
            cmd.append(f"--copyright={version_info['copyright']}")

        # 注册 pending 信息供 standalone 模式 rcedit 后处理（双重保障）
        if has_chinese_info:
            self._pending_version_info = version_info.copy()

    def package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
        gcc_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        执行 Nuitka 打包

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径
            gcc_path: GCC 编译器路径

        Returns:
            (是否成功, 消息)
        """
        # 验证 Nuitka
        is_available, version_info = self.verify_nuitka(python_path)
        if not is_available:
            return False, f"Nuitka 不可用: {version_info}"

        self.log(f"✓ Nuitka 版本: {version_info}")

        # Windows 下提前预置 Nuitka 精确版本的 GCC 工具链。
        # Nuitka >= 2.1 仅接受其版本化缓存目录中的精确版本 GCC
        # （downloads/gcc/<arch>/<release-tag>/mingw64），其他位置的 GCC
        # 一律被忽略；且 Nuitka 自带下载器无重试机制，zip 损坏会直接
        # FATAL。提前用内置下载器（多线程+重试+完整性校验）就位后，
        # Nuitka 检测到 gcc.exe 已存在会完全跳过下载环节。
        if sys.platform == "win32":
            provisioned_gcc = self._compiler_provider.ensure_nuitka_gcc(
                python_path, cancel_check=self._is_cancelled
            )
            if provisioned_gcc and not gcc_path:
                gcc_path = provisioned_gcc

        # 如果没有指定 GCC 路径，自动使用 Nuitka 缓存中的 mingw64
        # 防止 Nuitka 4.x 因版本不匹配而重复下载 GCC
        if not gcc_path:
            gcc_path = self.find_gcc()
            if gcc_path:
                self.log(f"使用 Nuitka 缓存中的 GCC: {gcc_path}")

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名
        if config.get("program_name"):
            script_name = config["program_name"]
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
        else:
            script_name = Path(script_path).stem

        # 检测中文字符，使用临时英文名
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in script_name)
        temp_name = None
        if has_chinese:
            import uuid

            temp_name = f"temp_{uuid.uuid4().hex[:8]}"
            self.log(f"检测到中文名称，使用临时名称打包: {temp_name}")
            build_name = temp_name
        else:
            build_name = script_name

        self.log(f"输出文件名: {script_name}")

        # 构建命令
        cmd, env = self.build_command(
            python_path,
            config,
            output_dir,
            build_name,
            hidden_imports,
            exclude_modules,
            icon_path,
            gcc_path,
        )

        self.log(f"\n执行命令: {' '.join(cmd[:5])}...")

        try:
            # GCC 下载损坏属于可恢复失败，最多执行 2 次（首次 + 重试）
            for attempt in (1, 2):
                self._output_tail = []

                # 执行打包
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                if self.process_callback:
                    self.process_callback(process)

                # 实时输出日志
                cancelled, msg = self._read_process_output(process)
                if cancelled:
                    return False, msg

                if process.returncode == 0:
                    break

                # Nuitka 自带下载器无重试机制，GCC 压缩包损坏会直接 FATAL。
                # 检测到该特征时，用内置下载器重新预置 GCC 后重试一次。
                if attempt == 1 and self._is_gcc_download_failure():
                    self.log("\n检测到 Nuitka 下载的 GCC 压缩包损坏，正在重新预置 GCC 并重试...")
                    self._compiler_provider.ensure_nuitka_gcc(
                        python_path, cancel_check=self._is_cancelled
                    )
                    continue

                error_msg = f"Nuitka 执行失败，返回码: {process.returncode}"
                if self._is_gcc_download_failure():
                    error_msg += (
                        "\n\n原因: Nuitka 下载 GCC 工具链失败（网络不稳定导致压缩包损坏）。"
                        "\n建议: 检查网络/代理后重试，或从以下地址手动下载对应版本并解压到 Nuitka 缓存目录:"
                        "\nhttps://github.com/brechtsanders/winlibs_mingw/releases"
                    )
                return False, error_msg

            # 检查结果
            if process.returncode == 0:
                # 查找输出文件
                exe_path = self._find_output_exe(output_dir, build_name, config)

                if exe_path and os.path.exists(exe_path):
                    # 如果使用了临时名称，重命名为最终名称
                    if temp_name:
                        is_onefile = config.get("onefile", True)
                        if is_onefile:
                            # onefile 模式：输出为单个 exe，直接重命名
                            exe_path = self._rename_onefile_exe(exe_path, script_name)
                        else:
                            # standalone 模式：输出为 .dist 目录，
                            # 必须同时重命名 exe 和 .dist 目录，
                            # 否则 exe 与依赖（包含 Qt platforms 插件）被遗留在
                            # temp_xxx.dist 中，用户易误拆分导致运行时找不到插件
                            #
                            # 注意：此处将 .dist 目录重命名为 script_name.dist，
                            # 上层 Packager._rename_nuitka_dist 会进一步判断 —— 仅当
                            # program_name 与 script_name 不同时才会再次重命名为
                            # program_name.dist。两层重命名互不冲突，因每层都做了
                            # "目标已是期望名称则跳过" 的短路判断（见 _rename_standalone_dist
                            # 与 Packager._rename_nuitka_dist）。
                            exe_path = self._rename_standalone_dist(exe_path, build_name, script_name)

                    self._last_exe_path = exe_path

                    # 清理构建缓存
                    self._clean_build_cache(output_dir, build_name, config)

                    return True, f"打包成功！\n\n输出文件: {exe_path}"
                else:
                    return False, "打包完成，但未找到输出文件"
            else:
                return False, f"Nuitka 执行失败，返回码: {process.returncode}"

        except Exception as e:
            return False, f"执行 Nuitka 时出错: {str(e)}"

    def _rename_onefile_exe(self, exe_path: str, final_name: str) -> str:
        """onefile 模式：将临时名称的单个 exe 重命名为最终名称。

        Args:
            exe_path: 当前 exe 路径（使用临时名）
            final_name: 最终文件名（不含扩展名）

        Returns:
            重命名后的 exe 路径（失败时返回原路径）
        """
        final_exe_path = os.path.join(os.path.dirname(exe_path), f"{final_name}.exe")
        try:
            if os.path.exists(final_exe_path):
                os.remove(final_exe_path)
            os.rename(exe_path, final_exe_path)
            self.log(f"已重命名为: {final_name}.exe")
            return final_exe_path
        except Exception as e:
            self.log(f"⚠️ 重命名失败: {e}")
            return exe_path

    def _rename_standalone_dist(self, exe_path: str, build_name: str, final_name: str) -> str:
        """standalone 模式：同时重命名 .dist 目录和其中的 exe。

        standalone 模式下 Qt 运行时依赖 exe 同级目录下的 PyQt6/Qt6/plugins/
        插件目录（如 platforms/qwindows.dll）。若仅重命名 exe 而保留
        temp_xxx.dist 目录名，用户会看到一个看似临时文件夹的目录，
        易将 exe 单独拷贝出来，导致 exe 与插件分离，进而报
        "no Qt platform plugin could be initialized" 错误。

        Args:
            exe_path: 当前 exe 路径（位于 temp_xxx.dist 内）
            build_name: 构建时使用的临时名（如 temp_xxx）
            final_name: 最终名称（不含扩展名）

        Returns:
            重命名后位于新 .dist 目录内的 exe 路径（失败时返回原路径）
        """
        dist_dir = os.path.dirname(exe_path)
        output_dir = os.path.dirname(dist_dir)

        # 预期的源 .dist 目录名为 build_name.dist，目标为 final_name.dist
        expected_dist = os.path.join(output_dir, f"{build_name}.dist")
        final_dist = os.path.join(output_dir, f"{final_name}.dist")

        # 1) 先重命名 dist 内的 exe
        renamed_exe_in_src = os.path.join(dist_dir, f"{final_name}.exe")
        try:
            if os.path.abspath(exe_path) != os.path.abspath(renamed_exe_in_src):
                if os.path.exists(renamed_exe_in_src):
                    os.remove(renamed_exe_in_src)
                os.rename(exe_path, renamed_exe_in_src)
            exe_path = renamed_exe_in_src
            self.log(f"已重命名 exe 为: {final_name}.exe")
        except Exception as e:
            self.log(f"⚠️ exe 重命名失败: {e}")
            return exe_path

        # 2) 重命名 .dist 目录本身
        # 仅当当前 dist 目录确实是临时名且与目标名不同时才重命名
        if os.path.abspath(dist_dir) == os.path.abspath(final_dist):
            return exe_path
        if os.path.abspath(dist_dir) != os.path.abspath(expected_dist):
            # dist 目录名不符合预期，为安全起见不重命名目录
            self.log(f"  保留 dist 目录名: {os.path.basename(dist_dir)}")
            return exe_path
        try:
            if os.path.exists(final_dist):
                shutil.rmtree(final_dist)
            os.rename(dist_dir, final_dist)
            exe_path = os.path.join(final_dist, f"{final_name}.exe")
            self.log(f"已重命名输出目录为: {final_name}.dist")
        except Exception as e:
            self.log(f"⚠️ 输出目录重命名失败（exe 仍可用，但目录名为临时名）: {e}")
        return exe_path

    @classmethod
    def _get_tools_dir(cls) -> Optional[str]:
        """获取项目 tools/ 目录的绝对路径。

        优先级：
        1. 当前文件所在项目目录下的 tools/
        2. 打包后 sys._MEIPASS（PyInstaller）/ __compiled__.containing_dir（Nuitka）下的 tools/
        3. exe 同目录下的 tools/
        """
        candidates = []
        # 源码运行：基于本文件的路径
        try:
            src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidates.append(os.path.join(src_dir, "tools"))
        except Exception:
            pass
        # PyInstaller 打包：_MEIPASS
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(getattr(sys, "_MEIPASS"), "tools"))
        # Nuitka 打包：__compiled__.containing_dir（onefile 解包临时目录）
        try:
            _nc = __compiled__  # type: ignore[name-defined] # noqa: F821
            candidates.append(os.path.join(_nc.containing_dir, "tools"))  # type: ignore[union-attr]
        except Exception:
            pass
        # 通用 frozen：exe 同目录
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "tools"))
        for c in candidates:
            if os.path.isdir(c):
                return c
        return None

    def _ensure_upx_available(self, python_path: str) -> Optional[str]:
        """确保 UPX 可用（委托给 CompressorProvider）。"""
        return self._compressor_provider.resolve(python_path)

    @classmethod
    def _get_upx_cache_dir(cls) -> str:
        """获取 UPX 缓存目录（委托给 CompressorProvider）。"""
        return CompressorProvider.get_cache_dir()

    @classmethod
    def _log_static(cls, message: str) -> None:
        """静态方法版本的安全日志输出，避免依赖实例级 log 回调。"""
        try:
            print(message)
        except Exception:
            pass

    @staticmethod
    def _resolve_framework_data_path(
        src_pattern: str,
        python_path: str,
    ) -> Optional[str]:
        """
        解析框架数据文件的源路径。

        对于相对路径（如 wx/locale），在项目的 site-packages 中查找。
        对于绝对路径，直接返回（如果存在）。
        """
        if os.path.isabs(src_pattern):
            return src_pattern if os.path.exists(src_pattern) else None

        # 相对路径：在 Python 环境中查找
        try:
            import subprocess

            result = subprocess.run(
                [
                    python_path,
                    "-c",
                    "import sys, importlib.util; "
                    "root_pkg = sys.argv[1].split('/')[0]; "
                    "spec = importlib.util.find_spec(root_pkg); "
                    "print(spec.submodule_search_locations[0] if spec and spec.submodule_search_locations else '', end='')",
                    src_pattern,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0 and result.stdout.strip():
                site_root = result.stdout.strip()
                resolved = os.path.join(site_root, src_pattern.split("/", 1)[1] if "/" in src_pattern else src_pattern)
                if os.path.exists(resolved):
                    return resolved
        except Exception:
            pass

        return None

    def _find_output_exe(
        self,
        output_dir: str,
        script_name: str,
        config: Dict,
    ) -> Optional[str]:
        """
        查找输出的 exe 文件

        Args:
            output_dir: 输出目录
            script_name: 脚本名称
            config: 打包配置

        Returns:
            exe 文件路径
        """
        is_onefile = config.get("onefile", True)

        if is_onefile:
            # onefile 模式：优先 output_dir 根目录下的单文件 exe
            patterns = [
                os.path.join(output_dir, f"{script_name}.exe"),
            ]
        else:
            # standalone 模式：优先 .dist 目录下的 exe
            # 注意：根目录下可能有遗留的 onefile exe，必须优先匹配 .dist
            patterns = [
                os.path.join(output_dir, f"{script_name}.dist", f"{script_name}.exe"),
                os.path.join(output_dir, script_name, f"{script_name}.exe"),
            ]

        for pattern in patterns:
            if os.path.exists(pattern):
                return pattern

        # 搜索输出目录（兜底）
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file == f"{script_name}.exe":
                    return os.path.join(root, file)

        return None

    def _clean_build_cache(self, output_dir: str, script_name: str, config: Optional[Dict] = None) -> None:
        """
        清理 Nuitka 构建缓存

        Args:
            output_dir: 输出目录
            script_name: 程序名称（输出文件名）
            config: 打包配置（用于获取入口脚本名）
        """
        # 收集需要清理的目录名前缀
        # Nuitka 使用入口脚本名（不含扩展名）作为临时目录名，而不是输出文件名
        names_to_clean = {script_name}

        if config and config.get("script_path"):
            # 获取入口脚本的基本名称（不含扩展名）
            entry_script_name = Path(config["script_path"]).stem
            names_to_clean.add(entry_script_name)

        # 同时扫描输出目录，查找所有 .build、.dist、.onefile-build 目录
        # 注意：.dist 在 standalone 模式下是最终输出，不应加入清理列表，
        # 此处仅收集居名不一致时的 .build 和 .onefile-build。
        #
        # 安全限制：仅清理与当前构建（script_name / entry_script_name）同名的目录，
        # 避免在共享输出目录（如 D:\builds\）中误删其他项目的产物。
        onefile_config = config.get("onefile", True) if config else True
        # 当前构建可能产生的目录名前缀白名单
        current_build_prefixes = set(names_to_clean)
        try:
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                if not os.path.isdir(item_path):
                    continue
                item_base = item.rsplit(".", 1)[0] if "." in item else item
                # 仅当目录名前缀属于本次构建产物时才考虑清理
                if item_base not in current_build_prefixes:
                    continue
                if item.endswith(".build") or item.endswith(".onefile-build"):
                    names_to_clean.add(item_base)
                elif item.endswith(".dist") and onefile_config:
                    # onefile 模式下 .dist 才是中间产物，可加入清理
                    names_to_clean.add(item_base)
        except Exception:
            pass

        # 判断是否为 onefile 模式：onefile 模式下 .dist 是编译中间产物可删除；
        # standalone 模式下 .dist 是最终输出目录，必须保留
        is_onefile = bool(config and config.get("onefile", True))

        # 清理所有匹配的目录
        for name in names_to_clean:
            # 清理 .build 目录（任何模式下都是临时编译目录，可安全删除）
            build_dir = os.path.join(output_dir, f"{name}.build")
            if os.path.exists(build_dir):
                try:
                    shutil.rmtree(build_dir)
                    self.log(f"已清理构建缓存: {build_dir}")
                except Exception as e:
                    self.log(f"⚠️ 清理构建缓存失败: {e}")

            # 清理 .dist 目录：
            # - onefile 模式：.dist 是中间产物，最终输出为单个 .exe，可删除
            # - standalone 模式：.dist 就是最终输出目录（含 exe + 依赖），必须保留
            if is_onefile:
                dist_dir = os.path.join(output_dir, f"{name}.dist")
                if os.path.exists(dist_dir):
                    try:
                        shutil.rmtree(dist_dir)
                        self.log(f"已清理 dist 中间目录: {dist_dir}")
                    except Exception as e:
                        self.log(f"⚠️ 清理 dist 目录失败: {e}")

            # 清理 .onefile-build 目录（仅 onefile 模式产生）
            onefile_build_dir = os.path.join(output_dir, f"{name}.onefile-build")
            if os.path.exists(onefile_build_dir):
                try:
                    shutil.rmtree(onefile_build_dir)
                    self.log(f"已清理构建缓存: {onefile_build_dir}")
                except Exception as e:
                    self.log(f"⚠️ 清理构建缓存失败: {e}")

        # 清理 Nuitka 全局编译缓存（clcache、ccache 等）
        nuitka_options = config.get("nuitka_advanced_options", {}) if config else {}
        if nuitka_options.get("clean_cache_after_build", False):
            self._clean_nuitka_global_cache(nuitka_options.get("custom_cache_dir", ""))

        # 注意：不再此处清理 icon_converted.ico，保留给后处理使用
        # 由 packager.py 在完成所有操作后统一清理

    @staticmethod
    def _get_default_nuitka_cache_dir() -> str:
        """获取 Nuitka 默认缓存目录（委托给 CompilerProvider）。"""
        return CompilerProvider.get_nuitka_cache_dir()

    def _clean_nuitka_global_cache(self, custom_cache_dir: str = "") -> None:
        """
        清理 Nuitka 全局编译缓存目录

        清理的子目录包括：
        - clcache   (Windows MSVC 编译缓存)
        - ccache    (GCC/Clang 编译缓存)
        - bytecode  (字节码缓存)
        - dll_dependencies (DLL 依赖分析缓存)

        不清理的子目录：
        - downloads (已下载的工具链，如 MinGW GCC，清理后需重新下载)

        Args:
            custom_cache_dir: 用户自定义的缓存根目录，为空则使用默认位置
        """
        # 确定缓存根目录
        if custom_cache_dir and os.path.isdir(custom_cache_dir):
            cache_root = custom_cache_dir
        else:
            cache_root = self._get_default_nuitka_cache_dir()

        if not os.path.isdir(cache_root):
            self.log(f"Nuitka 全局缓存目录不存在，跳过清理: {cache_root}")
            return

        self.log(f"\n开始清理 Nuitka 全局编译缓存: {cache_root}")

        # 需要清理的编译缓存子目录
        # 注意：保留 downloads 目录，该目录包含已下载的工具链（如 MinGW GCC），
        # 清理后需要重新下载，耗时且浪费带宽
        cache_subdirs = [
            "clcache",
            "ccache",
            "bytecode",
            "dll_dependencies",
        ]

        total_cleaned_size = 0

        for subdir_name in cache_subdirs:
            subdir_path = os.path.join(cache_root, subdir_name)
            if not os.path.isdir(subdir_path):
                continue

            # 计算目录大小
            dir_size = 0
            try:
                for dirpath, _dirnames, filenames in os.walk(subdir_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            dir_size += os.path.getsize(fp)
                        except OSError:
                            pass
            except Exception:
                pass

            # 执行清理
            try:
                shutil.rmtree(subdir_path)
                size_mb = dir_size / (1024 * 1024)
                total_cleaned_size += dir_size
                self.log(f"  ✓ 已清理 {subdir_name} ({size_mb:.1f} MB)")
            except Exception as e:
                self.log(f"  ⚠️ 清理 {subdir_name} 失败: {e}")

        if total_cleaned_size > 0:
            total_mb = total_cleaned_size / (1024 * 1024)
            self.log(f"  共释放空间: {total_mb:.1f} MB")
        else:
            self.log("  未发现需要清理的编译缓存")

    def extract_gcc(self, gcc_zip_path: str, extract_base_dir: str) -> Optional[str]:
        """解压 GCC 工具链（委托给 CompilerProvider）。"""
        return self._compiler_provider.extract_zip(gcc_zip_path, extract_base_dir)

    def find_gcc(self) -> Optional[str]:
        """查找系统中的 GCC 编译器（委托给 CompilerProvider）。

        同时覆盖"在 Nuitka 缓存中查找"场景——CompilerProvider.resolve()
        已包含缓存目录查找逻辑，故合并原 _find_cached_gcc。
        """
        return self._compiler_provider.resolve()

    def verify_gcc(self, gcc_path: str) -> Tuple[bool, str]:
        """验证 GCC 是否可用（委托给 CompilerProvider）。"""
        return self._compiler_provider.verify(gcc_path)

    def get_nuitka_version_info(
        self,
        python_path: str,
    ) -> Dict[str, Any]:
        """
        获取 Nuitka 版本信息

        Args:
            python_path: Python 解释器路径

        Returns:
            版本信息字典
        """
        info = {
            "version": None,
            "supports_onefile": False,
            "supports_plugins": False,
        }

        try:
            result = subprocess.run(
                [python_path, "-m", "nuitka", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if result.returncode == 0:
                version_str = result.stdout.strip().split("\n")[0]
                info["version"] = version_str

                # 解析版本号
                import re

                match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
                if match:
                    major = int(match.group(1))
                    minor = int(match.group(2))
                    patch = int(match.group(3))

                    # Nuitka 0.6.8+ 支持 onefile
                    if (major, minor, patch) >= (0, 6, 8):
                        info["supports_onefile"] = True

                    # Nuitka 0.6.0+ 支持插件
                    if (major, minor) >= (0, 6):
                        info["supports_plugins"] = True

        except Exception:
            pass

        return info
