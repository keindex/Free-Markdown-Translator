![Free-Markdown-Translator](https://socialify.git.ci/CrazyMayfly/Free-Markdown-Translator/image?custom_description=Free+Markdown+Translator%E6%98%AF%E4%B8%80%E6%AC%BE%E5%9F%BA%E4%BA%8E+AI+Agent+%E6%B5%81%E6%B0%B4%E7%BA%BF%E7%9A%84+Markdown+%E6%96%87%E6%A1%A3%E7%BF%BB%E8%AF%91%E5%99%A8&description=1&font=Bitter&forks=1&language=1&name=1&owner=1&pattern=Solid&stargazers=1&theme=Auto)

[English](doc/README.en.md) | [繁體中文](doc/README.zh-tw.md) | [Deutsch](doc/README.de.md) | [日本語](doc/README.ja.md) | [русский](doc/README.ru.md) | [한국어](doc/README.ko.md) | [Português](doc/README.pt.md) | [Español](doc/README.es.md) | [Français](doc/README.fr.md) | [हिन्दी](doc/README.hi.md)

## 简介

Free Markdown Translator 现在是一套基于 Agent 的 Markdown 翻译流水线，而不是旧的“手写解析器 + 按行拼接”工具。

当前核心能力：

- 使用 `markdown-it-py` 解析 Markdown AST
- 使用 `Segment` 做语义分段翻译
- 使用 `TranslatorAgent / ReviewerAgent / FormatGuardAgent` 分离翻译、审校、格式监督职责
- 使用 `MarkdownValidator` 做 front matter 和结构校验
- 支持 OpenAI 兼容接口
- 支持报告输出和测试

## 安装

```bash
pip install -r requirements.txt
```

## 运行

配置文件使用 [config.yaml](/D:/codes/PythonProjects/Free-Markdown-Translator/src/config.yaml)。

```yaml
# 目标语言列表。支持一次翻译到多个语言。
target_languages:
  - zh-CN

# 大模型服务配置。兼容 OpenAI 风格接口。
provider:
  name: openai
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  # 二选一：优先读取 api_key，其次读取 api_key_env 指向的环境变量。
  api_key:
  api_key_env: DASHSCOPE_API_KEY
  model: qwen3.5-flash
  temperature: 0.2
  max_tokens: 4000

# 翻译流程控制。
pipeline:
  mode: balanced
  enable_review: false
  enable_format_guard: false
  fail_on_validation_error: true

# 分段策略。用于控制单次提交给模型的文本规模。
segmentation:
  max_bundle_chars: 6000
  max_bundle_segments: 12

# 术语和文风提示，会注入给翻译 Agent。
style:
  tone: technical
  audience: developers
  preserve_terms:
    - Markdown
    - OpenAI
    - Python
  instructions:
    - Keep protected placeholders unchanged.
    - Do not alter Markdown control syntax.

# 输出文件和报告设置。
output:
  file_suffix_template: "{stem}.{lang}.md"
  write_report: true

# 可选术语表路径。文件不存在时会自动忽略。
glossary_path:

# 并行执行设置。
execution:
  max_parallel_translations: 4
```

说明：

- `provider.api_key`：直接填写真实 API Key
- `provider.api_key_env`：可选，填写环境变量名
- 如果 `provider.api_key` 已填写，就不再需要环境变量
- 源语言不再配置，由模型自动识别
- `pipeline.mode` 支持 `fast`、`balanced`、`strict`
- `segmentation.max_bundle_chars` 和 `segmentation.max_bundle_segments` 用来控制分段大小
- `style` 用来约束语气、受众和术语保留
- `output.write_report` 控制是否生成 `*.report.json`
- `glossary_path` 可指向 YAML 术语表文件
- `execution.max_parallel_translations` 控制多目标语言/多文件翻译时的最大并行任务数，默认 `1`
- 默认推荐 `balanced`：只常驻 `TranslatorAgent`，`ReviewerAgent` 和 `FormatGuardAgent` 按需触发
- 普通日志会记录模型调用的阶段、模型名、耗时和输入输出大小；并行翻译时会自动带上任务标识
- `--verbose` 会额外输出模型完整输入和原始输出，便于排查 prompt/response 问题

命令示例：

```bash
python src/cli/main.py translate README.md --to zh-CN
python src/cli/main.py validate README.md
python src/cli/main.py report README.md --to zh-CN
python src/cli/main.py --verbose translate README.md
```

## 测试

测试代码位于 [src/test](/D:/codes/PythonProjects/Free-Markdown-Translator/src/test)。

运行：

```bash
python -m unittest discover -s src/test
```

## 项目结构

```text
src/
  cli/
  core/
  parser/
  agents/
  llm/
  memory/
  validators/
  test/
```
