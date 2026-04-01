# PDF-InDesign 文字替换工具

PDF 版面分析 + InDesign 文字替换工作流工具。

## 功能

- **PDF 文字区域标注** — 手动绘制或自动检测文字区域
- **OCR 识别** — 支持多供应商多模型（SiliconFlow、豆包等）
- **InDesign 集成** — 在 InDesign 中搜索/替换文本
- **供应商管理** — 通过 UI 动态添加/移除 AI 供应商和模型
- **批量处理** — 支持多页批量 OCR

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python pdf_analyzer.py
```

## 配置

首次运行会自动生成 `config.json`。通过 UI 的 **⚙️** 按钮管理供应商和模型：

- 添加新供应商（ID、名称、API Key、Base URL）
- 为供应商添加/移除模型
- 编辑供应商的 API Key 和 Base URL

## 供应商配置示例

参考 `config.example.json`。

## 依赖

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 渲染
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — UI 框架
- [Pillow](https://pillow.readthedocs.io/) — 图像处理
- [rapidocr-onnxruntime](https://github.com/RapidAI/RapidOCR) — 本地 OCR（自动检测）

## 打包 EXE

```bash
pip install pyinstaller
pyinstaller build.spec
```

打包完成后在 `dist/` 目录下找到 `PDF-InDesign-Tool.exe`。

## 许可证

MIT
