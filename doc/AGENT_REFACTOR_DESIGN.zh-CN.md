# Free Markdown Translator Agent 化重构设计文档

## 1. 文档目标

本文档给出一套可直接实施的破坏性重构方案，用于将当前项目重构为基于 AI Agent 的 Markdown 翻译系统。

本次重构遵循以下原则：

- 不保留原有的手写节点解析与按行拼接架构
- 不以兼容旧模块为目标
- 以结构正确性、译文连贯性、可验证性为核心
- 采用“结构解析”和“语言生成”彻底解耦的设计
- 采用多阶段 Agent 流水线，而不是单次翻译调用

---

## 2. 重构目标

### 2.1 需要解决的问题

当前项目存在以下结构性问题：

1. Markdown 解析依赖手写规则和正则拆分，无法稳定覆盖复杂 Markdown 语法。
2. 翻译单位以“行”或“局部碎片”为主，导致长段落、列表、上下文关联内容容易语义不连贯。
3. 格式保护主要依赖 prompt 和字符串回填，没有独立、可靠的格式校验机制。
4. 翻译、结构处理、输出拼接强耦合，导致模块不可替换、不可测试、不可扩展。
5. 缺少文档级上下文、术语记忆、审校机制，难以保证跨段一致性。

### 2.2 重构后的目标能力

重构后的系统应具备：

- 正确解析复杂 Markdown，包括标题、列表、嵌套列表、表格、引用、HTML 混排、front matter、图片、链接、代码块
- 以“语义片段”而非“单行文本”作为翻译单位
- 基于 Agent 执行翻译、术语约束、审校、格式监督
- 保证不可翻译结构绝不被误修改
- 对输出进行自动校验和失败回退
- 支持后续扩展到多模型、多提供商、多工作流

---

## 3. 总体架构

### 3.1 核心思想

新架构分为四层：

1. 结构层
   负责 Markdown 解析、AST 管理、可翻译节点提取、渲染。

2. Agent 层
   负责翻译、术语一致性、译后审校、格式监督。

3. 验证层
   负责输出结构校验、front matter 校验、链接与代码块完整性检查。

4. 编排层
   负责整个文档翻译流水线、失败重试、缓存、并发调度、产物写出。

### 3.2 新流程

完整处理流程如下：

1. 读取 Markdown 文件
2. 解析为 AST
3. 提取可翻译语义片段
4. 构建文档级上下文与术语约束
5. 使用 Translator Agent 分段翻译
6. 使用 Reviewer Agent 做译后审校和统一性修正
7. 使用 Format Guard Agent 做格式监督
8. 将翻译结果写回 AST
9. 重新渲染 Markdown
10. 运行验证器检查结构正确性
11. 产出目标文件和质量报告

---

## 4. 关键技术路线

### 4.1 Markdown 结构处理

不再维护自定义 `Node` 类型，也不再手工识别标题、链接、列表项。

推荐路线：

- 优先方案：`markdown-it-py`
- 备选方案：`mistune` AST 模式
- 高稳定性备选：通过 `pandoc` 做 AST 转换

建议优先选择 `markdown-it-py`，原因如下：

- 生态成熟
- 对 CommonMark 兼容较好
- Token/结构边界明确
- 易于扩展 plugin
- 适合在 Python 中做二次处理

### 4.2 翻译单位

翻译单位不再是行，而是 `Segment`。

一个 `Segment` 表示一个可翻译的语义单元，典型包括：

- 标题文本
- 段落文本
- 列表项文本
- 引用文本
- 表格单元格文本
- 图片 alt 文本
- front matter 中允许翻译的字段值

以下内容默认不可翻译：

- fenced code block
- inline code
- URL
- HTML 标签名和属性名
- front matter 中结构字段
- 原始 Markdown 符号

### 4.3 Agent 工作流

核心 Agent 分为三类：

1. `TranslatorAgent`
   负责将一个 `SegmentBundle` 从源语言翻译为目标语言。

