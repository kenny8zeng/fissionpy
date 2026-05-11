# CLI Command Contracts: fissionpy

**Feature**: 002-project-fission
**Date**: 2026-05-11

## 命令总览

| 命令 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `fission analyze` | 分析工程目录，索引所有文件和符号 | 目录路径 | SQLite 数据库 |
| `fission show` | 浏览符号信息 | 符号名或文件路径 | 终端格式化输出 |
| `fission tree` | 打印符号依赖树 | 文件路径 | 终端树形视图 |
| `fission plan` | 生成 YAML 迁移计划模板 | 目标文件路径 | YAML 文件 |
| `fission extract` | 执行代码提取 | YAML 计划文件 | 新模块文件 + SQLite 进度 |
| `fission migrate` | 完成项目级迁移 | YAML 计划文件 | 更新文件 + 迁移报告 |

---

## `fission analyze`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `directory` | PATH | 是 | Python 工程目录路径 |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--exclude` | TEXT | 否 | 追加排除目录模式（可多次使用） |
| `--force` | FLAG | 否 | 强制重新解析所有文件（忽略 hash 缓存） |

### 输出

- SQLite 数据库写入 files / symbols / dependencies / file_imports 四张表
- stdout: 扫描摘要（文件数、符号数、依赖数、跨文件依赖数、耗时）

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 分析成功 |
| 1 | 目录不存在 |
| 2 | 无 .py 文件被发现 |

---

## `fission show`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `--file` | TEXT | 否 | 查看指定文件的顶层符号列表 |
| `--symbol` | TEXT | 否 | 查看指定符号的详情（所属文件、行数、依赖、被依赖） |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |

### 输出

- `--file`: 文件符号表格（名称、类型、行号范围）
- `--symbol`: 符号详情（所属文件、行数、依赖列表、被依赖列表，跨文件标注来源文件）
- 未指定 `--file` 或 `--symbol`: �列出项目中所有已索引文件的概览

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 展示成功 |
| 1 | 数据库不存在或无分析数据 |
| 2 | 指定的文件或符号未找到 |

---

## `fission tree`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `--file` | TEXT | 是 | 目标文件路径 |
| `--symbol` | TEXT | 否 | 仅展示指定符号的子树 |
| `--reverse` | FLAG | 否 | 反向视图：展示谁依赖了该符号 |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |

### 输出

- 终端树形视图（rich.tree 渲染）
- 颜色编码：函数=青色，类=黄色，变量=白色，跨文件依赖=品红色+文件标注
- 依赖箭头=灰色

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 展示成功 |
| 1 | 数据库不存在或无分析数据 |
| 2 | 指定文件未找到 |

---

## `fission plan`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `--target` | TEXT | 是 | 要拆分的目标文件路径 |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--output` | PATH | 否 | YAML 输出路径，默认 `./fission-plan.yaml` |

### 输出

- YAML 文件，目标文件的所有符号默认标记 `retain`
- 包含 `import_impact` 段：自动计算跨文件影响提示
- 每个符号附带注释说明类型和行号范围

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 生成成功 |
| 1 | 数据库无分析数据 |
| 2 | 目标文件未在索引中找到 |

---

## `fission extract`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `plan` | PATH | 是 | YAML 迁移计划文件路径 |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--resume` | FLAG | 否 | 从上次中断处继续提取 |

### 处理流程

1. 校验 YAML 计划合法性（符号有效性、模块路径合法性）
2. 计算跨文件依赖影响，校验迁移可行性
3. 逐符号执行提取，每个符号即时校对代码一致性
4. 为新模块文件生成 import 语句
5. 检测循环依赖风险

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 全部提取成功 |
| 1 | 计划校验失败 |
| 2 | 部分符号提取失败 |
| 3 | 检测到循环依赖风险 |

---

## `fission migrate`

### 输入

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `plan` | PATH | 是 | YAML 迁移计划文件路径 |
| `--db` | PATH | 否 | SQLite 数据库路径，默认 `./.fission/fission.db` |
| `--no-reexport` | FLAG | 否 | 不在原文件生成重导出 import |
| `--resume` | FLAG | 否 | 从上次中断处继续迁移 |

### 处理流程

1. 确认 extract 已完成
2. 逐个更新迁移符号在项目所有文件中的 import 引用
3. 自动创建目标路径的 `__init__.py`（如不存在）
4. 重命名原始目标文件为 `.bak`
5. 将剩余符号提取为新的同名目标文件
6. 添加重导出 import（保持向后兼容）
7. 执行最终一致性检查（Python import 验证 + 符号完整性 + 格式无损性）
8. 输出迁移总结报告

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 迁移全部成功 |
| 1 | extract 未完成 |
| 2 | 部分文件 import 更新失败 |
| 3 | 最终一致性检查失败 |

### 迁移报告格式

```text
迁移报告
========
目标文件: app/models.py → app/models.py.bak
迁移符号: User, Admin, Product

新增模块:
  ✓ app/_migrated/user_types.py (User, Admin)
  ✓ app/_migrated/product_types.py (Product)

import 更新:
  ✓ app/views.py: from app.models import User → from app._migrated.user_types import User
  ✓ app/api.py: from app.models import Product → from app._migrated.product_types import Product
  ✗ app/legacy.py: 更新失败 (原因: ...)

重导出:
  ✓ app/models.py: from app._migrated.user_types import User, Admin
  ✓ app/models.py: from app._migrated.product_types import Product

自动创建:
  ✓ app/_migrated/__init__.py

最终检查:
  ✓ 所有模块 Python import 验证通过
  ✓ 符号完整性通过
  ✓ 格式无损性通过

统计: 3 符号迁移, 2 文件 import 更新, 0 失败
```

## 全局选项

| 选项 | 类型 | 说明 |
|------|------|------|
| `--db` | PATH | SQLite 数据库路径，所有命令共享，默认 `./.fission/fission.db` |
| `--verbose` | FLAG | 详细输出模式 |
| `--version` | FLAG | 显示版本号 |
