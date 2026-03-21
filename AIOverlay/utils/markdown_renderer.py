# -*- coding: utf-8 -*-
"""
Markdown 渲染器模块
将 Markdown 文本转换为带样式的 HTML
"""
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension


def markdown_to_html(md_text: str) -> str:
    """
    将 Markdown 文本转换为 HTML
    
    Args:
        md_text: Markdown 格式的文本
        
    Returns:
        str: 转换后的 HTML 字符串
    """
    if not md_text:
        return ""
    
    # 配置 Markdown 扩展
    extensions = [
        FencedCodeExtension(),  # 支持 ```代码块```
        CodeHiliteExtension(    # 代码高亮
            linenums=False,
            guess_lang=True,
            css_class='highlight'
        ),
        TableExtension(),       # 支持表格
        'nl2br',               # 换行转 <br>
        'sane_lists',          # 更好的列表处理
    ]
    
    # 转换 Markdown 到 HTML
    html = markdown.markdown(
        md_text,
        extensions=extensions,
        output_format='html'
    )
    
    # 包装在带样式的 div 中
    styled_html = f"""
    <div class="markdown-content">
        {html}
    </div>
    """
    
    return styled_html


def get_markdown_css(font_color: str = "#333", font_size: int = 11, bg_color: str = "transparent", line_height: float = 1.5) -> str:
    """
    获取 Markdown 渲染的 CSS 样式
    """
    return f"""
    <style>
    .markdown-content {{
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: {font_size}px;
        line-height: {line_height};
        color: {font_color};
    }}
    
    .markdown-content h1, .markdown-content h2, .markdown-content h3 {{
        color: {font_color};
        margin-top: 12px;
        margin-bottom: 6px;
        font-weight: 600;
    }}
    
    .markdown-content h1 {{ font-size: {int(font_size * 1.3)}px; border-bottom: 2px solid {font_color}44; padding-bottom: 3px; }}
    .markdown-content h2 {{ font-size: {int(font_size * 1.2)}px; border-bottom: 1px solid {font_color}22; padding-bottom: 2px; }}
    .markdown-content h3 {{ font-size: {int(font_size * 1.1)}px; }}
    
    .markdown-content p {{
        margin: 6px 0;
    }}
    
    .markdown-content code {{
        background-color: rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 3px;
        padding: 1px 4px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: {max(9, font_size - 1)}px;
        color: #c7254e;
    }}
    
    .markdown-content pre {{
        background-color: rgba(0, 0, 0, 0.03);
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 4px;
        padding: 10px;
        overflow-x: auto;
        margin: 10px 0;
    }}
    
    .markdown-content pre code {{
        background: none;
        border: none;
        padding: 0;
        color: {font_color};
        font-size: {max(9, font_size - 1)}px;
        line-height: 1.4;
    }}
    
    .markdown-content ul, .markdown-content ol {{
        margin: 6px 0;
        padding-left: 22px;
    }}
    
    .markdown-content li {{
        margin: 3px 0;
    }}
    
    .markdown-content blockquote {{
        border-left: 4px solid {font_color}66;
        background-color: rgba(0, 0, 0, 0.02);
        padding: 6px 10px;
        margin: 10px 0;
        color: {font_color}BB;
    }}
    
    .markdown-content table {{
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
    }}
    
    .markdown-content th, .markdown-content td {{
        border: 1px solid rgba(0, 0, 0, 0.1);
        padding: 6px;
        text-align: left;
    }}
    
    .markdown-content th {{
        background-color: rgba(0, 0, 0, 0.04);
        font-weight: 600;
    }}
    
    .markdown-content strong {{
        font-weight: 600;
        color: {font_color};
    }}
    
    .markdown-content em {{
        font-style: italic;
        color: {font_color}CC;
    }}
    
    /* Pygments 代码高亮样式 - 尽量保持低对比度以免刺眼 */
    .markdown-content .highlight {{
        background: transparent;
    }}
    </style>
    """
