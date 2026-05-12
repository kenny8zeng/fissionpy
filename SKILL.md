# Python Code Fission Skill

**Description**: 使用 fissionpy 工具将大型 Python 文件无损拆分为多个小模块，自动更新全项目 import 引用。

**When to use**: 当需要拆分超过 500 行的 Python 文件，或重构大型模块为多个职责单一的小文件时。

## Triggers

- "拆分这个 Python 文件"
- "将 [file.py] 拆分成多个模块"
- "重构大型文件"
- "split this Python file"
- "refactor large module"
- "导出符号索引"
- "export symbol index"
- 发现文件超过 1000 行需要拆分时主动建议

## Workflow

### ⚠️ 重要：路径一致性规则

**所有命令必须使用工程根目录为基准的相对路径，否则会导致找不到文件或提取失败。**

**原因**：支持工程目录移动和版本控制。

**正确**（使用 `./` 前缀）：
```bash
cd /path/to/project/
fission analyze ./backend/
fission plan --target ./backend/models.py
```

**错误**（使用绝对路径）：
```bash
fission analyze /home/user/project/backend/
fission plan --target /home/user/project/backend/models.py
```

### Phase 1: 分析项目

```bash
# 在工程根目录执行
cd /path/to/project/
fission analyze ./backend/ --verbose
```

这会：
- 递归扫描所有 `.py` 文件
- 使用 LibCST 解析顶层符号（函数、类、变量）
- 分析符号间依赖关系
- 建立跨文件 import 映射
- 索引到 SQLite 数据库（`.fission/fission.db`）

### Phase 2: 浏览符号与导出索引

```bash
# 查看目标文件的所有符号
fission show --file ./backend/models.py

# 查看符号详情和依赖关系
fission show --symbol User

# 查看依赖树
fission tree --file ./backend/models.py

# 反向依赖（谁依赖了这个符号）
fission tree --file ./backend/models.py --reverse

# 导出符号索引为 JSON（供 AI Agent 分析使用）
fission export --output ./fission-index.json
```

### Phase 3: 生成迁移计划

```bash
# 生成 YAML 迁移计划
fission plan --target ./backend/models.py --output ./fission-plan.yaml --verbose
```

生成的 YAML 包含：
- `modules`: 自动分组的符号列表（基于依赖连通分量）
- `retain`: 保留在原文件的符号
- `import_impact`: 受影响的文件和 import 变更

### Phase 4: 编辑计划

**⚠️ 重要提示**：编辑 YAML 计划时必须严格遵守以下规则，否则会导致提取失败。

#### 编辑步骤

1. **读取生成的计划文件**：
   ```bash
   cat fission-plan.yaml
   ```

2. **理解计划结构**：
   - `modules`: 要提取到新模块的符号列表
   - `retain`: 保留在原文件的符号
   - `import_impact`: 自动计算的 import 影响范围（只读，不要修改）

3. **编辑模块分配**：
   - 将需要提取的符号从 `retain` 移到 `modules` 中的目标模块
   - 可以创建新的模块或调整现有模块的符号分配
   - **每个符号只能出现在一个地方**（要么在 `modules`，要么在 `retain`）

4. **验证编辑结果**：
   ```bash
   # 检查 YAML 语法
   python -c "import yaml; yaml.safe_load(open('fission-plan.yaml'))"
   ```

#### 编辑示例

**初始生成的计划**（所有符号默认在 `retain`）：
```yaml
project_root: .
target_file: backend/models.py
modules: []
retain:
- User
- Product
- Order
- UserService
- ProductService
- format_name
- calculate_total
- router
- app_config
import_impact: []
```

**编辑后的计划**（将符号分配到不同模块）：
```yaml
project_root: .
target_file: backend/models.py
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
- file: ./backend/views.py
  old_import: from backend.models import User
  new_import: from _internal.models import User
```

#### ⚠️ 常见错误和注意事项