2. `ReviewerAgent`
   负责在文档级上下文内检查术语统一、语气一致、跨段衔接、歧义修复。

3. `FormatGuardAgent`
   负责检查译文是否引入结构风险，只允许最小文本级修复，不允许任意改写结构。

注意：

- 格式保护不能只依赖 Agent，必须同时由程序验证器兜底
- Agent 只负责文本建议，最终结构合法性由验证器决定

---

## 5. 模块设计

建议完全重组目录：

```text
src/
  cli/
    main.py
    commands.py
  core/
    pipeline.py
    orchestrator.py
    models.py
    types.py
    errors.py
  parser/
    markdown_parser.py
    frontmatter.py
    segment_extractor.py
    ast_mapper.py
    renderer.py
  agents/
    translator_agent.py
    reviewer_agent.py
    format_guard_agent.py
    prompts.py
  llm/
    client.py
    provider.py
    schemas.py
  memory/
    glossary.py
    translation_memory.py
    document_context.py
  validators/
    markdown_validator.py
    structure_validator.py
    frontmatter_validator.py
    output_report.py
  infra/
    config.py
    logging.py
    cache.py
    retry.py
  tests/
    fixtures/
    unit/
    integration/
    e2e/
```

### 5.1 `core`

负责流程编排，不直接关心 Markdown 细节和模型实现。

核心职责：

- 接收翻译任务
- 管理文档处理状态
- 调度 Agent 顺序
- 处理失败重试与回退
- 汇总质量报告

### 5.2 `parser`

负责结构真相。

核心职责：

- 将 Markdown 解析为中间结构
- 抽取可翻译文本节点
- 为每个文本节点分配稳定 ID
- 记录节点与 AST 的映射关系
- 将译文写回 AST
- 渲染最终 Markdown

### 5.3 `agents`

负责所有模型任务定义。

要求：

- Agent 输入输出必须是结构化数据，不允许只返回自由文本
- 每类 Agent 只承担单一职责
- Prompt 与代码逻辑分离

### 5.4 `memory`

负责提升文档级一致性。

核心能力：

- 术语表加载和强约束
- 历史翻译缓存
- 文档摘要
- 章节标题链路
- 源文片段和目标文片段对照记录

### 5.5 `validators`

负责兜底，避免“看起来翻译成功，实际上格式已坏”。

必须包含：

- front matter YAML 可解析校验
- Markdown 二次解析校验
- 结构 diff 校验
- 代码块 fence 完整性校验
- 表格列数一致性校验
- 链接 URL 不变性校验

---

## 6. 核心数据模型

建议定义以下核心模型。

### 6.1 `Document`

```python
@dataclass
class Document:
    source_path: Path
    source_text: str
    source_lang: str
    target_lang: str
    ast: Any
    metadata: dict
```

### 6.2 `Segment`

```python
@dataclass
class Segment:
    segment_id: str
    node_type: str
    source_text: str
    context_path: list[str]
    protected_spans: list["ProtectedSpan"]
    metadata: dict
```

说明：

- `segment_id` 必须稳定，便于回填和追踪
- `context_path` 表示所在章节路径，如 `["Getting Started", "Installation"]`
- `protected_spans` 用于标记不可翻译内容，例如 inline code、URL、占位符

### 6.3 `SegmentBundle`

```python
@dataclass
class SegmentBundle:
    bundle_id: str
    segments: list[Segment]
    summary_before: str
    summary_after: str
    glossary_terms: dict[str, str]
    style_instructions: list[str]
```

作用：

- 作为 Agent 的最小处理批次
- 避免只给模型局部句子，导致失去上下文

### 6.4 `TranslationResult`

```python
@dataclass
class TranslationResult:
    segment_id: str
    translated_text: str
    notes: list[str]
    applied_terms: dict[str, str]
    confidence: float
```

### 6.5 `ValidationReport`

```python
@dataclass
class ValidationReport:
    passed: bool
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, Any]
```

