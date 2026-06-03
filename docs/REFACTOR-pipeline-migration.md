# Refactor Plan — 完成 Pipeline 框架并迁移为主打包路径

> 状态: 待执行
> 类型: 架构迁移 (严格等价)
> 创建: 2026-06
> 前置技能: request-refactor-plan

---

## Problem Statement

当前项目存在两条打包路径:

1. **传统路径** `Packager.package()` — 一个 350+ 行的方法,内联 12 个步骤,
   GUI 的全部 3 个调用方 (`workers.py`、`packaging_handler.py`、`main_window.py`)
   都走这条路。这是**唯一真正工作的路径**。
2. **Pipeline 路径** `Packager.package_via_pipeline()` + `core/packaging/pipeline.py`
   + `core/packaging/pipeline_steps.py` — 之前重构引入的"渐进迁移骨架",
   但**从未被任何调用方使用**,且实现严重不完整 (是草稿,不是等价实现)。

开发者希望: **完成 Pipeline 框架,把业务逻辑补全到与 `package()` 严格等价,
并将其确立为项目的主打包路径**,从而获得:
- 每个打包步骤独立可测试 (当前 `package()` 是巨型方法,无法单步测试)
- `_do_package` 中纠缠的后处理逻辑 (rcedit / UPX / 清理) 解耦,便于扩展维护

## Solution

分三大阶段,严格遵循"每次提交都让代码处于可工作状态":

- **阶段 A — 建立安全网**: 先补端到端打包冒烟测试,锁定 `package()` 当前行为。
- **阶段 B — 补全 Pipeline 至严格等价**: 逐步把 `package()` 的 12 步 + `_do_package`
  的 5 个关注点搬进 Step,每搬一步用安全网验证行为不变。最终 `package_via_pipeline`
  与 `package` 产出一致。
- **阶段 C — 切换主路径 (并存)**: GUI 调用点切到 Pipeline,旧 `package()` 标记
  deprecated 但保留。旧路径的删除留到后续"删死代码"阶段。

迁移策略为**严格等价**: Pipeline 必须产出与 `package()` 相同的命令、顺序、副作用。
不借机改进任何业务逻辑。

---

## Commits

### 阶段 A — 安全网 (3 commits)

**A1. 添加打包冒烟测试的骨架与夹具**
新增一个集成测试文件,提供"用真实脚本走完整 `package()`"的测试夹具:
一个最小可打包的 Python 脚本 (仅 import 标准库,避免网络依赖) + 临时输出目录。
此 commit 仅建立夹具和一个 `@pytest.mark.slow` 标记的占位用例,确认能跑通 pytest 收集。

**A2. 编写 `package()` 端到端冒烟测试**
用 A1 的夹具调用 `Packager().package(config)`,断言:
返回三元组 `(success, message, exe_path)` 的 `success is True`、
`exe_path` 指向真实存在的文件、退出码正常。
这是后续所有迁移 commit 的回归基准。标记为 slow,默认可跳过,CI/手动触发时运行。

**A3. 记录 `package()` 的步骤副作用快照**
在测试中追加断言,捕获 `package()` 执行过程中的关键中间副作用:
输出目录被创建、临时文件 (`version_info.txt`/`icon_converted.ico`/`_ppt_entry.py`)
在结束时已被清理、日志中出现 12 个步骤的标志性输出。
这些断言定义了"严格等价"的可观测边界。

### 阶段 B — 补全 Pipeline 至严格等价 (12 commits)

> 每个 commit 只搬一个步骤进 Step,搬完立即让 `package_via_pipeline` 多覆盖一步,
> 并用阶段 A 的冒烟测试验证 `package_via_pipeline` 与 `package` 产出一致。

**B1. 修正 `PythonDiscoveryStep` 至与 `_get_python_path` 等价**
现有 Step 简化了逻辑 (缺少 `is_valid_python_interpreter` 校验、缺少错误信息文案)。
改为内部直接委托 `Packager._get_python_path`,保证行为逐字一致。

**B2. 确认 `VenvSetupStep` 已等价 (可能仅加注释)**
现有 Step 已委托 `_setup_venv_if_needed`,核对其与 `package()` 第 2 步调用方式一致。
若一致则仅补充文档说明,不改逻辑。

