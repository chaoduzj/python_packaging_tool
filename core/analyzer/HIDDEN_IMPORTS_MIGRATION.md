# hidden_imports.py 配置表驱动迁移指南

## 背景

`core/analyzer/hidden_imports.py`（2432 行）包含 23 个简单模板方法，每个都是
相同模式的复制粘贴：

```python
def _get_xxx_hidden_imports(self, dependencies):
    hidden = []
    if "xxx" in dependencies:
        hidden.extend([...])
    return hidden
```

合计约 140 条 `dependency → hidden_imports` 规则，是配置表驱动的理想候选。
预计迁移后可减少 1200+ 行代码。

## 当前进度

- ✅ **已完成**：38 个基线测试（`tests/test_hidden_imports.py`）
  覆盖 Qt 框架推导、典型 GUI 框架、common_libs 抽样、主入口编排、过滤逻辑。
  这些测试在迁移前后必须全部通过。
- ⏸️ **未执行**：实际配置表抽取（见下方"风险说明"）。

## 风险说明

未立即执行完整迁移的原因：

1. **覆盖度不足**：现有 38 个测试是**抽样**测试。`_get_common_libs_hidden_imports`
   有约 40 条规则，目前只测了 requests/dns/empty 3 条；其他分类方法也只抽样
   1-2 条。手工翻译 140 条规则时，遗漏任何一条都不会被测试发现。

2. **影响面大**：hidden_imports 缺漏会直接导致**用户打包的 exe 运行时崩溃**
   （如 `ModuleNotFoundError`）。这是核心功能的正确性问题。

3. **代码搬家收益有限**：配置表迁移本质上是把代码改为数据，**不修复任何 bug**，
   也不改变运行时行为。减少的 1200 行是重复模板，维护负担转为"数据校验"。

## 推荐迁移方案

若后续仍要执行，推荐以下渐进步骤：

### 步骤 1：扩充基线测试到全规则覆盖

为每个简单方法添加"全依赖场景"测试，遍历所有 trigger：

```python
@pytest.mark.parametrize("trigger", ["dns", "dnspython"])
def test_dns_triggers(manager, trigger):
    result = manager._get_common_libs_hidden_imports({trigger})
    expected = {"dns", "dns.resolver", "dns.rdatatype", ...}  # 完整列表
    assert set(result) == expected
```

只有当每个 trigger 都有精确集合断言后，才能安全迁移。

### 步骤 2：创建配置表文件

新建 `core/analyzer/hidden_imports_table.py`，schema 设计：

```python
from dataclasses import dataclass, field
from typing import Set, List

@dataclass(frozen=True)
class HiddenImportRule:
    """单条隐藏导入规则。"""
    triggers: Set[str]              # 命中条件（任一即可）
    imports: List[str]              # 命中后追加的模块列表
    match: str = "any"              # "any"（默认）或 "all"

# 示例：dns/dnspython 别名场景
Rule(triggers={"dns", "dnspython"},
     imports=["dns", "dns.resolver", "dns.rdatatype", ...]),

# 示例：pywin32 any-match 场景
Rule(triggers={"win32api", "win32com", "win32gui", "pywin32"},
     imports=["win32com", "win32com.client", "pythoncom", "pywintypes", ...]),
```

### 步骤 3：用脚本辅助翻译（避免手工出错）

编写一次性脚本 `tools/generate_hidden_imports_table.py`，用 AST 解析
现有方法自动生成配置表：

```python
import ast
# 解析 hidden_imports.py，抽取所有 `if X in dependencies: hidden.extend([...])` 模式
# 自动生成 Rule 列表
```

这样能保证 140 条规则被 100% 忠实翻译，避免人工遗漏。

### 步骤 4：让原方法委托到配置表（保留方法签名）

```python
def _get_dns_hidden_imports(self, dependencies):
    """[已迁移到配置表] 保留方法以维持 API 兼容。"""
    return _table_lookup(TRIGGERS_DNS, dependencies)
```

迁移期间两套实现并存，由 feature flag 切换，便于 A/B 对比和回滚。

### 步骤 5：全量回归后删除原方法

当所有测试通过、且生产环境观察一段时间无异常后，再删除原方法体。

## 替代方案：保持现状

如果维护负担可接受，**保持现状也是合理选择**：
- 当前方法虽重复但**工作正常**
- 23 个方法各自独立，新增库只需复制模板
- 静态代码比动态配置表更易调试

迁移的真正价值在于"新增库的门槛降低"，但当前模板已足够简单。