---

## 7. Agent 设计

## 7.1 Translator Agent

### 职责

- 在文档级上下文中翻译 `SegmentBundle`
- 保持术语一致
- 保留受保护片段
- 输出结构化结果

### 输入

- 源语言
- 目标语言
- segment 列表
- 上下文摘要
- 标题路径
- 术语表
- 风格要求

### 输出

- 每个 segment 的译文
- 使用了哪些术语映射
- 是否存在歧义或需要人工注意的点

### 约束

- 不得新增或删除 segment
- 不得修改受保护内容
- 不得输出解释性废话

## 7.2 Reviewer Agent

### 职责

- 修复上下文不连贯
- 统一术语和风格
- 纠正前后段落称呼不一致
- 检查标题和正文是否语义匹配

### 输入

- 原文 segment
- 初版译文
- 相邻上下文
- 术语表

### 输出

- 修订后的译文
- 修订原因

### 触发策略

- 默认启用
- 对超短文本可跳过
- 对长文档按章节执行

## 7.3 Format Guard Agent

### 职责

- 对文本层面格式异常做最小修复
- 发现潜在结构风险并上报

### 可修复范围

- 被意外翻译的 Markdown 控制符附近的文本
- 引号、强调符号、列表编号附近的轻微破坏
- 图片 alt/link title 文本中的误包裹

### 不可做的事

- 不得重写整段内容
- 不得改变标题层级
- 不得改 URL
- 不得改代码块内容

---

## 8. 保护机制设计

### 8.1 Protected Span

对每个 `Segment` 内部的不可翻译内容先做占位保护，再送入 Agent。

例如：

- `` `pip install xxx` `` -> `{{CODE_1}}`
- `[OpenAI](https://openai.com)` 的 URL -> `{{URL_1}}`
- HTML attribute -> `{{ATTR_1}}`

翻译完成后再恢复。

这样做的目的不是替代 AST，而是进一步降低模型误改概率。

### 8.2 结构级不可变约束

对翻译前后的 AST 执行结构比对。

允许变化：

- 文本节点内容

不允许变化：

- 节点类型
- 节点数量
- 标题层级
- 列表嵌套深度
- 链接 URL
- 代码块 fence 和 info string

只要发现非法变化，就直接判定当前输出失败并进入回退流程。

---

## 9. 分段策略

### 9.1 分段原则

分段目标不是“控制 token 长度”，而是在“语义完整”和“模型上下文成本”之间平衡。

推荐规则：

- 标题与紧随其后的第一段尽量进入同一个 bundle
- 列表项尽量保持同一列表内聚合
- 表格逐行处理，但保留表头上下文
- blockquote 整块优先不拆
- 超长段落按句群拆分，但必须保留前后摘要

### 9.2 Bundle 生成

每个 bundle 建议包含：

- 3 到 12 个 segment
- 同一章节下的相邻内容
- 总长度控制在模型稳定区间内

推荐实现：

- 小模型模式：2000 到 4000 字符
- 大模型模式：4000 到 12000 字符

---

## 10. 文档上下文设计

为解决“局部翻译语义不连贯”，必须显式维护文档级上下文。

建议构建 `DocumentContext`：

```python
@dataclass
class DocumentContext:
    title: str
    abstract: str
    section_summaries: dict[str, str]
    glossary: dict[str, str]
    style_guide: list[str]
    audience: str
```

上下文来源：

- front matter 标题和描述
- 一级、二级标题提取
- 文档开头摘要
- 项目级术语表
- 用户配置中的风格说明

这样 Translator Agent 翻译某一段时，不是只看到局部内容，而是知道它处于整篇文档的什么位置。

---

## 11. 配置设计

新配置应重写，不再沿用当前配置格式。

建议配置文件 `translator.yaml`：

