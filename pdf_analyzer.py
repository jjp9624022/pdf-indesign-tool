"""
PDF 版面分析工具
入口文件

用法:
    GUI 模式: python pdf_analyzer.py
    CLI 模式: python pdf_analyzer.py input.pdf --page 1 --mark
"""

import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='PDF 版面分析工具')
    parser.add_argument('input', nargs='?', help='输入 PDF 文件')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-p', '--page', type=int, default=1, help='处理的页面（从1开始）')
    parser.add_argument('--mark', action='store_true', help='生成带标记框的 PDF')
    parser.add_argument('--dpi', type=int, default=150, help='渲染 DPI')
    
    args = parser.parse_args()
    
    if args.input:
        # CLI 模式
        from pdf_analyzer.utils import cli_process
        cli_process(args)
    else:
        # GUI 模式
        from pdf_analyzer import PDFAnalyzerApp
        app = PDFAnalyzerApp()
        app.mainloop()


if __name__ == "__main__":
    main()
