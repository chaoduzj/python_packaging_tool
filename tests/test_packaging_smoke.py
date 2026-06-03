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
