# fissionpy

**Python 工程目录裂变迁移工具** —— 基于 LibCST 的无损代码拆分与迁移解决方案。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**仓库地址**: https://github.com/kenny8zeng/fissionpy

**文档**:
- [English](../README.md) | [中文](README.ch.md)

fissionpy 专为大型 Python 项目重构设计，能够将超大型模块文件（数千至数万行）安全、自动化地拆分为多个小模块，同时保持代码的完整性和可维护性。通过 LibCST（Concrete Syntax Tree）技术，确保所有代码变更都是无损的——保留原始格式、注释和空白字符。

## 核心功能

### 1. 工程级符号索引
- 递归扫描整个 Python 项目，解析所有 `.py` 文件
- 使用 LibCST 提取顶层符号（函数、类、变量赋值）
- 通过 LibCST ScopeProvider 分析符号间依赖关系
- 跨文件 import 语句追踪，自动识别符号引用链
- SQLite 持久化存储，支持增量分析（基于文件哈希）

### 2. 符号浏览与依赖可视化
- `fission show`：查看项目文件列表、文件符号表、符号详情
- `fission tree`：以树形结构展示符号依赖关系
- 跨文件依赖标注：清晰标识哪些符号被其他文件引用
- 反向依赖查询：找出谁依赖了某个符号

### 3. 智能迁移计划生成
- 基于符号依赖图的连通分量自动分组
- 生成 YAML 迁移计划，支持手动编辑调整
- 自动计算 import 影响范围（哪些文件需要更新 import）
- 支持子目录模块（`module/deep/path` → `module/deep/path.py`）

### 4. 无损代码提取
- 使用 LibCST CST 节点提取，逐字符保留原始格式
- 保留 leading_lines（注释、空行）、decorator、base class
- 自动追加 `from __future__ import annotations` 等必要导入
- 提取后即时校对：对比提取文本与原始文本

### 5. 项目级 import 传播
- 使用 LibCST CSTTransformer 精确替换 import 语句
- 处理复杂场景：`from X import Y, Z` 拆分、别名导入
- 自动更新全项目所有受影响的 import 语句
- 支持相对导入和绝对导入

### 6. 重组与重导出
- 备份原文件（`.bak` 后缀）
- 移除已提取符号，保留剩余符号
- 自动添加重导出 import（`from new_module import Symbol`）
- 创建子目录 `__init__.py` 文件

### 7. 三重一致性校验
- **符号完整性**：所有原始符号在拆分后文件中可找到
- **格式无损性**：提取文本与原始文本逐字符一致
- **import 可达性**：所有 import 语句目标文件存在

## 安装

```bash
uv pip install -e .
```

要求 Python 3.11+。

## 快速开始

```bash
# Step 1: 分析项目
fission analyze ./my_project/

# Step 2: 浏览符号
fission show
fission show --file ./my_project/models.py
fission show --symbol User
fission tree --file ./my_project/views.py

# Step 3: 生成迁移计划
fission plan --target ./my_project/models.py --output plan.yaml

# Step 4: 编辑 plan.yaml（将符号从 retain 移到 modules）
# 编辑 YAML，将需要提取的符号分配到目标模块

# Step 5: 提取符号
fission extract plan.yaml

# Step 6: 迁移（更新全项目 import 引用）
fission migrate plan.yaml
```

## 命令参考

### `fission analyze`

分析工程目录，索引所有文件和符号到 SQLite 数据库。

```bash
fission analyze <directory> [--db PATH] [--exclude PATTERN] [--force] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--db` | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--exclude` | 排除目录模式，可多次使用 |
| `--force` | 强制重新解析所有文件（忽略增量缓存） |
| `--verbose` | 详细输出 |

### `fission show`

浏览符号信息——项目文件列表、文件符号列表、符号详情与依赖关系。

```bash
fission show [--file PATH] [--symbol NAME] [--db PATH] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--file` | 查看指定文件的顶层符号和导入 |
| `--symbol` | 查看指定符号的详情、依赖和被依赖关系 |
| `--db` | SQLite 数据库路径 |
| `--verbose` | 详细输出 |

不带选项时显示项目文件总览。

### `fission tree`

打印指定文件的符号依赖树。

```bash
fission tree --file PATH [--symbol NAME] [--reverse] [--db PATH] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--file` | 目标文件路径（必选） |
| `--symbol` | 仅展示指定符号的子树 |
| `--reverse` | 反向视图：显示谁依赖了该符号 |
| `--db` | SQLite 数据库路径 |
| `--verbose` | 详细输出 |

### `fission plan`

为目标文件生成 YAML 迁移计划模板。基于符号依赖关系自动分组，用户可编辑调整。

```bash
fission plan --target PATH [--db PATH] [--output PATH] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--target` | 要拆分的目标文件路径（必选） |
| `--db` | SQLite 数据库路径 |
| `--output` | YAML 输出路径，默认 `./fission-plan.yaml` |
| `--verbose` | 详细输出 |

### `fission extract`

执行代码提取——按计划将符号无损提取到新模块文件。

```bash
fission extract <plan_file> [--db PATH] [--resume] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--db` | SQLite 数据库路径 |
| `--resume` | 从上次中断处继续提取 |
| `--verbose` | 详细输出 |

### `fission migrate`

完成项目级迁移——更新全项目 import 引用、备份重组原文件、一致性校验。

```bash
fission migrate <plan_file> [--db PATH] [--no-reexport] [--resume] [--verbose]
```

| 选项 | 说明 |
|------|------|
| `--db` | SQLite 数据库路径 |
| `--no-reexport` | 不在原文件生成重导出 import |
| `--resume` | 从上次中断处继续迁移 |
| `--verbose` | 详细输出 |

全局选项：`--version` 显示版本号。

## YAML 计划格式

`fission plan` 生成的 YAML 文件结构如下：

```yaml
# fission migration plan - edit modules/symbols before running extract
project_root: /path/to/my_project
target_file: models.py
modules:
- name: _migrated/user_types
  symbols:
  - User
  - UserProfile
  - UserStatus