```yaml
source_language: en
target_languages:
  - zh-CN

provider:
  name: openai
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: gpt-5-mini

pipeline:
  enable_review: true
  enable_format_guard: true
  enable_translation_memory: true
  fail_on_validation_error: true

segmentation:
  max_bundle_chars: 6000
  min_bundle_segments: 3
  max_bundle_segments: 12

style:
  tone: technical
  preserve_terms:
    - OpenAI
    - Markdown
    - Python
  audience: developers

output:
  file_suffix_template: "{stem}.{lang}.md"
  write_report: true
```

---

## 12. CLI 设计

建议重新设计命令行接口：

```bash
mdtx translate README.md --to zh-CN
mdtx translate docs/ --to zh-CN ja
mdtx validate README.zh-CN.md
mdtx glossary sync
mdtx report README.md --to zh-CN
```

### 12.1 `translate`

职责：

- 读取输入
- 跑完整流水线
- 输出目标文档与质量报告

### 12.2 `validate`

职责：

- 校验已有 Markdown 是否结构健康

### 12.3 `report`

职责：

- 只生成翻译和验证报告，不写正式输出

---

## 13. 失败处理与回退策略

### 13.1 Agent 调用失败

策略：

- 指数退避重试
- 达到上限后标记当前 bundle 失败
- 输出失败报告而非悄悄跳过

### 13.2 校验失败

策略：

1. 触发 Format Guard Agent 最小修复
2. 再次校验
3. 若仍失败，则本 bundle 回退到更细粒度翻译
4. 若仍失败，则终止该文件输出并生成错误报告

### 13.3 严格模式

建议默认开启严格模式：

- 只要结构校验失败，就不生成最终文件

这比输出一个格式损坏的 Markdown 更安全。

---

## 14. 并发策略

并发单位不再是“文件内随意多线程翻译字符串”，而是：

- 文件级并发
- bundle 级受控并发

建议策略：

- 同一文件内 bundle 保持章节顺序执行，便于上下文和术语记忆稳定
- 多文件之间可并发
- 若同一文件非常大，可按顶级章节并发，但章节内部顺序执行

---

## 15. 测试方案

本次重构必须引入系统化测试，否则新架构难以稳定。

### 15.1 单元测试

覆盖：

- Markdown 解析
- Segment 提取
- Protected span 替换与恢复
- AST 回填
- 结构 diff
- front matter 校验

### 15.2 集成测试

覆盖：

- Translator Agent 输入输出解析
- Reviewer Agent 修订链路
- Format Guard 修复链路
- 失败回退链路

### 15.3 端到端测试

准备一组 Markdown fixture：

- 普通段落
- 多级标题
- 嵌套列表
- 表格
- 图片和链接
- 引用块
- front matter
- HTML 混排
- 代码块和行内代码
- 含复杂强调和转义字符

验收标准：

- 输出可再次成功解析
- 结构 diff 通过
- 受保护内容不变
- 目标语言文本存在且覆盖率达标

---

## 16. 分阶段实施计划

本次虽然是破坏性重构，但仍建议分阶段实施，避免一次性重写后不可验证。

### 阶段 1：搭建新骨架

目标：

- 建立新目录结构
- 建立 CLI 骨架
- 接入新的配置体系
- 接入 `markdown-it-py`

产出：

- 能成功解析并渲染 Markdown
- 能输出 segment 列表

### 阶段 2：实现结构层

目标：

- 完成 AST -> Segment 提取
- 实现 protected span 保护
- 实现译文回填 AST

产出：

- 即使不调用模型，也能完成“提取 -> 写回 -> 重渲染”

### 阶段 3：实现 Translator Agent

目标：

- 实现 LLM 客户端
- 实现结构化翻译输出
- 实现 bundle 翻译

产出：

- 可以稳定翻译段落、标题、列表项

### 阶段 4：实现 Reviewer / Format Guard

目标：

- 实现审校修订链路
- 实现格式监督链路
- 实现失败回退

产出：

- 长文档的上下文一致性明显改善
- 结构错误能被拦截或修复

### 阶段 5：补齐验证与报告