**错误 1：符号重复**
```yaml
# ❌ 错误：符号 User 同时出现在两个模块中
modules:
- name: models
  symbols:
  - User
- name: entities
  symbols:
  - User  # 重复！
retain: []
```

**错误 2：符号不存在**
```yaml
# ❌ 错误：NonExistent 符号不在目标文件中
modules:
- name: models
  symbols:
  - User
  - NonExistent  # 不存在！
retain: []
```

**错误 3：模块名不合法**
```yaml
# ❌ 错误：模块名包含非法字符
modules:
- name: 123-bad-name  # 不能以数字开头
  symbols:
  - User
- name: class         # 不能是 Python 关键字
  symbols:
  - Product
retain: []
```

**错误 4：修改 import_impact**
```yaml
# ❌ 错误：不要手动修改 import_impact
import_impact:
- file: /path/to/views.py
  old_import: from large_module import User
  new_import: from wrong.path import User  # 不要修改！
```

#### ✅ 正确的编辑方式

1. **使用 `fission show` 验证符号名**：
   ```bash
   # 查看目标文件的所有符号
   fission show --file large_module.py
   ```

2. **使用 `fission tree` 了解依赖关系**：
   ```bash
   # 查看符号依赖树，帮助合理分组
   fission tree --file large_module.py
   ```

3. **逐步验证**：
   - 每次编辑后检查 YAML 语法
   - 确保所有符号名与 `fission show` 输出完全一致
   - 确保没有重复符号

#### 模块命名建议

- **使用 `/` 创建子目录**：`_internal/models` → `_internal/models.py`
- **使用 `_` 前缀**：表示内部模块（如 `_models`、`_services`）
- **避免冲突**：不要与现有模块名冲突
- **保持简洁**：模块名应该清晰表达其职责

**多层目录示例**：
```yaml
modules:
- name: _migrated/models/user
  symbols:
  - User
  - UserProfile
- name: _migrated/models/order
  symbols:
  - Order
  - OrderItem
- name: _migrated/services
  symbols:
  - UserService
  - OrderService
retain:
- router
```

### Phase 5: 提取符号

```bash
# 执行提取
fission extract ./fission-plan.yaml --verbose
```

这会：
- 使用 LibCST 无损提取每个符号
- 保留原始格式、注释、空白字符
- 创建新模块文件
- 验证提取的文本与原始一致

### Phase 6: 完成迁移

```bash
# 执行全项目迁移
fission migrate ./fission-plan.yaml --verbose
```

这会：
- 更新全项目所有受影响的 import 语句
- 备份原文件（`.bak`）
- 重组原文件（移除已提取符号，添加重导出 import）
- 创建必要的 `__init__.py`
- 执行三重校验（符号完整性、格式无损、import 可达性）

### Phase 7: 导出索引（可选）

```bash
# 导出完整索引为 JSON
fission export --output ./fission-index.json

# 仅导出特定文件的符号
fission export --file ./backend/models.py --output ./models-index.json

# 导出包含源代码内容
fission export --include-source --output ./fission-index-with-source.json
```

这会：
- 将索引的符号、依赖、import 信息导出为 JSON 格式
- 供 AI Agent 或外部工具分析使用
- 支持筛选特定文件或包含源代码内容

#### 命令参考：`fission export`

导出索引数据为 JSON 格式，供 AI Agent 或外部工具分析使用。

```bash
fission export [--file PATH] [--db PATH] [--output PATH] [--include-source] [--verbose]
```

| 选项 | 描述 |
|------|------|
| `--file` | 筛选特定文件的符号（可选，支持多次使用） |
| `--db` | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--output` | JSON 输出路径，默认 `./fission-index.json` |
| `--include-source` | 在导出中包含源代码内容 |
| `--verbose` | 详细输出 |

#### 使用示例

**完整导出**：
```bash
fission export --output ./fission-index.json
```

**筛选特定文件**：
```bash
fission export --file ./backend/models.py --file ./backend/views.py \
  --output ./filtered-index.json