- name: _migrated/order_types
  symbols:
  - Order
  - OrderItem
retain:
- router
- app_config
import_impact:
- file: /path/to/my_project/views.py
  old_import: from models import User
  new_import: from _migrated.user_types import User
- file: /path/to/my_project/services.py
  old_import: from models import Order
  new_import: from _migrated.order_types import Order
```

| 字段 | 说明 |
|------|------|
| `project_root` | 项目根目录绝对路径 |
| `target_file` | 目标文件相对路径 |
| `modules` | 要提取的模块列表，每个模块包含 `name` 和 `symbols` |
| `retain` | 保留在目标文件中的符号 |
| `import_impact` | import 更新影响列表，显示受影响文件及旧/新 import 对 |

编辑时将需要提取的符号从 `retain` 移到 `modules` 中的目标模块，或调整模块分组。

## 子目录支持

模块名中使用 `/` 可创建子目录结构。例如：

- `_migrated/types` → 输出文件为 `_migrated/types.py`，自动创建 `_migrated/` 目录和 `__init__.py`
- `_migrated/models/user` → 输出文件为 `_migrated/models/user.py`，自动补全所有中间目录的 `__init__.py`

模块名每个路径段必须是合法 Python 标识符，不能是关键字。对应的 Python import 语句将 `/` 替换为 `.`，如 `_migrated.types`。

## 核心特性

- **LibCST 无损提取**：基于 CST（Concrete Syntax Tree）提取代码，完整保留注释、格式和空白字符
- **CSTTransformer 更新 import**：使用 CSTTransformer 精确修改 import 语句，绝不使用正则替换
- **增量分析**：基于文件哈希的增量解析，未修改文件自动跳过
- **跨文件依赖追踪**：自动识别并记录符号间的跨文件依赖关系
- **三步校验**：迁移后自动执行符号完整性、格式无损性、import 可达性三项验证

## 真实案例：12,775 行 FastAPI 文件拆分

fissionpy 成功处理过 12,775 行的 `presales_api.py` 文件（FastAPI 路由模块），将其拆分为 7 个模块：

```bash
# 分析 158 个文件，3190 个符号（65 秒）
fission analyze ./backend/

# 生成计划，手动编辑将 454 个符号分配到 7 个模块
fission plan --target app/presales_api.py --output plan.yaml

# 提取 127 个符号到 6 个新模块（21 秒）
fission extract plan.yaml

# 迁移并更新 2 个依赖文件的 import（80 秒）
fission migrate plan.yaml
```

**结果**：

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/presales_api.py` | 8,783 | 重组后（减少 3,992 行，31%） |
| `app/_di.py` | 157 | DI 配置 + router + providers |
| `app/case_api.py` | 2,171 | Case API 端点 |
| `app/knowledge_api.py` | 758 | 知识库 API 端点 |
| `app/mailbox_api.py` | 462 | 邮箱同步 API |
| `app/template_api.py` | 421 | 模板 & FAQ API |
| `app/misc_api.py` | 413 | 其他 API |

**总计**：~3 分钟完成 12,775 行大型文件的无损拆分与迁移，所有校验通过。

## AI Agent Skill

fissionpy 提供了专为 AI Agent 设计的 Skill 文件（`SKILL.md`），让 AI 编程助手能够自主完成大型 Python 文件的拆分迁移工作。

### 安装 Skill

将 fissionpy 项目克隆到本地后，Skill 文件位于项目根目录的 `SKILL.md`。AI Agent 可通过以下方式加载：

```bash
# 克隆项目
git clone https://github.com/your-org/fissionpy.git

# AI Agent 自动识别 SKILL.md 并加载工作流
```

### Skill 触发条件

当用户发出以下指令时，AI Agent 会自动激活 fissionpy Skill：

- "拆分这个 Python 文件"
- "将 [file.py] 拆分成多个模块"
- "重构大型文件"
- "split this Python file"
- "refactor large module"
- 发现文件超过 1000 行时主动建议拆分

### Skill 工作流

AI Agent 加载 Skill 后，会按照以下 6 阶段自动执行：

1. **分析项目** → `fission analyze` 索引所有符号和依赖
2. **浏览符号** → `fission show` / `fission tree` 了解文件结构
3. **生成计划** → `fission plan` 创建 YAML 迁移计划
4. **编辑计划** → 智能分配符号到合理模块（用户可调整）
5. **提取符号** → `fission extract` 无损提取代码
6. **完成迁移** → `fission migrate` 更新全项目 import 并校验

### Skill 特性

- **自主执行**：AI Agent 可自动完成从分析到迁移的完整流程
- **智能分组**：基于依赖连通分量自动建议模块拆分方案
- **安全校验**：每步操作后自动验证，确保代码无损
- **最佳实践**：内置模块命名约定、拆分策略、边界情况处理
- **故障排除**：提供常见问题诊断和解决方案

## 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试（63 个测试，<1 秒）
pytest tests/
```

## 技术栈

- **LibCST**：Python 具体语法树解析，支持无损代码操作
- **Typer**：CLI 框架，基于 Click 的类型安全封装
- **SQLite**：轻量级关系型数据库，存储项目符号索引
- **ruamel.yaml**：支持 round-trip 的 YAML 解析器
- **pytest**：测试框架，63 个单元测试 + 集成测试

## 许可证

MIT License

Copyright (c) 2025 FissionPy Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
