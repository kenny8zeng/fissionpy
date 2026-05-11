# Feature Specification: Python 工程目录裂变迁移工具

**Feature Branch**: `002-project-fission`
**Created**: 2026-05-11
**Status**: Draft
**Input**: User description: "做功能升级，不针对单一目标文件进行拆分，工作流调整为：1. 分析目录 2. 浏览符号 3. 生成计划 4. 执行提取 5. 完成迁移。使用LibCST执行文件分析，实现代码块保留注释和风格等无损迁移。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 分析工程目录，建立全局符号索引 (Priority: P1)

开发者有一个包含多个 Python 文件的工程目录，需要理解整个项目的符号结构。CLI 工具递归扫描该目录下所有 `.py` 文件，使用 LibCST 解析每个文件的顶层符号（函数、类、变量）和文件间的 import 依赖关系，将结果写入项目级 SQLite 数据库。分析完成后，开发者可以查询任意文件的符号列表、任意符号的定义位置和依赖信息。

**Why this priority**: 全局符号索引是所有后续操作的基础——没有项目级索引就无法做跨文件依赖分析和迁移决策。

**Independent Test**: 给定一个包含 3 个以上 `.py` 文件的工程目录，执行分析命令后，SQLite 数据库中应包含所有文件的符号表、文件间 import 关系和跨文件依赖关系。

**Acceptance Scenarios**:

1. **Given** 一个包含 `app/models.py`（定义 `User`、`Product`）和 `app/views.py`（`from app.models import User`）的工程目录，**When** 开发者运行目录分析命令，**Then** SQLite 中记录两个文件、4 个符号（User、Product、及 views.py 中的顶层符号）、以及 `views.py` 对 `models.py` 中 `User` 的跨文件依赖
2. **Given** 目录中包含 `__init__.py` 和子目录，**When** 运行分析命令，**Then** 递归扫描所有子目录中的 `.py` 文件，包括 `__init__.py`
3. **Given** 目录中某文件有语法错误，**When** 运行分析命令，**Then** 跳过该文件并报告警告，其余文件正常索引
4. **Given** 已分析过的目录，**When** 再次运行分析命令且文件内容未变（hash 相同），**Then** 跳过未变更文件的分析，仅处理新增或修改的文件

---

### User Story 2 - 浏览符号和依赖关系 (Priority: P2)

开发者需要查看项目中的符号信息来决定拆分策略。CLI 工具提供多种查询方式：列出指定文件的顶层符号、查看指定符号的所属文件和代码行数、查看符号的依赖和被依赖关系（包括跨文件）、以及以树形视图展示指定文件的符号依赖树。

**Why this priority**: 符号浏览是拆分决策的依据，但不依赖后续的提取/迁移逻辑。

**Independent Test**: 给定已分析的工程目录，运行查询命令后能正确展示符号信息、依赖关系和依赖树。

**Acceptance Scenarios**:

1. **Given** 已分析的工程目录，**When** 开发者查询文件 `app/models.py` 的符号列表，**Then** 展示该文件所有顶层符号的名称、类型（function/class/assignment）和行号范围
2. **Given** 已分析的工程目录，**When** 开发者查询符号 `User` 的信息，**Then** 展示其所属文件、行数、依赖了哪些其他符号、以及被哪些文件中的哪些符号依赖
3. **Given** 已分析的工程目录，**When** 开发者查询文件 `app/views.py` 的依赖树，**Then** 以缩进树形格式展示该文件每个顶层符号的依赖链路，跨文件依赖标注来源文件
4. **Given** 已分析的工程目录，**When** 开发者查询一个不存在的符号名，**Then** 报告该符号未找到

---

### User Story 3 - 为目标文件生成拆分计划 (Priority: P3)

开发者确定了要拆分的目标文件后，CLI 工具根据全局索引为该文件生成 YAML 格式的迁移计划模板。模板列出该文件的所有顶层符号，默认全部保留在原文件中。开发者编辑模板，将需要提取的符号移到目标模块下。计划中还应包含自动计算的跨文件影响提示——哪些其他文件会因符号迁移而需要更新 import。