**B3. 新增 `ChinesePathCheckStep` (补全缺失的第 3 步)**
`package()` 第 3 步 `_check_chinese_paths` 在 Pipeline 中完全缺失。
新增一个 Step 委托 `_check_chinese_paths`,插入到 venv 与输出目录之间。

**B4. 修正 `OutputDirStep` 至与 `_prepare_output_dir` 等价 (关键)**
现有 Step 只做 `mkdir`,**丢失了安全检查 (`_is_safe_output_dir`,防止误删 C:\)
和清理逻辑 (`_prepare_output_dir`)**。改为内部委托 `_prepare_output_dir`,
恢复全部安全与清理行为。这是迁移中最高风险的一步,单独成 commit。

**B5. 新增 `QtFrameworkDetectStep` (补全缺失的第 5 步)**
`package()` 第 5 步 `detect_primary_qt_framework` 在 Pipeline 中缺失。
新增 Step 委托该检测,把结果写入 context (供后续打包步骤使用)。

**B6. 修正 `DependencyAnalysisStep` 至与 `_analyze_dependencies` 等价 (关键)**
现有 Step 用了 `get_hidden_imports()/get_exclude_modules()` 的独立接口,
与 `package()` 第 6 步走的 `_analyze_dependencies` 接口不一致。
改为内部委托 `_analyze_dependencies`,保证依赖/隐藏导入/排除模块三者计算一致。

**B7. 拆分 `DependencyInstallStep` 为安装依赖 + 安装打包工具两步**
现有 Step 把 `package()` 的第 7、8 步合并了。为严格对齐步骤边界,
拆为 `DependencyInstallStep` (第 7 步,委托 `_install_dependencies`) 和
`PackagingToolInstallStep` (第 8 步,委托 `install_packaging_tool`)。

**B8. 修正 `IconProcessingStep` 至与 `_process_icon` 等价**
现有 Step 是简化版,与 `package()` 第 9 步 `_process_icon` 的警告处理/路径返回不一致。
改为内部委托 `_process_icon`。

**B9. 新增 `VersionInfoStep` (补全缺失的第 10 步)**
`package()` 第 10 步 `_prepare_version_info` 在 Pipeline 中缺失。
新增 Step 委托该方法,把 `version_file` 写入 context。

**B10. 新增 `DataFileDetectStep` (补全缺失的第 11 步)**
`package()` 第 11 步 `_auto_detect_data_files` 在 Pipeline 中缺失。
新增 Step 委托该方法。

**B11. 拆解 `_do_package` 为多个后处理 Step (核心,Q3)**
把 `_do_package` 的 5 个关注点拆为独立 Step,串入 Pipeline 末尾:
- `ConfigEnhanceStep` — 填充 qt_framework / GUI 框架标志 / 版本文件到 config
- `IconInjectStep` — Nuitka 图标入口注入 (`_create_icon_entry_wrapper`)
- `BuildExecuteStep` — 调用 nuitka/pyinstaller packager,记录 `_last_exe_path`
- `VersionPostProcessStep` — rcedit 后处理 (含 UPX/PyInstaller-onefile 的跳过判定)
- `TempCleanupStep` — 清理 version_info.txt / icon_converted.ico / _ppt_entry.py
每个 Step 拆完立即用冒烟测试验证整链产出不变。

**B12. 让 `package_via_pipeline` 走完整 Pipeline,移除对 `_do_package` 的直接调用**
此时 `build_pipeline` 已包含全部步骤。`package_via_pipeline` 改为纯粹运行 Pipeline,
不再回落到 `_do_package`。冒烟测试断言 `package_via_pipeline` 与 `package` 结果一致。

### 阶段 C — 切换主路径 (并存) (4 commits)

**C1. 为每个 Step 补单元测试**
利用 Step 的独立接口 (这正是 Pipeline 化的收益),为关键 Step 注入 mock 依赖
编写单元测试: Python 发现、输出目录安全检查、依赖分析、后处理跳过判定。

**C2. GUI 调用点 #1 切换到 `package_via_pipeline`**
把 `gui/controllers/workers.py` 的 `package()` 调用改为 `package_via_pipeline`。
手动 + 冒烟测试验证。

