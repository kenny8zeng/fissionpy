# Python Code Fission Skill

**Description**: 使用 fissionpy 工具将大型 Python 文件无损拆分为多个小模块，自动更新全项目 import 引用。

**When to use**: 当需要拆分超过 500 行的 Python 文件，或重构大型模块为多个职责单一的小文件时。

## Triggers

- "拆分这个 Python 文件"
- "将 [file.py] 拆分成多个模块"
- "重构大型文件"
- "split this Python file"
- "refactor large module"
- 发现文件超过 1000 行需要拆分时主动建议

## Workflow

### Phase 1: 分析项目

```bash
# 在项目根目录执行
fission analyze <project_dir> --verbose
```

这会：
- 递归扫描所有 `.py` 文件
- 使用 LibCST 解析顶层符号（函数、类、变量）
- 分析符号间依赖关系
- 建立跨文件 import 映射
- 索引到 SQLite 数据库（`.fission/fission.db`）

### Phase 2: 浏览符号

```bash
# 查看目标文件的所有符号
fission show --file <target_file.py>

# 查看符号详情和依赖关系
fission show --symbol <SymbolName>

# 查看依赖树
fission tree --file <target_file.py>

# 反向依赖（谁依赖了这个符号）
fission tree --file <target_file.py> --reverse
```

### Phase 3: 生成迁移计划

```bash
# 生成 YAML 迁移计划
fission plan --target <target_file.py> --output fission-plan.yaml --verbose
```

生成的 YAML 包含：
- `modules`: 自动分组的符号列表（基于依赖连通分量）
- `retain`: 保留在原文件的符号
- `import_impact`: 受影响的文件和 import 变更

### Phase 4: 编辑计划

编辑 `fission-plan.yaml`，将符号分配到合理的模块：

```yaml
project_root: /path/to/project
target_file: large_module.py
modules:
- name: _internal/models
  symbols:
  - User
  - Product
  - Order
- name: _internal/services
  symbols:
  - UserService
  - ProductService
- name: _internal/utils
  symbols:
  - format_name
  - calculate_total
retain:
- router
- app_config
import_impact:
- file: /path/to/views.py
  old_import: from large_module import User
  new_import: from _internal.models import User
```

**模块命名建议**：
- 使用 `_internal/` 或 `_migrated/` 前缀表示自动生成的模块
- 使用 `/` 创建子目录（如 `_internal/models` → `_internal/models.py`）
- 每个模块名必须是合法 Python 标识符

### Phase 5: 提取符号

```bash
# 执行提取
fission extract fission-plan.yaml --verbose
```

这会：
- 使用 LibCST 无损提取每个符号
- 保留原始格式、注释、空白字符
- 创建新模块文件
- 验证提取的文本与原始一致

### Phase 6: 完成迁移

```bash
# 执行全项目迁移
fission migrate fission-plan.yaml --verbose
```

这会：
- 更新全项目所有受影响的 import 语句
- 备份原文件（`.bak`）
- 重组原文件（移除已提取符号，添加重导出 import）
- 创建必要的 `__init__.py`
- 执行三重校验（符号完整性、格式无损、import 可达性）

## Best Practices

### 模块拆分策略

1. **按职责拆分**：将相关功能的符号放在同一模块
2. **按依赖关系分组**：使用 `fission tree` 查看依赖，将强依赖的符号放在一起
3. **保持模块大小**：每个拆分后的文件建议 < 500 行
4. **保留公共接口**：将 `router`、`app` 等入口点保留在原文件，使用重导出

### 命名约定

- 内部模块使用 `_` 前缀（如 `_models`、`_services`）
- 子目录模块使用 `/` 分隔（如 `_internal/models`）
- 避免与现有模块名冲突

### 验证迁移

迁移完成后，运行以下验证：

```bash
# 检查 Python 语法
python -m py_compile <new_module.py>

# 运行项目测试
pytest tests/

# 验证 import 可达性
python -c "from new_module import SymbolName"
```

## Edge Cases

### `from X import *` 处理

工具会尽力解析 star import，但可能无法确定所有符号。迁移后需手动验证。

### 循环依赖

如果符号间存在循环依赖，自动分组可能不准确。需手动调整计划。

### 装饰器和元类

装饰器和元类引用的符号会被正确保留，但需确保依赖顺序正确。

## Troubleshooting

### 分析失败

```bash
# 强制重新分析
fission analyze <dir> --force

# 排除特定目录
fission analyze <dir> --exclude .venv --exclude node_modules
```

### 提取失败

检查 YAML 计划中的符号名是否与目标文件中的实际符号名一致：

```bash
fission show --file <target_file.py>
```

### 迁移后 import 错误

检查 `import_impact` 是否正确，手动编辑 YAML 后重新运行 migrate。

## Installation

```bash
# 克隆项目
git clone https://github.com/your-org/fissionpy.git
cd fissionpy

# 安装
uv pip install -e .

# 验证安装
fission --version
```

## Project Structure

```
src/fissionpy/
├── cli/              # CLI 命令实现
├── analysis/         # 符号分析和依赖追踪
├── extraction/       # 代码提取和计划生成
├── migration/        # 项目级迁移和校验
└── common/           # 路径工具
```

## Key Features

- **LibCST 无损操作**：完整保留注释、格式、空白字符
- **CSTTransformer import 更新**：精确修改，禁用正则替换
- **增量分析**：基于文件哈希，未修改文件自动跳过
- **跨文件依赖追踪**：自动识别符号引用链
- **三重校验**：迁移后自动验证完整性