**Why this priority**: 计划生成依赖全局索引和符号浏览，是执行提取的前提。

**Independent Test**: 给定已分析的工程目录和目标文件名，运行计划生成命令后输出 YAML 文件，包含该文件所有符号和跨文件影响提示。

**Acceptance Scenarios**:

1. **Given** 已分析的工程目录中 `app/models.py` 有 5 个顶层符号，**When** 为该文件生成计划，**Then** YAML 文件列出全部 5 个符号，默认标记为 `retain`
2. **Given** 开发者将 `User` 从 `app/models.py` 的 `retain` 移到 `app/_migrated/user_types` 模块，**When** 工具校验该计划，**Then** 自动提示 `app/views.py` 中的 `from app.models import User` 需要更新为 `from app._migrated.user_types import User`
3. **Given** 计划中引用了目标文件中不存在的符号名，**When** 校验计划，**Then** 报告错误并指出无效符号名
4. **Given** 计划中目标模块名包含子目录路径（如 `app/_migrated/user_types`），**When** 校验计划，**Then** 视为合法路径

---

### User Story 4 - 执行提取，即时校对一致性 (Priority: P4)

开发者确认拆分计划后，CLI 工具按计划将指定符号从目标文件提取到新模块文件。提取使用 LibCST 的 lossless 特性，完整保留注释、空行、缩进和代码格式。每提取一个符号后即时校对逻辑一致性，确保提取的代码块与原始代码文本一致。提取过程中同时计算跨文件依赖的变更，验证迁移方案在依赖关系上是否可行。

**Why this priority**: 提取是核心操作，但依赖分析、计划生成必须先完成。即时校对确保每一步的正确性。

**Independent Test**: 给定有效的 YAML 计划，运行提取命令后，指定符号被无损写入对应模块文件，每次提取后校对通过。

**Acceptance Scenarios**:

1. **Given** 计划要求将 `User` 和 `Product` 提取到 `app/_migrated/user_types`，**When** 执行提取，**Then** 生成 `app/_migrated/user_types.py` 包含 `User` 和 `Product`，且代码文本与原始文件中逐行一致（注释、空行、缩进零丢失）
2. **Given** 提取过程中符号 `User` 已完成但 `Product` 失败，**When** 查看进度，**Then** `User` 标记为已完成，`Product` 标记为失败，已完成部分不回滚
3. **Given** 提取的符号 `User` 依赖同文件中保留的符号 `_helper`，**When** 提取到新模块后，**Then** 新模块文件自动添加 `from app.models import _helper`（按包结构正确的 import 路径）
4. **Given** 提取会创建循环依赖（A 模块依赖 B 模块，B 模块又依赖 A 模块），**When** 执行提取，**Then** 检测并报告循环依赖风险

---

### User Story 5 - 完成迁移，更新全项目引用 (Priority: P5)

提取完成后，CLI 工具执行项目级迁移：逐个更新迁移符号在整个工程目录中的被依赖关系——修改所有引用了迁移符号的文件的 import 语句。更新完成后，重命名目标文件为备份，将未迁移的剩余符号提取成新的目标文件，在原文件位置添加重导出 import 保持向后兼容。最终执行方法检查和一致性校对，输出迁移总结报告。

**Why this priority**: 迁移是最终的收尾步骤，确保项目级引用完整性。只有提取和迁移都正确完成，整个拆分才算成功。

**Independent Test**: 给定已提取的状态，运行迁移命令后，所有引用迁移符号的文件 import 被正确更新，原文件备份重组，项目可正常导入。

**Acceptance Scenarios**:

