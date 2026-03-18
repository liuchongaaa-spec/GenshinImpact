# -*- coding: utf-8 -*-
"""
AI服务模块 - 封装所有与Gemini AI的交互
"""
from google import genai
from google.genai import types
from AIOverlay.config import GEMINI_API_KEY, SYSTEM_PROMPT, MODEL_ID


class AIService:
    """Gemini AI服务封装"""

    def __init__(self):
        """初始化AI客户端"""
        import os
        from AIOverlay.config import PROXY_URL
        
        # 使用环境变量设置代理 (httpx 会自动识别)
        if PROXY_URL:
            os.environ['HTTP_PROXY'] = PROXY_URL
            os.environ['HTTPS_PROXY'] = PROXY_URL
            print(f"📡 已设置网络代理: {PROXY_URL}")

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat = None
        self.history = []
        self._init_history()

    def _init_history(self):
        """初始化对话历史"""
        self.history = [
            types.Content(role="user", parts=[types.Part.from_text(text="你好")]),
            types.Content(role="model", parts=[types.Part.from_text(text="你好！我是您的AI助手。")])
        ]

    def create_session(self) -> bool:
        """
        创建模型会话
        
        Returns:
            bool: 是否成功
        """
        try:
            self.chat = self.client.chats.create(
                model=MODEL_ID,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
                history=self.history
            )
            return True
        except Exception as e:
            print(f"会话创建失败: {e}")
            return False

    def send_stream(self, content):
        """
        向模型发送消息并获取流式响应 (带重试逻辑)
        
        Args:
            content: 消息内容
            
        Yields:
            str: 响应的每个chunk
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if self.chat is None:
                    print("Session missing, creating...")
                    self.create_session()

                response_stream = self.chat.send_message_stream(content)
                full_text = ""

                for chunk in response_stream:
                    if chunk.text:
                        full_text += chunk.text
                        yield chunk.text

                # 只有成功完成后才记录历史
                self._update_history(content, full_text)
                return  # 成功退出

            except Exception as e:
                error_msg = str(e).lower()
                print(f"AI Stream Error (Attempt {attempt+1}): {e}")
                
                # 如果是连接中断或会话过期，尝试重新创建会话并重试
                if "disconnect" in error_msg or "eof" in error_msg or "session" in error_msg or attempt == 0:
                    print("🔄 连接中断，尝试重建会话并重试...")
                    self.create_session()
                    continue
                else:
                    raise e

    def _update_history(self, content, full_text):
        """更新对话历史"""
        if isinstance(content, str):
            self.history.append(
                types.Content(role="user", parts=[types.Part.from_text(text=content)])
            )
        else:
            self.history.append(types.Content(role="user", parts=content))

        self.history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=full_text)])
        )

    @staticmethod
    def create_text_part(text: str):
        """创建文本Part"""
        return types.Part.from_text(text=text)

    @staticmethod
    def create_image_part(image_bytes: bytes, mime_type: str = "image/jpeg"):
        """创建图片Part"""
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    @staticmethod
    def test_connection(api_key: str) -> None:
        """
        测试 AI 服务连接
        """
        import os
        from AIOverlay.config import PROXY_URL
        from AIOverlay.utils.exceptions import InitializationError

        # 确保测试连接也走代理
        if PROXY_URL:
            os.environ['HTTP_PROXY'] = PROXY_URL
            os.environ['HTTPS_PROXY'] = PROXY_URL

        try:
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
            if models:
                return
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                return
            elif "API key not valid" in error_msg or "invalid" in error_msg.lower():
                raise InitializationError("API Key 无效，请检查配置")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                raise InitializationError("网络连接失败，请检查网络")
            else:
                raise InitializationError(f"AI 服务连接失败: {error_msg}")
