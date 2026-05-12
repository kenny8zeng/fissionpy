# Feature Specification: Export Index to JSON

**Feature Branch**: `003-export-json`
**Created**: 2026-05-12
**Status**: Draft
**Input**: User description: "增加一个功能，将索引到sqlite中整个工程目录的所有符号和依赖关系输出到json文件。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 导出全量符号与依赖关系 (Priority: P1)

用户在完成 `fission analyze` 后，希望将整个工程的符号表和依赖关系导出为 JSON 文件，供外部工具（如可视化、审计、AI Agent）消费。

**Why this priority**: 这是核心需求，所有其他用途都依赖此基础导出能力。

**Independent Test**: 运行 `fission export` 命令后，检查输出 JSON 文件是否包含完整的文件列表、符号列表和依赖关系。

**Acceptance Scenarios**:

1. **Given** 已完成 `fission analyze` 的工程目录，**When** 用户执行导出命令，**Then** 生成一个 JSON 文件，包含所有已索引文件的符号信息和依赖关系。
2. **Given** 已完成 `fission analyze` 的工程目录，**When** 用户指定输出路径，**Then** JSON 文件写入指定路径。
3. **Given** 未完成 `fission analyze` 的工程目录，**When** 用户执行导出命令，**Then** 提示用户先运行 analyze。

---

### User Story 2 - 按文件筛选导出范围 (Priority: P2)

用户只想导出某个文件的符号和依赖关系，而非整个工程。

**Why this priority**: 大型工程全量导出可能很大，按文件筛选更实用。

**Independent Test**: 使用 `--file` 参数指定文件后，检查 JSON 只包含该文件的相关数据。

**Acceptance Scenarios**:

1. **Given** 已完成 analyze 的工程目录，**When** 用户指定 `--file` 参数，**Then** 仅导出该文件的符号和依赖关系。
2. **Given** 已完成 analyze 的工程目录，**When** 用户指定不存在的文件，**Then** 提示文件未索引。

---

### User Story 3 - AI Agent 自动化消费 (Priority: P3)

AI Agent 通过 CLI 调用导出命令，获取结构化 JSON 数据用于智能拆分决策。

**Why this priority**: AI Agent 是重要用户，但基础导出能力（P1）已满足其核心需求。

**Independent Test**: AI Agent 执行命令后能解析 JSON 并基于符号和依赖数据做出决策。

**Acceptance Scenarios**:

1. **Given** AI Agent 在工程根目录执行导出命令，**When** 命令成功执行，**Then** 输出的 JSON 格式稳定、可解析，包含符号间依赖的方向和类型。

---

### Edge Cases

- 数据库为空（未分析过）时执行导出 → 应报错提示
- 数据库文件不存在时执行导出 → 应报错提示
- 导出路径不可写时 → 应报错提示
- 工程目录包含大量符号（>10000）时 → 应在合理时间内完成导出
- 跨文件依赖中引用了已删除文件中的符号 → 仍应包含在导出中，但标注状态

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供 CLI 命令，将已索引的符号和依赖关系导出为 JSON 文件
- **FR-002**: 导出的 JSON 必须包含完整的文件列表（路径、状态）
- **FR-003**: 导出的 JSON 必须包含每个文件下的所有符号（名称、类型、行号范围）
- **FR-004**: 导出的 JSON 必须包含所有符号间的依赖关系（源符号、目标符号、依赖类型、是否跨文件）
- **FR-005**: 导出的 JSON 必须包含每个文件的 import 语句信息
- **FR-006**: 用户必须能够指定输出文件路径（默认 `./fission-index.json`）
- **FR-007**: 用户必须能够指定数据库路径（与现有命令保持一致）
- **FR-008**: 用户必须能够通过 `--file` 参数筛选单个文件的导出范围
- **FR-009**: 命令必须支持 `--verbose` 参数显示导出详情
- **FR-010**: 导出的 JSON 必须使用 UTF-8 编码，支持中文符号名
- **FR-011**: 路径必须遵循项目已有的路径一致性规则（统一修剪 `./` 前缀）

### Key Entities

- **文件条目**: 文件路径、解析状态、符号数量
- **符号条目**: 符号名、类型（函数/类/变量）、所属文件、行号范围
- **依赖条目**: 源符号、目标符号、依赖类型、是否跨文件
- **导入条目**: 文件路径、import 类型、模块路径、导入的名称列表

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户通过一条命令即可完成符号和依赖关系的完整导出
- **SC-002**: 导出的 JSON 文件可被标准 JSON 解析器正确解析
- **SC-003**: 导出 10000 个符号的工程在 5 秒内完成
- **SC-004**: 导出数据与 `fission show` / `fission tree` 展示的数据完全一致
- **SC-005**: 命令风格与现有 fission CLI 命令保持一致（选项命名、路径规则、输出风格）

## Assumptions

- 导出功能依赖已有的 `fission analyze` 产出的数据库，不独立进行分析
- JSON 输出格式不需要版本号字段（v1 不需要考虑向后兼容）
- 不需要支持增量导出（每次全量导出）
- 导出路径默认与 `fission-plan.yaml` 同目录（工程根目录）
- `--file` 筛选时，依赖关系仅导出与该文件符号相关的条目