1. **Given** `User` 从 `app/models.py` 迁移到 `app/_migrated/user_types.py`，且 `app/views.py` 中有 `from app.models import User`，**When** 执行迁移，**Then** `app/views.py` 中的 import 更新为 `from app._migrated.user_types import User`
2. **Given** 迁移完成后，**When** 在原文件 `app/models.py` 位置生成新文件，**Then** 新文件仅含保留符号和必要的 import，原文件重命名为 `app/models.py.bak`
3. **Given** `User` 被其他文件引用，**When** 生成新的 `app/models.py`，**Then** 包含 `from app._migrated.user_types import User` 重导出，确保旧代码 `from app.models import User` 仍然可用
4. **Given** 迁移过程中某文件的 import 更新失败，**When** 输出迁移报告，**Then** 明确列出失败的文件和原因，已成功的更新不回滚
5. **Given** 迁移全部完成，**When** 执行最终检查，**Then** Python 解释器可无错误导入所有迁移后的模块（无 ImportError、无 AttributeError）

---

### Edge Cases

- 目标文件包含条件性导入（`try/except import`）时，import 更新如何处理？
- 迁移符号与项目其他文件中的同名符号冲突时如何处理？
- `from module import *` 引用了迁移符号时如何处理？
- 文件中包含 `if __name__ == "__main__"` 块，该块不属于任何顶层符号但可能依赖多个符号，如何处理？
- 目录中包含 `__pycache__`、`.venv`、`node_modules` 等应排除的目录时，分析如何过滤？
- 迁移符号的装饰器引用了其他文件中的符号，import 更新是否覆盖装饰器依赖？
- 同一符号被同一文件以多种方式引用（直接 import + 别名 import），迁移时是否全部更新？
- 迁移目标路径中需要新建 `__init__.py` 使其成为合法 Python 包时，工具是否自动创建？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 工具 MUST 递归扫描指定工程目录下的所有 `.py` 文件，跳过排除目录（如 `__pycache__`、`.venv`、`.git`），将文件路径和内容 hash 索引到 SQLite
- **FR-002**: 工具 MUST 使用 LibCST 解析每个 `.py` 文件的顶层符号（函数定义、类定义、变量赋值语句），记录名称、类型、行号范围和完整源码文本
- **FR-003**: 工具 MUST 分析每个文件内的符号间依赖关系（调用、引用、继承、装饰器、类型注解），以及文件间的 import 依赖关系（`import X`、`from X import Y`），将所有依赖写入 SQLite
- **FR-004**: 工具 MUST 支持增量分析——已索引且内容 hash 未变的文件跳过重新解析，仅处理新增或修改的文件
- **FR-005**: 工具 MUST 提供符号浏览命令——列出指定文件的顶层符号、查询指定符号的所属文件/行数/依赖/被依赖信息
- **FR-006**: 工具 MUST 提供指定文件的符号依赖树展示功能，跨文件依赖标注来源文件名
- **FR-007**: 工具 MUST 为指定目标文件生成 YAML 迁移计划模板，列出该文件所有顶层符号，默认标记为 `retain`
- **FR-008**: YAML 计划中 MUST 支持子目录路径作为目标模块名（如 `app/_migrated/user_types`），工具在提取时创建对应目录结构
- **FR-009**: 工具 MUST 对用户编辑后的 YAML 计划进行校验——检查符号名有效性、目标模块路径合法性、自动计算跨文件影响并提示
- **FR-010**: 工具 MUST 使用 LibCST 的 lossless 特性将指定符号从目标文件提取到新模块文件——保留原始注释、空行、缩进和代码格式，确保提取后代码文本与原始文件中逐行一致
- **FR-011**: 提取过程 MUST 逐符号执行，每提取一个符号后即时校对逻辑一致性——对比提取的代码块与原始代码文本
- **FR-012**: 提取完成后，工具 MUST 根据依赖元数据自动为新模块文件生成所需的 import 语句，确保同文件内和跨文件依赖链路完整
- **FR-013**: 工具 MUST 检测提取后的循环依赖风险（两个或多个模块互相 import），并发出警告
- **FR-014**: 工具 MUST 逐个更新迁移符号在整个工程目录中的被依赖关系——修改所有引用了迁移符号的文件的 import 语句，使用 LibCST 进行 CST 级别的精确替换
- **FR-015**: 工具 MUST 在更新 import 时处理 `from X import Y` 和 `from X import Y as Z` 两种形式，确保别名引用正确更新
- **FR-016**: 迁移完成后，工具 MUST 将原始目标文件重命名为备份文件（添加 `.bak` 后缀）
- **FR-017**: 工具 MUST 将未迁移的剩余符号提取为新的同名目标文件，包含必要的 import 语句和保留符号的完整代码
- **FR-018**: 新的目标文件 MUST 包含重导出 import（如 `from new_module import MigratedSymbol`），保持旧代码 `from original_file import MigratedSymbol` 的向后兼容
- **FR-019**: 迁移完成后，工具 MUST 执行最终一致性检查——验证所有迁移后的模块可被 Python 解释器无错误导入，所有跨文件引用完整
- **FR-020**: 工具 MUST 输出迁移总结报告，列出：已迁移符号、已更新的文件列表、新增的模块文件、备份文件路径、循环依赖警告、失败项

