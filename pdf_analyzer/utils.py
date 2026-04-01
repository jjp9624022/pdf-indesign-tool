"""
CLI 工具函数
"""

import os
import tempfile
import json
import fitz
from PIL import Image


def merge_regions(regions, h_gap=25, v_gap=15):
    """
    合并相邻的小区域
    h_gap: 水平间距阈值
    v_gap: 垂直间距阈值
    """
    if not regions:
        return regions
    
    regions = sorted(regions, key=lambda r: (r['y1'], r['x1']))
    
    i = 0
    while i < len(regions):
        j = i + 1
        while j < len(regions):
            r1, r2 = regions[i], regions[j]
            
            y_overlap = max(0, min(r1['y2'], r2['y2']) - max(r1['y1'], r2['y1']))
            x_overlap = max(0, min(r1['x2'], r2['x2']) - max(r1['x1'], r2['x1']))
            merged = False
            
            # 水平合并
            if y_overlap > 0:
                gap = r2['x1'] - r1['x2'] if r2['x1'] > r1['x2'] else r1['x1'] - r2['x2']
                if gap <= h_gap:
                    regions[i] = {
                        'x1': min(r1['x1'], r2['x1']),
                        'y1': min(r1['y1'], r2['y1']),
                        'x2': max(r1['x2'], r2['x2']),
                        'y2': max(r1['y2'], r2['y2']),
                        'content': r1['content'] + r2['content'],
                        'score': (r1['score'] + r2['score']) / 2,
                        'type': 'text'
                    }
                    regions.pop(j)
                    merged = True
            
            # 垂直合并
            if not merged and x_overlap > 0:
                gap = r2['y1'] - r1['y2'] if r2['y1'] > r1['y2'] else r1['y1'] - r2['y2']
                if gap <= v_gap:
                    regions[i] = {
                        'x1': min(r1['x1'], r2['x1']),
                        'y1': min(r1['y1'], r2['y1']),
                        'x2': max(r1['x2'], r2['x2']),
                        'y2': max(r1['y2'], r2['y2']),
                        'content': r1['content'] + '\r' + r2['content'],
                        'score': (r1['score'] + r2['score']) / 2,
                        'type': 'text'
                    }
                    regions.pop(j)
            
            if not merged:
                j += 1
        i += 1
    
    return regions


def cli_process(args):
    """CLI 模式处理"""
    print(f"处理: {args.input}")
    print(f"页面: {args.page}")
    print("使用 RapidOCR 进行版面分析")
    
    # 打开 PDF
    doc = fitz.open(args.input)
    total_pages = len(doc)
    print(f"PDF 总页数: {total_pages}")
    
    # 渲染页面
    page_idx = args.page - 1
    if page_idx >= total_pages:
        print(f"错误: 页面 {args.page} 超出范围 (1-{total_pages})")
        return
    
    page = doc[page_idx]
    dpi = args.dpi
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat)
    
    page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    print(f"页面尺寸: {page_img.width}x{page_img.height} @ {dpi} DPI")
    
    # 保存临时图片
    temp_path = os.path.join(tempfile.gettempdir(), 'pdf_analyzer_cli.png')
    page_img.save(temp_path)
    
    # RapidOCR 分析
    print("正在分析版面...")
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    result, elapse = ocr_engine(temp_path)
    
    # 转换结果
    regions = []
    if result:
        for item in result:
            box = item[0]
            text = item[1]
            score = item[2]
            
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            
            regions.append({
                "x1": int(min(xs)), "y1": int(min(ys)),
                "x2": int(max(xs)), "y2": int(max(ys)),
                "content": text.replace('\n', '\r'),
                "score": float(score), "type": "text"
            })
    
    print(f"检测到 {len(regions)} 个原始文字区域 (耗时: {sum(elapse):.2f}s)")
    
    # 合并
    regions = merge_regions(regions, h_gap=25, v_gap=15)
    print(f"合并后: {len(regions)} 个文字区域")
    
    # 生成带标记框的 PDF
    if args.mark:
        output_dir = args.output or os.path.dirname(args.input) or '.'
        import time
        timestamp = time.strftime("%H%M%S")
        output_pdf = os.path.join(output_dir, f"marked_p{args.page}_{timestamp}.pdf")
        
        print(f"生成带标记 PDF: {output_pdf}")
        
        out_doc = fitz.open()
        out_page = out_doc.new_page(width=pix.width, height=pix.height)
        
        temp_img_path = os.path.join(tempfile.gettempdir(), 'pdf_mark_img.png')
        page_img.save(temp_img_path)
        out_page.insert_image(out_page.rect, filename=temp_img_path)
        
        for i, region in enumerate(regions):
            x1, y1, x2, y2 = region.get('x1', 0), region.get('y1', 0), region.get('x2', 0), region.get('y2', 0)
            rect = fitz.Rect(x1, y1, x2, y2)
            out_page.draw_rect(rect, color=(0, 1, 1), width=3)
            out_page.insert_text((x1 + 5, y1 + 15), f"[{i+1}]", fontsize=12, color=(1, 1, 0), fontname="helv")
        
        out_doc.save(output_pdf)
        out_doc.close()
        print(f"✓ 已保存: {output_pdf}")
    
    # 保存结果
    output_dir = args.output or os.path.dirname(args.input) or '.'
    result_file = os.path.join(output_dir, f"result_p{args.page}.json")
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'input': args.input,
            'page': args.page,
            'method': 'RapidOCR',
            'regions': regions,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 结果已保存: {result_file}")
    
    # 输出文字
    print("\n识别内容:")
    print("-" * 50)
    for i, region in enumerate(regions):
        content = region.get('content', '')
        if content:
            print(f"[{i+1}] ({region.get('score', 0):.2f}) {content[:80]}...")
    print("-" * 50)
    
    doc.close()
