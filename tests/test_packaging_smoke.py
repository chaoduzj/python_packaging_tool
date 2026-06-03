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

import os
import shutil

import pytest

from core.packager import Packager


def _pyinstaller_available() -> bool:
    """检测当前环境是否可执行 PyInstaller 打包。"""
    return shutil.which("pyinstaller") is not None or _module_available("PyInstaller")


def _module_available(module_name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module_name) is not None


@pytest.mark.slow
class TestPackagingSmoke:
    """端到端打包冒烟测试（安全网占位，逐步充实）。"""

    def test_smoke_placeholder(self, minimal_packable_project):
        """占位用例：确认夹具可用、Packager 可实例化。

        A1 阶段仅验证测试骨架能被 pytest 正确收集与运行。
        真实打包断言在 A2 补充。
        """
        project_dir, main_script, output_dir = minimal_packable_project
        assert os.path.isfile(main_script)
        packager = Packager()
        assert packager is not None