### Key Entities

- **工程目录（ProjectDirectory）**: 被分析的 Python 工程根目录；包含多个 `.py` 文件和子目录
- **文件记录（FileRecord）**: 索引到 SQLite 的 `.py` 文件；属性包括路径、内容 hash、解析状态
- **顶层符号（TopLevelSymbol）**: Python 文件中定义在模块顶层的函数、类、变量；属性包括名称、类型、行号范围、所属文件、源码文本
- **文件间导入（FileImport）**: 文件中的 import 语句记录；属性包括来源文件、import 类型（import/from_import）、模块路径、导入的符号名列表
- **依赖关系（Dependency）**: 两个符号之间的引用关系；区分文件内依赖和跨文件依赖
- **迁移计划（MigrationPlan）**: YAML 格式的符号迁移指令集合；每个符号对应一条指令（保留或迁移到指定模块）
- **迁移记录（MigrationRecord）**: 记录迁移过程中每个符号的状态；属性包括迁移状态、源文件、目标模块、时间戳
- **Import更新记录（ImportUpdate）**: 记录需要对项目文件执行的 import 语句变更；属性包括目标文件、旧 import、新 import

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 个 `.py` 文件以内的工程目录，完整分析和索引完成时间不超过 30 秒
- **SC-002**: 符号浏览和依赖查询响应时间不超过 1 秒
- **SC-003**: 迁移后的所有模块文件可被 Python 解释器无错误导入（无 ImportError、无 AttributeError）
- **SC-004**: 提取后的代码块与原始代码文本逐行一致，注释和空行零丢失
- **SC-005**: 迁移后项目所有文件中被迁移符号的引用 100% 被正确更新（`from X import Y` 和 `from X import Y as Z` 两种形式）
- **SC-006**: 迁移过程中断后重启，可从中断位置继续或了解中断位置
- **SC-007**: 向后兼容性——迁移后旧代码 `from original_file import MigratedSymbol` 仍可正常工作

## Design Constraints

- **代码无损提取**: 使用 LibCST 作为解析引擎——LibCST 保留所有空白和注释信息，确保提取后的代码块与原始文件中的外观完全一致，包括函数/类上方的文档注释、行内注释、装饰器注释、间隔空行等均不丢失
- **CST 级别 Import 更新**: 跨文件 import 更新必须使用 LibCST 的 CSTTransformer 进行精确替换，不使用正则替换或文本替换

## Assumptions

- 目标工程目录是合法的 Python 项目，文件内代码无语法错误
- 顶层符号的粒度为整个函数/类/变量定义，不考虑将函数内部逻辑拆分到不同模块
- 拆分后的模块文件与原始文件在同一 Python 包内（同一项目根目录下）
- `if __name__ == "__main__"` 块始终保留在原文件中
- 条件性导入（`try/except import`）的 import 更新按静态最大集处理（即假设所有分支都可能执行）
- 备份文件使用 `.bak` 后缀，不会自动删除，由开发者决定是否清理
- 排除目录默认包含 `__pycache__`、`.git`、`.venv`、`node_modules`、`site-packages`
- 迁移目标路径如需成为合法 Python 包，工具自动创建 `__init__.py`
- `from module import *` 的引用更新按最佳努力处理，无法静态解析的标记为需人工确认