**C3. GUI 调用点 #2、#3 切换**
把 `gui/handlers/packaging_handler.py`、`gui/main_window.py` 的调用切换。

**C4. 旧 `package()` 标记 deprecated (保留,不删)**
在 `package()` 添加 deprecation 文档/注释,说明已被 `package_via_pipeline` 取代,
保留以备回退。实际删除留到后续"删死代码"阶段。

---

## Decision Document

- **迁移策略**: 严格等价。Pipeline 不改变任何业务行为,逐字搬运 `package()` 逻辑。
- **Step 委托而非重写**: 每个 Step 内部委托现有 `Packager` 的私有方法
  (`_get_python_path`、`_prepare_output_dir`、`_analyze_dependencies` 等),
  而非重新实现。这把"等价性"风险降到最低。
- **`_do_package` 拆解 (Q3)**: 拆为 5 个独立后处理 Step
  (配置增强 / 图标注入 / 打包执行 / 版本后处理 / 临时清理),
  解耦 rcedit / UPX / 清理的纠缠逻辑,提升扩展维护性。
- **步骤边界对齐**: Pipeline 的 Step 数量与 `package()` 的 12 步严格对应,
  之前被合并的步骤 (依赖安装+工具安装) 拆开,以便逐步验证。
- **退役策略 (Q4)**: 新旧路径并存一段。GUI 先切到 Pipeline,
  旧 `package()` 标记 deprecated 保留,确认稳定后在第二阶段删除。
- **context 契约**: Pipeline 各 Step 通过 context dict 传递中间产物
  (python_path / output_dir / dependencies / hidden_imports / exclude_modules /
  icon_path / version_file / qt_framework / _last_exe_path)。
  这是 Step 之间的接口,新增 Step 时遵循同一契约。
- **取消检查**: `package()` 在每步后检查 `_is_cancelled()`。
  PackagingPipeline.run 已在 Step 之间统一做取消检查,行为等价。

## Testing Decisions

- **好测试的标准**: 只测外部可观测行为 (返回值、生成的 exe、临时文件清理、
  关键日志标志),不测实现细节 (不断言内部调用了哪个私有方法)。
- **集成测试 (安全网)**: 端到端调用 `package()` / `package_via_pipeline`,
  断言打包成功 + exe 存在 + 临时文件已清理。两条路径用**同一组断言**,
  这就是"严格等价"的验证方式。标记为 slow,避免拖慢常规测试。
- **Step 单元测试**: 利用 Step 的独立接口,注入 mock `Packager` 依赖,
  测每个 Step 的 context 输入/输出契约。重点测: 输出目录安全检查
  (拒绝 C:\ 等受保护目录)、后处理的跳过判定 (UPX 时跳过 rcedit)。
- **Prior art**: 现有 `tests/test_packager.py` 已有针对私有方法的单元测试
  (`_check_chinese_paths`、`_prepare_output_dir`、`_has_chinese`),
  新测试沿用其 fixture 风格 (`temp_dir`、`log_messages`、`sample_project`)。

## Out of Scope

- **删除死代码 / 大文件内部简化**: 本次只做 Pipeline 迁移。
  `main_window.py` (2824行)、`hidden_imports.py` (2144行) 的内部简化,
  以及 `tests/qq.py`、`tests/update_brave.py`、`test_subprocess_args.py` 等
  无关文件的删除,全部留到迁移完成且测试通过后的**第二阶段**。
- **删除旧 `package()`**: 本次仅标记 deprecated 并保留,不删除。
- **改变打包业务逻辑**: 不优化任何打包行为,不改 rcedit/UPX 判定规则,
  不改依赖分析算法。严格等价。
- **`pyproject.toml` 的 setuptools packages 配置缺失**: 已知问题,非本次范围。

## Further Notes

- 当前**零端到端打包测试**是最大风险点,故阶段 A 必须先行。
- 阶段 B 的 B4 (输出目录安全检查) 和 B6 (依赖分析接口对齐) 是两个最高风险 commit,
  各自独立成 commit 并立即用冒烟测试验证。
- 由于打包涉及真实 subprocess (nuitka/pyinstaller) 且耗时较长,
  冒烟测试默认标记 slow;开发者也可继续用 GUI 手动验证作为补充。
