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


def get_markdown_css() -> str:
    """
    获取 Markdown 渲染的 CSS 样式
    
    Returns:
        str: CSS 样式字符串
    """
    return """
    <style>
    .markdown-content {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 11px;
        line-height: 1.5;
        color: #333;
    }
    
    .markdown-content h1, .markdown-content h2, .markdown-content h3 {
        color: #2c3e50;
        margin-top: 10px;
        margin-bottom: 5px;
        font-weight: 600;
    }
    
    .markdown-content h1 { font-size: 14px; border-bottom: 2px solid #3498db; padding-bottom: 3px; }
    .markdown-content h2 { font-size: 13px; border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; }
    .markdown-content h3 { font-size: 12px; }
    
    .markdown-content p {
        margin: 5px 0;
    }
    
    .markdown-content code {
        background-color: #f4f4f4;
        border: 1px solid #ddd;
        border-radius: 3px;
        padding: 1px 4px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 11px;
        color: #c7254e;
    }
    
    .markdown-content pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 8px;
        overflow-x: auto;
        margin: 8px 0;
    }
    
    .markdown-content pre code {
        background: none;
        border: none;
        padding: 0;
        color: #333;
        font-size: 11px;
        line-height: 1.4;
    }
    
    .markdown-content ul, .markdown-content ol {
        margin: 5px 0;
        padding-left: 20px;
    }
    
    .markdown-content li {
        margin: 2px 0;
    }
    
    .markdown-content blockquote {
        border-left: 3px solid #3498db;
        background-color: #f0f7fb;
        padding: 5px 8px;
        margin: 8px 0;
        color: #555;
    }
    
    .markdown-content table {
        border-collapse: collapse;
        width: 100%;
        margin: 8px 0;
    }
    
    .markdown-content th, .markdown-content td {
        border: 1px solid #ddd;
        padding: 5px;
        text-align: left;
    }
    
    .markdown-content th {
        background-color: #f2f2f2;
        font-weight: 600;
    }
    
    .markdown-content strong {
        font-weight: 600;
        color: #2c3e50;
    }
    
    .markdown-content em {
        font-style: italic;
        color: #555;
    }
    
    /* Pygments 代码高亮样式 */
    .markdown-content .highlight {
        background: #f8f8f8;
    }
    
    .markdown-content .highlight .k { color: #0000ff; font-weight: bold; }  /* Keyword */
    .markdown-content .highlight .s { color: #a31515; }  /* String */
    .markdown-content .highlight .c { color: #008000; font-style: italic; }  /* Comment */
    .markdown-content .highlight .n { color: #000000; }  /* Name */
    .markdown-content .highlight .o { color: #000000; }  /* Operator */
    .markdown-content .highlight .m { color: #09885a; }  /* Number */
    </style>
    """