目标：

- 完成各类 validator
- 输出机器可读和人类可读报告

产出：

- 可用于 CI 或批量翻译任务

### 阶段 6：清理旧代码

目标：

- 删除旧的按行节点解析和传统翻译器主路径
- 清理旧配置、旧说明文档、旧依赖

产出：

- 仓库只保留新架构

---

## 17. 破坏性重构范围

以下内容建议直接删除或废弃：

- 手写节点体系
- 基于正则的 Markdown 主解析逻辑
- 基于按行拼接的翻译回填逻辑
- “传统翻译器”和“LLM 翻译器”共用旧数据模型的做法
- 依赖 `splitlines()` 保持结构的流程

明确来说，以下旧模块不应继续作为核心保留对象：

- `Nodes.py`
- `MarkdownTranslator.py`
- `Translator.py`
- 现有 `llm_translator.py` 的字符串级翻译主逻辑
- 基于 `RawData.chunks` 的处理方式

它们最多只在过渡期存在，最终都应下线。

---

## 18. 第一批必须实现的类

建议优先实现以下类：

```python
class MarkdownParser:
    def parse(self, text: str) -> ParsedDocument: ...

class SegmentExtractor:
    def extract(self, doc: ParsedDocument) -> list[Segment]: ...

class ProtectedSpanProcessor:
    def protect(self, segment: Segment) -> Segment: ...
    def restore(self, translated_text: str, segment: Segment) -> str: ...

class TranslatorAgent:
    def translate_bundle(self, bundle: SegmentBundle, context: DocumentContext) -> list[TranslationResult]: ...

class ReviewerAgent:
    def review_bundle(self, bundle: SegmentBundle, translations: list[TranslationResult], context: DocumentContext) -> list[TranslationResult]: ...

class FormatGuardAgent:
    def repair_bundle(self, bundle: SegmentBundle, translations: list[TranslationResult]) -> list[TranslationResult]: ...

class AstMapper:
    def apply(self, doc: ParsedDocument, translations: list[TranslationResult]) -> ParsedDocument: ...

class MarkdownValidator:
    def validate(self, source_doc: ParsedDocument, output_text: str) -> ValidationReport: ...

class TranslationPipeline:
    def run(self, input_path: Path, target_lang: str) -> PipelineResult: ...
```

---

## 19. 验收标准

重构完成后，至少满足以下标准：

1. 对复杂 Markdown 文档可稳定解析和重渲染
2. 行内代码、代码块、URL、front matter 结构字段不被误翻译
3. 长段落和列表项在译文中保持上下文连贯
4. 标题、段落、表格、引用、图片 alt 文本都能正确翻译
5. 输出 Markdown 可被再次解析且结构一致
6. 当输出结构损坏时，系统能阻断输出并给出报告
7. 项目代码结构能支持后续增加新模型和新 Agent

---

## 20. 推荐实施顺序

如果只给一个最实际的执行顺序，我建议这样开始：

1. 先实现 `MarkdownParser + SegmentExtractor + Renderer`
2. 再实现 `ProtectedSpanProcessor + AstMapper`
3. 再实现 `TranslatorAgent`
4. 然后补 `MarkdownValidator`
5. 最后接入 `ReviewerAgent` 和 `FormatGuardAgent`

原因很简单：

- 结构层不稳，后面所有 Agent 都会建立在错误前提上
- 先把“结构正确”做成，再优化“语言质量”，整体风险最低

---

## 21. 结论

本项目的最佳重构方向不是继续增强旧的手写解析器，而是彻底切换为：

- AST 驱动的结构处理
- Segment 驱动的翻译单位
- 多 Agent 分工协作
- Validator 兜底的可靠输出

这是一种从“字符串处理工具”升级为“结构化文档翻译系统”的重构。

如果按本文档执行，项目会得到三个本质提升：

1. Markdown 复杂格式的稳定性
2. 译文的语义连贯性
3. 系统的可维护性和可扩展性

