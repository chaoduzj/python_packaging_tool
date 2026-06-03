"""
端到端打包冒烟测试 — Pipeline 迁移的安全网。

这些测试运行真实的 nuitka/pyinstaller 子进程，耗时较长，统一标记为 slow。
运行方式:
    pytest -m slow tests/test_packaging_smoke.py        # 只跑冒烟测试
    pytest -m "not slow"                                # 跳过冒烟测试

作用:
    锁定 Packager.package() 的当前外部可观测行为，作为 Pipeline 迁移的回归基准。
    迁移完成后，同一组断言用于验证 package_via_pipeline() 与 package() 严格等价。
"""

import importlib.util
import os

import pytest

from core.packager import Packager


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _make_config(main_script: str, output_dir: str, tool: str) -> dict:
    """构造最小打包配置：单文件、无控制台关闭、不建 venv（用当前解释器）。"""
    return {
        "script_path": main_script,
        "project_dir": os.path.dirname(main_script),
        "output_dir": output_dir,
        "tool": tool,
        "onefile": True,
        "console": True,
        "use_venv": False,
        "upx": False,
        "clean": True,
    }


def _run_package(packager: Packager, config: dict):
    """调用 package() 并收集日志。返回 (success, message, exe_path, logs)。"""
    logs: list[str] = []
    success, message, exe_path = packager.package(
        config,
        log_callback=logs.append,
    )
    return success, message, exe_path, logs


@pytest.mark.slow
@pytest.mark.skipif(
    not _module_available("PyInstaller"),
    reason="PyInstaller 未安装，跳过 PyInstaller 冒烟测试",
)
class TestPackageSmokePyInstaller:
    """用 PyInstaller 端到端打包最小项目（安全网基准）。"""

    def test_package_produces_exe(self, minimal_packable_project):
        """package() 应成功打包并产出真实存在的 exe 文件。"""
        project_dir, main_script, output_dir = minimal_packable_project
        packager = Packager()
        success, message, exe_path, logs = _run_package(
            packager, _make_config(main_script, output_dir, "pyinstaller")
        )

        assert success is True, f"打包失败: {message}\n日志:\n" + "\n".join(logs[-30:])
        assert exe_path is not None, "未返回 exe 路径"
        assert os.path.isfile(exe_path), f"exe 文件不存在: {exe_path}"
        assert exe_path.lower().endswith(".exe")

    def test_package_side_effects(self, minimal_packable_project):
        """快照 package() 的可观测副作用：阶段日志 + 输出目录 + 临时文件清理。

        这些断言定义了 Pipeline 迁移后必须保持一致的"严格等价"边界。
        """
        project_dir, main_script, output_dir = minimal_packable_project
        packager = Packager()
        success, message, exe_path, logs = _run_package(
            packager, _make_config(main_script, output_dir, "pyinstaller")
        )

        assert success is True, f"打包失败: {message}"
        joined = "\n".join(logs)

        # 1. 三个核心阶段日志标志均出现
        assert "第一阶段：依赖分析" in joined
        assert "第二阶段：依赖安装" in joined
        assert "第三阶段：打包" in joined

        # 2. 输出目录被创建
        assert os.path.isdir(output_dir)

        # 3. 临时文件在打包结束后已清理（不残留）
        assert not os.path.exists(os.path.join(output_dir, "version_info.txt"))
        assert not os.path.exists(os.path.join(output_dir, "icon_converted.ico"))
        assert not os.path.exists(os.path.join(project_dir, "_ppt_entry.py"))
