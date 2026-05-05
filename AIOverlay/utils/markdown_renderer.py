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


def get_markdown_css(font_color: str = "#333", font_size: int = 11, bg_color: str = "transparent", line_height: float = 1.5, text_opacity: float = 1.0) -> str:
    """
    获取 Markdown 渲染的 CSS 样式
    """
    def get_color(base_color, base_opacity, alpha_mult=1.0):
        color = base_color.lstrip('#')
        if len(color) == 3:
            color = ''.join(c + c for c in color)
        if len(color) == 6:
            r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, {base_opacity * alpha_mult:.3f})"
        return base_color

    main_color = get_color(font_color, text_opacity, 1.0)
    border_color_strong = get_color(font_color, text_opacity, 0.27) # 原 44
    border_color_weak = get_color(font_color, text_opacity, 0.13)   # 原 22
    quote_border = get_color(font_color, text_opacity, 0.4)         # 原 66
    quote_text = get_color(font_color, text_opacity, 0.73)          # 原 BB
    em_text = get_color(font_color, text_opacity, 0.8)              # 原 CC

    return f"""
    <style>
    .markdown-content {{
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: {font_size}px;
        line-height: {line_height};
        color: {main_color};
    }}
    
    .markdown-content h1, .markdown-content h2, .markdown-content h3 {{
        color: {main_color};
        margin-top: 12px;
        margin-bottom: 6px;
        font-weight: 600;
    }}
    
    .markdown-content h1 {{ font-size: {int(font_size * 1.3)}px; padding-bottom: 3px; }}
    .markdown-content h2 {{ font-size: {int(font_size * 1.2)}px; padding-bottom: 2px; }}
    .markdown-content h3 {{ font-size: {int(font_size * 1.1)}px; }}
    
    .markdown-content p {{
        margin: 6px 0;
    }}
    
    .markdown-content code {{
        background: transparent;
        border: none;
        padding: 0 2px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: {max(9, font_size - 1)}px;
        color: {main_color};
    }}
    
    .markdown-content pre {{
        background: transparent;
        border: none;
        padding: 4px 0;
        margin: 6px 0;
        white-space: pre-wrap;       /* 强制代码自动换行 */
        word-wrap: break-word;       /* 允许超长字符串截断换行 */
    }}
    
    .markdown-content pre code {{
        background: none;
        border: none;
        padding: 0;
        color: {main_color};
        font-size: {max(9, font_size - 1)}px;
        line-height: 1.4;
        white-space: pre-wrap;
    }}
    
    .markdown-content ul, .markdown-content ol {{
        margin: 6px 0;
        padding-left: 22px;
    }}
    
    .markdown-content li {{
        margin: 3px 0;
    }}
    
    .markdown-content blockquote {{
        border: none;
        background: transparent;
        padding: 6px 10px;
        margin: 10px 0;
        color: {quote_text};
    }}
    
    .markdown-content table {{
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
        border: none;
    }}
    
    .markdown-content th, .markdown-content td {{
        border: none;
        padding: 6px;
        text-align: left;
    }}
    
    .markdown-content th {{
        background: transparent;
        font-weight: 600;
    }}
    
    .markdown-content strong {{
        font-weight: 600;
        color: {main_color};
    }}
    
    .markdown-content em {{
        font-style: italic;
        color: {em_text};
    }}
    
    /* Pygments 代码高亮样式 - 尽量保持低对比度以免刺眼 */
    .markdown-content .highlight {{
        background: transparent;
    }}
    </style>
    """