```

**包含源代码**：
```bash
fission export --include-source --output ./fission-index-with-source.json
```

#### JSON 输出结构

导出的 JSON 包含以下结构：

```json
{
  "files": [
    {
      "path": "backend/models.py",
      "hash": "abc123...",
      "indexed_at": "2026-01-15T10:30:00"
    }
  ],
  "symbols": [
    {
      "name": "User",
      "type": "class",
      "file": "backend/models.py",
      "line": 15,
      "column": 0,
      "source": "class User(BaseModel):..."  // 仅当 --include-source
    }
  ],
  "dependencies": [
    {
      "symbol": "User",
      "depends_on": ["BaseModel", "datetime"]
    }
  ],
  "imports": [
    {
      "file": "backend/views.py",
      "module": "backend.models",
      "names": ["User", "Order"]
    }
  ]
}
```

#### 路径说明

与其他命令一样，`fission export` 使用相对于工程根目录的路径：

```bash
# 正确：使用相对路径
fission export --file ./backend/models.py --output ./index.json

# 错误：使用绝对路径
fission export --file /home/user/project/backend/models.py
```

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
python -m py_compile ./_internal/models.py

# 运行项目测试
pytest ./tests/

# 验证 import 可达性
python -c "from _internal.models import User"
```

### AI Agent 执行最佳实践

**1. 始终先验证符号名**
```bash
# ✅ 正确流程
fission show --file ./backend/models.py
# 记录所有符号名
# 编辑 ./fission-plan.yaml
# 确保符号名完全匹配
```

**2. 使用依赖树指导分组**
```bash
# ✅ 正确流程
fission tree --file ./backend/models.py
# 分析依赖关系
# 将强依赖的符号放在一起
```

**3. 逐步验证**
```bash
# ✅ 正确流程
# 1. 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('./fission-plan.yaml'))"

# 2. 运行提取
fission extract ./fission-plan.yaml --verbose

# 3. 检查提取结果
ls -la ./_internal/

# 4. 运行迁移
fission migrate ./fission-plan.yaml --verbose

# 5. 验证结果
python -c "from _internal.models import User"
```

**4. 处理大型文件**
```bash
# 对于超过 1000 行的文件，建议分批提取
# 第一批：提取核心模型
modules:
- name: _migrated/models/core
  symbols:
  - User
  - Product

# 第二批：提取服务层
modules:
- name: _migrated/services
  symbols:
  - UserService
  - ProductService
```

**5. 处理循环依赖**
```bash
# 如果检测到循环依赖，需要手动调整
# 使用 fission tree 查看依赖关系
fission tree --file ./backend/models.py

# 将循环依赖的符号放在同一模块中
modules:
- name: _migrated/models
  symbols:
  - User
  - Order  # User 和 Order 互相依赖
```

**6. 处理装饰器和元类**
```bash
# 装饰器和元类引用的符号会被正确保留
# 但需要确保依赖顺序正确
# 建议将装饰器和被装饰的类放在同一模块
modules:
- name: _migrated/models
  symbols:
  - User
  - user_decorator  # 装饰器
```

**7. 使用导出索引辅助 AI Agent 决策**
```bash
# 正确流程：导出索引辅助决策
fission export --output ./fission-index.json
# AI Agent 读取 JSON 获取符号和依赖数据
```

## Edge Cases

### `from X import *` 处理

工具会尽力解析 star import，但可能无法确定所有符号。迁移后需手动验证。

### 循环依赖

如果符号间存在循环依赖，自动分组可能不准确。需手动调整计划。

### 装饰器和元类

装饰器和元类引用的符号会被正确保留，但需确保依赖顺序正确。

### 导出索引的边界情况

**数据库不存在**：
```bash
# 错误：未找到数据库
Error: Database not found at ./.fission/fission.db

# 解决：先运行分析命令
fission analyze ./backend/
```

**空数据库**：
```bash
# 错误：数据库为空，没有任何符号
Warning: No symbols found in database

# 解决：确认分析命令正确执行且文件被索引
fission analyze ./backend/ --verbose
```

