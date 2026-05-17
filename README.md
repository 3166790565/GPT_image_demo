# GPT 文生图

基于 OpenAI GPT-Image 系列模型的文字生成图片工具，支持命令行（CLI）和图形界面（GUI）两种使用方式。

## 功能特性

- **多模型支持**：`gpt-image-2` / `gpt-image-1` / `gpt-image-1-mini` / `dall-e-3`
- **双界面**：命令行脚本 + Tkinter 图形界面
- **丰富参数**：尺寸、质量、数量、推理模式、背景控制、随机种子等
- **代理中转**：支持自定义 Base URL，方便使用中转 API
- **双输出格式**：Base64 直接保存 / URL 下载
- **实时预览**（GUI）：生成后自动展示缩略图
- **进度反馈**（GUI）：进度条 + 运行日志

## 环境要求

- Python >= 3.9
- 依赖库：

```bash
pip install openai pillow requests
```

## 快速开始

### 1. 设置 API Key

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 或写入 .env 文件（需自行创建）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. 命令行使用

```bash
# 使用默认提示词生成图片
python gpt_image_2.py

# 自定义提示词
python gpt_image_2.py "一只柴犬在樱花树下奔跑，动漫风格"

# 高级参数
python gpt_image_2.py "一只橘猫坐在窗台上晒太阳，水彩画风格" \
    -s 1024x1536 -n 2 -q high -t medium --bg transparent --seed 42
```

### 3. 图形界面使用

```bash
python gpt_image_2_gui.py
```

## 参数说明

### 命令行参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `prompt` | 默认提示词 | 图像描述文本（位置参数） |
| `-m` / `--model` | `gpt-image-2` | 模型名称 |
| `-s` / `--size` | `1024x1024` | 图像尺寸 |
| `-q` / `--quality` | `high` | 质量：`standard` / `high` |
| `-n` / `--count` | `1` | 生成数量（1-10） |
| `-t` / `--thinking` | 无 | 推理模式：`off` / `low` / `medium` / `high` |
| `-f` / `--format` | `b64_json` | 输出格式：`b64_json` / `url` |
| `--bg` / `--background` | 无 | 背景模式：`auto` / `transparent` / `opaque` |
| `--seed` | 随机 | 随机种子（int32） |
| `--api-key` | 环境变量 | OpenAI API Key |
| `--base-url` | 无 | 自定义中转地址 |
| `-o` / `--output` | `./output` | 输出目录 |
| `--prefix` | `gpt-image` | 文件名前缀 |

### 支持尺寸

- `1024x1024`
- `1024x1536`（竖版）
- `1536x1024`（横版）
- `1536x1536`
- `2000x2000`
- `2000x667`（宽幅）
- `667x2000`（长幅）

## 项目结构

```
GPT文生图/
├── gpt_image_2.py          # 命令行版本
├── gpt_image_2_gui.py      # 图形界面版本
├── output/                  # 图片输出目录（git 忽略）
└── README.md               # 本文件
```

## 注意事项

- API Key 请妥善保管，不要提交到版本控制。推荐使用环境变量或 `.env` 文件存放。
- `gpt-image-2` 模型需要 OpenAI 账户有对应的 API 访问权限。
- 使用中转 API 时，通过 `--base-url` 或 GUI 中的 Base URL 字段配置中转地址。
- 生成图片默认保存在 `./output/` 目录。
