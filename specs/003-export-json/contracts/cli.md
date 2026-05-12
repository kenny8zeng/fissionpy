# CLI Contract: fission export

**Date**: 2026-05-12
**Feature**: 003-export-json

## Command

```
fission export [--file PATH] [--db PATH] [--output PATH] [--include-source] [--verbose]
```

## Arguments & Options

| Parameter        | Type   | Required | Default                | Description                    |
|------------------|--------|----------|------------------------|--------------------------------|
| --file           | string | No       | (none, 全量导出)        | 筛选指定文件的符号和依赖        |
| --db             | string | No       | `./.fission/fission.db` | SQLite 数据库路径              |
| --output         | string | No       | `./fission-index.json`  | JSON 输出路径                  |
| --include-source | flag   | No       | false                  | 包含符号源代码文本              |
| --verbose        | flag   | No       | false                  | 详细输出                       |

## Behavior

### 全量导出（无 --file）

1. 打开数据库连接
2. 查询所有非 deleted 文件
3. 查询所有符号（关联文件信息）
4. 查询所有依赖关系
5. 查询所有 import 语句
6. 组装 JSON 结构并写入输出文件
7. 输出统计信息：文件数、符号数、依赖数、import 数

### 按文件筛选（有 --file）

1. 使用 `normalize_path` 处理文件路径
2. 查找文件记录（与 `show`/`tree` 一致的查找逻辑）
3. 查询该文件的符号
4. 查询该文件的依赖关系（双向）
5. 查询该文件的 import 语句
6. 组装 JSON 结构并写入输出文件
7. 输出统计信息

## Output Format

stdout 示例（verbose 模式）：

```
导出完成: 156 文件, 3227 符号, 3719 依赖, 845 import
写入: ./fission-index.json
```

stdout 示例（非 verbose 模式）：

```
导出完成: 156 文件, 3227 符号, 3719 依赖, 845 import
写入: ./fission-index.json
```

## Error Handling

| 条件                   | 输出                          | Exit Code |
|------------------------|-------------------------------|-----------|
| 数据库文件不存在       | `数据库不存在: <path>`         | 1         |
| 数据库无数据           | `暂无已索引数据，请先运行 fission analyze` | 1 |
| --file 指定的文件未索引 | `文件未索引: <path>`           | 1         |
| 输出路径不可写         | `无法写入: <path>`             | 1         |
| 成功                   | 统计信息 + 写入路径            | 0         |

## Path Consistency

遵循项目路径一致性规则：
- `--file` 参数使用 `normalize_path` 修剪 `./` 前缀
- JSON 中的路径与数据库存储格式一致（无 `./` 前缀）
- `--db` 和 `--output` 参数与现有命令默认值风格一致