**文件未被索引**：
```bash
# 错误：指定的文件未被索引
fission export --file ./backend/models.py --output ./index.json
# Error: File ./backend/models.py not found in index

# 解决：确认文件路径正确且已被分析
fission show --file ./backend/models.py
```

## Troubleshooting

### 分析失败

```bash
# 强制重新分析
fission analyze ./backend/ --force

# 排除特定目录
fission analyze ./backend/ --exclude .venv --exclude node_modules
```

### 提取失败

**检查 YAML 计划中的符号名是否与目标文件中的实际符号名一致**：

```bash
fission show --file ./backend/models.py
```

**常见提取失败原因**：

1. **符号名拼写错误**：
   ```bash
   # 检查实际符号名
   fission show --file ./backend/models.py
   # 确保计划中的符号名与输出完全一致
   ```

2. **符号重复**：
   ```yaml
   # ❌ 错误
   modules:
   - name: models
     symbols:
     - User
   - name: entities
     symbols:
     - User  # 重复！
   ```

3. **符号不存在**：
   ```yaml
   # ❌ 错误
   modules:
   - name: models
     symbols:
     - NonExistent  # 不存在！
   ```

4. **模块名不合法**：
   ```yaml
   # ❌ 错误
   modules:
   - name: 123-bad-name  # 不能以数字开头
   - name: class         # 不能是关键字
   ```

### 迁移后 import 错误

检查 `import_impact` 是否正确，手动编辑 YAML 后重新运行 migrate。

**验证 import 更新**：
```bash
# 检查受影响的文件
grep -r "from old_module import" ./backend/

# 验证新的 import 路径
python -c "from _internal.models import User"
```

### AI Agent 编辑计划时的常见错误

**错误 1：没有验证符号名就编辑计划**
```bash
# ❌ 错误做法：直接编辑计划
vim ./fission-plan.yaml

# ✅ 正确做法：先验证符号名
fission show --file ./backend/models.py
vim ./fission-plan.yaml
```

**错误 2：修改了 import_impact**
```yaml
# ❌ 错误：手动修改 import_impact
import_impact:
- file: ./backend/views.py
  old_import: from backend.models import User
  new_import: from wrong.path import User  # 不要修改！

# ✅ 正确：保持 import_impact 不变
import_impact:
- file: ./backend/views.py
  old_import: from backend.models import User
  new_import: from _internal.models import User  # 自动生成
```

**错误 3：符号分配不合理**
```yaml
# ❌ 错误：将强依赖的符号分散到不同模块
modules:
- name: models
  symbols:
  - User
- name: services
  symbols:
  - UserService  # UserService 依赖 User，应该放在一起

# ✅ 正确：将强依赖的符号放在一起
modules:
- name: models
  symbols:
  - User
  - UserService
```

**错误 4：没有检查 YAML 语法**
```bash
# ❌ 错误：直接运行提取
fission extract ./fission-plan.yaml

# ✅ 正确：先验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('./fission-plan.yaml'))"
fission extract ./fission-plan.yaml
```

### 调试技巧

**1. 查看详细输出**：
```bash
fission plan --target ./backend/models.py --output ./fission-plan.yaml --verbose
fission extract ./fission-plan.yaml --verbose
fission migrate ./fission-plan.yaml --verbose
```

**2. 检查数据库**：
```bash
# 查看数据库中的符号
sqlite3 ./.fission/fission.db "SELECT name, type FROM symbols WHERE file_id = (SELECT id FROM files WHERE path = 'backend/models.py');"
```

**3. 验证提取结果**：
```bash
# 检查提取的文件
cat ./_internal/models.py

# 验证 Python 语法
python -m py_compile ./_internal/models.py
```

**4. 回滚迁移**：
```bash
# 恢复原文件
mv ./backend/models.py.bak ./backend/models.py

# 删除提取的模块
rm -rf ./_internal/
```

## Installation

```bash
# 克隆项目
git clone https://github.com/kenny8zeng/fissionpy.git
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
