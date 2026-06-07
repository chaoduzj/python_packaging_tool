"""
cx_Freeze 打包器模块

本模块负责使用 cx_Freeze 进行打包，包括：
- 构建 cx_Freeze 命令行参数
- 处理隐藏导入和排除模块
- 处理数据文件和资源
- 执行打包过程

功能：
- 支持控制台和 GUI 模式
- 支持图标和版本信息（通过 rcedit 后处理）
- 不支持真正的单文件模式（输出始终为目录）
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.packaging.base import CREATE_NO_WINDOW, BasePackager, verify_tool


class CxFreezePackager(BasePackager):
    """cx_Freeze 打包器"""

    def __init__(self):
        """初始化 cx_Freeze 打包器"""
        super().__init__()

    def verify_cx_freeze(self, python_path: str) -> Tuple[bool, str]:
        """验证 cx_Freeze 是否可用"""
        return verify_tool(python_path, "cx_Freeze")

    def build_command(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        script_name: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
    ) -> List[str]:
        """
        构建 cx_Freeze 命令行参数

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            script_name: 脚本名称
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径

        Returns:
            命令行参数列表
        """
        script_path = config["script_path"]
        project_dir = config.get("project_dir") or os.path.dirname(os.path.abspath(script_path))

        cmd = [
            python_path,
            "-m", "cx_Freeze",
            script_path,
            "--target-dir", output_dir,
            f"--target-name={script_name}",
        ]

        # 控制台模式
        if not config.get("console", False):
            cmd.append("--base=Win32GUI")
        else:
            cmd.append("--base=Console")

        # 图标
        if icon_path and os.path.exists(icon_path):
            cmd.append(f"--icon={icon_path}")

        # 单文件模式警告（cx_Freeze 不支持真正的单文件）
        if config.get("onefile", True):
            self.log("⚠️ cx_Freeze 不支持单文件模式，将以目录模式输出")

        # 项目路径（类似 PyInstaller --paths），跳过与输出目录相同的路径
        norm_project = os.path.normpath(project_dir)
        norm_output = os.path.normpath(output_dir)
        if norm_project != norm_output:
            cmd.append(f"--include-path={project_dir}")

        # 隐藏导入
        if hidden_imports:
            cmd.append(f"--include-modules={','.join(hidden_imports)}")

        # 自动收集项目本地包的所有子模块
        local_packages = self._get_local_packages(project_dir)
        if local_packages:
            cmd.append(f"--packages={','.join(local_packages)}")

        # 排除模块
        if exclude_modules:
            cmd.append(f"--exclude-modules={','.join(exclude_modules)}")

        # 静默模式（减少输出噪音）
        cmd.append("--silent")

        return cmd

    def package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        执行 cx_Freeze 打包

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径

        Returns:
            (是否成功, 消息)
        """
        # 验证 cx_Freeze
        is_available, version_info = self.verify_cx_freeze(python_path)
        if not is_available:
            return False, f"cx_Freeze 不可用: {version_info}"

        self.log(f"✓ cx_Freeze 版本: {version_info}")

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名
        if config.get("program_name"):
            script_name = config["program_name"]
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
        else:
            script_name = Path(script_path).stem

        self.log(f"输出文件名: {script_name}")

        # 重新确认 project_dir（可能被 config 覆盖）
        project_dir = config.get("project_dir") or os.path.dirname(
            os.path.abspath(script_path)
        )

        # 构建命令
        cmd = self.build_command(
            python_path,
            config,
            output_dir,
            script_name,
            hidden_imports,
            exclude_modules,
            icon_path,
        )

        self.log(f"\n执行命令: {' '.join(cmd)}...")

        try:
            # 执行打包
            # 清除 PYTHONPATH 中的打包工具路径，避免打包工具的模块被误导入
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
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

            # 检查结果
            if process.returncode == 0:
                # 查找输出文件
                exe_path = self._find_output_exe(output_dir, script_name)

                if exe_path and os.path.exists(exe_path):
                    self._last_exe_path = exe_path
                    # 构建后再复制数据文件（避免被 cx_Freeze 清空 target-dir 时删除）
                    self._pre_copy_data_files(config, output_dir, project_dir)
                    # 清理 egg-info（项目根目录 + 输出目录均可能产生）
                    self._clean_egg_info(output_dir)
                    self._clean_egg_info(project_dir)
                    return True, f"打包成功！\n\n输出文件: {exe_path}"
                else:
                    return False, "打包完成，但未找到输出文件"
            else:
                return False, f"cx_Freeze 执行失败，返回码: {process.returncode}"

        except Exception as e:
            return False, f"执行 cx_Freeze 时出错: {str(e)}"

    def _get_local_packages(self, project_dir: str) -> List[str]:
        """
        扫描项目根目录，返回所有顶层本地包名。

        包括有 __init__.py 的常规包和包含 .py 文件的命名空间包。
        跳过虚拟环境、构建目录等无关目录。
        """
        from utils.constants import SKIP_DIRECTORIES

        skip_dirs = set(SKIP_DIRECTORIES) | {
            ".github", ".tox", ".mypy_cache", "logs", "output",
        }
        packages: List[str] = []
        try:
            for entry in os.scandir(project_dir):
                if not entry.is_dir():
                    continue
                if entry.name in skip_dirs or entry.name.startswith("."):
                    continue
                init_file = os.path.join(entry.path, "__init__.py")
                if os.path.isfile(init_file):
                    packages.append(entry.name)
                    continue
                # 无 __init__.py 但包含 .py 文件：视为命名空间包
                try:
                    has_py = any(
                        e.is_file() and e.name.endswith(".py")
                        for e in os.scandir(entry.path)
                    )
                    if has_py:
                        packages.append(entry.name)
                except Exception:
                    pass
        except Exception:
            pass
        return packages

    def _pre_copy_data_files(
        self,
        config: Dict,
        output_dir: str,
        project_dir: str,
    ) -> None:
        """预复制数据文件 + 图标到输出目录，保留子目录结构。

        cx_Freeze CLI 的 --include-files 将所有文件平铺到 build 根目录，
        导致 app 无法通过子目录路径找到文件。此方法在打包前将数据文件
        按项目内的相对路径复制到输出目录，cx_Freeze 构建时会自动包含
        这些已就位的文件。
        """
        import shutil

        # 收集所有需要复制的文件
        files_to_copy: List[str] = []

        # 1. 原始图标（运行时需要，如 _ppt_entry.py 注入代码查找 icon.ico）
        icon = config.get("icon_path") or config.get("icon")
        if icon and os.path.isfile(icon):
            files_to_copy.append(icon)

        # 2. 整个 resources/ 目录（图标、捐赠二维码等静态资源）
        resources_dir = os.path.join(project_dir, "resources")
        if os.path.isdir(resources_dir):
            for root, dirs, files in os.walk(resources_dir):
                for fname in files:
                    files_to_copy.append(os.path.join(root, fname))

        # 3. extra_data（config.env, images/*.png 等）
        extra_data: List[str] = config.get("extra_data", []) or []
        for src in extra_data:
            if os.path.exists(src):
                files_to_copy.append(src)

        if not files_to_copy:
            return

        copied = 0
        for src in files_to_copy:
            # 计算相对路径（相对于项目根目录）
            try:
                rel_path = os.path.relpath(src, project_dir)
            except ValueError:
                rel_path = os.path.basename(src)

            dst = os.path.join(output_dir, rel_path)
            dst_dir = os.path.dirname(dst)
            if dst_dir and not os.path.isdir(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
            try:
                if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                    shutil.copy2(src, dst)
                    copied += 1
            except Exception:
                pass

        if copied:
            self.log(f"  已预复制 {copied} 个数据/图标文件到输出目录（保留子目录结构）")

        # 额外在输出根目录放一份 icon.ico，覆盖 exe_dir/icon.ico 查找模式
        icon = config.get("icon_path") or config.get("icon")
        if icon and os.path.isfile(icon):
            root_icon = os.path.join(output_dir, "icon.ico")
            try:
                shutil.copy2(icon, root_icon)
            except Exception:
                pass

    @staticmethod
    def _clean_egg_info(output_dir: str) -> None:
        """清理 cx_Freeze 生成的 *.egg-info 目录。"""
        try:
            for entry in os.scandir(output_dir):
                if entry.is_dir() and entry.name.endswith(".egg-info"):
                    import shutil
                    shutil.rmtree(entry.path, ignore_errors=True)
        except Exception:
            pass

    def _find_output_exe(
        self,
        output_dir: str,
        script_name: str,
    ) -> Optional[str]:
        """
        查找输出的 exe 文件

        cx_Freeze 将输出放在 target-dir 目录下，
        exe 文件直接在该目录中（与 DLL/PYD 同级）。

        Args:
            output_dir: 输出目录
            script_name: 脚本名称

        Returns:
            exe 文件路径
        """
        # cx_Freeze 在 target-dir 下直接放 exe
        exe_path = os.path.join(output_dir, f"{script_name}.exe")
        if os.path.exists(exe_path):
            return exe_path

        # 尝试子目录
        for subdir_name in [script_name, "exe.win-amd64-3.12", "exe.win32-3.12"]:
            sub_exe = os.path.join(output_dir, subdir_name, f"{script_name}.exe")
            if os.path.exists(sub_exe):
                return sub_exe

        # 尝试查找任何 .exe 文件
        try:
            for entry in os.scandir(output_dir):
                if entry.is_file() and entry.name.endswith(".exe"):
                    return entry.path
        except Exception:
            pass

        return None

    def test_exe_for_missing_modules(
        self,
        exe_path: str,
        timeout: int = 10,
    ) -> Tuple[bool, Set[str]]:
        """
        测试 exe 运行，检测是否有缺失的模块

        Args:
            exe_path: exe 文件路径
            timeout: 超时时间

        Returns:
            (运行成功, 缺失的模块集合)
        """
        import re
        import time

        self.log("\n" + "=" * 50)
        self.log("依赖分析阶段 3/3：打包后自动测试")
        self.log("=" * 50)
        self.log(f"测试运行: {exe_path}")

        if not os.path.exists(exe_path):
            self.log("⚠️ exe 文件不存在，跳过测试")
            return True, set()

        missing_modules: Set[str] = set()
        process = None

        try:
            process = subprocess.Popen(
                [exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self.log("正在检测程序启动状态...")

            start_time = time.time()
            while time.time() - start_time < timeout:
                poll_result = process.poll()
                if poll_result is not None:
                    if poll_result != 0:
                        _, stderr = process.communicate()
                        missing = self._parse_missing_modules(stderr)
                        if missing:
                            missing_modules.update(missing)
                            self.log(f"⚠️ 检测到缺失模块: {', '.join(missing)}")
                            return False, missing_modules
                    break
                time.sleep(0.5)

            if process.poll() is None:
                self.log("✓ 程序启动成功")
                process.terminate()
                return True, set()

            return True, set()

        except Exception as e:
            self.log(f"⚠️ 测试时出错: {e}")
            return True, set()
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def _parse_missing_modules(self, error_output: str) -> Set[str]:
        """解析错误输出，提取缺失的模块"""
        import re

        missing_modules: Set[str] = set()

        patterns = [
            r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
            r"ImportError: No module named ['\"]([^'\"]+)['\"]",
            r"No module named ['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, error_output)
            for match in matches:
                root_module = match.split('.')[0]
                missing_modules.add(match)
                if root_module != match:
                    missing_modules.add(root_module)

        return missing_modules
