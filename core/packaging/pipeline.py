"""
打包流水线 — 将 Packager.package() 的 12 步流程拆分为可组合、可测试的 Step。

每个 Step 遵循相同接口，Pipeline 负责编排、取消检查、日志。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple


class PackagingStep(ABC):
    """打包流水线中的一个步骤。

    每个 Step 接收上下文 dict 并返回修改后的上下文。
    上下文在步骤间传递，累积中间结果。
    """

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行步骤，返回更新后的上下文。

        context 中始终包含的字段：
        - config: Dict — 打包配置
        - log: Callable — 日志回调
        - cancelled: Callable[[], bool] — 取消检查
        - python_path: str — 当前 Python 解释器路径
        """
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class PackagingPipeline:
    """打包流水线编排器。

    按顺序执行 Step 列表，在步骤之间检查取消标志。
    """

    def __init__(self, steps: List[PackagingStep]):
        self._steps = steps

    def add_step(self, step: PackagingStep) -> None:
        self._steps.append(step)

    def run(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """按顺序执行所有步骤。

        在 Step 之间统一检查取消标志（等价于传统 package() 每步后的取消检查）。
        不打印额外的步骤横幅，使日志输出与传统路径严格一致——
        各 Step 的日志由其委托的 Packager 方法原样产生。
        """
        context = initial_context.copy()
        log = context.get("log", print)
        cancelled = context.get("cancelled", lambda: False)

        for step in self._steps:
            if cancelled():
                log("打包已取消")
                context["success"] = False
                context["message"] = "打包已取消"
                return context

            try:
                context = step.run(context)
            except Exception as e:
                log(f"步骤 {step.name} 失败: {e}")
                context["success"] = False
                context["message"] = str(e)
                return context

            # 前置步骤硬停止（如 Python 发现失败）：设置 _halt 提前结束。
            # 注意：打包执行失败 (success=False) 不在此提前退出，
            # 以便后续的版本后处理/临时清理 Step 仍能执行（与传统 _do_package 一致）。
            if context.get("_halt"):
                return context

        return context
