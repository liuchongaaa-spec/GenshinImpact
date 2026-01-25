# -*- coding: utf-8 -*-
"""
AI服务模块 - 封装所有与Gemini AI的交互
"""
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, SYSTEM_PROMPT


class AIService:
    """Gemini AI服务封装"""
    
    def __init__(self):
        """初始化AI客户端"""
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat_flash = None
        
        # 对话历史
        self.flash_history = []
        
        # 初始化历史
        self._init_history()
        
    def _init_history(self):
        """初始化对话历史"""
        initial_history = [
            types.Content(role="user", parts=[types.Part.from_text(text="你好")]),
            types.Content(role="model", parts=[types.Part.from_text(text="你好！我是您的AI助手。")])
        ]
        self.flash_history = list(initial_history)
        
    def create_flash_session(self, model_id: str) -> bool:
        """
        创建Flash模型会话
        
        Args:
            model_id: 模型ID
            
        Returns:
            bool: 是否成功
        """
        try:
            self.chat_flash = self.client.chats.create(
                model=model_id,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
                history=self.flash_history
            )
            return True
        except Exception as e:
            print(f"Flash会话创建失败: {e}")
            return False
            
    def send_to_flash_stream(self, content):
        """
        向Flash模型发送消息并获取流式响应
        
        Args:
            content: 消息内容 (可以是字符串或列表)
            
        Yields:
            str: 响应的每个chunk
        """
        if self.chat_flash is None:
            raise ValueError("Flash session not initialized")
            
        response_stream = self.chat_flash.send_message_stream(content)
        full_text = ""
        
        for chunk in response_stream:
            if chunk.text:
                full_text += chunk.text
                yield chunk.text
                
        # 更新历史
        if isinstance(content, str):
            self.flash_history.append(
                types.Content(role="user", parts=[types.Part.from_text(text=content)])
            )
        else:
            self.flash_history.append(types.Content(role="user", parts=content))
            
        self.flash_history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=full_text)])
        )
        
    @staticmethod
    def create_text_part(text: str):
        """创建文本Part"""
        return types.Part.from_text(text=text)
        
    @staticmethod
    def create_audio_part(audio_bytes: bytes, mime_type: str = "audio/wav"):
        """创建音频Part"""
        return types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        
    @staticmethod
    def create_image_part(image_bytes: bytes, mime_type: str = "image/jpeg"):
        """创建图片Part"""
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    
    @staticmethod
    def test_connection(api_key: str) -> None:
        """
        测试 AI 服务连接
        
        Args:
            api_key: API Key
            
        Raises:
            InitializationError: 连接失败时抛出
        """
        from AIOverlay.utils.exceptions import InitializationError
        
        try:
            client = genai.Client(api_key=api_key)
            # 使用 models.list() 测试连接，不消耗配额
            models = list(client.models.list())
            # 如果能获取到模型列表，说明连接成功
            if models:
                return
        except Exception as e:
            error_msg = str(e)
            # 429 表示配额用完，但 API Key 是有效的
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                return  # API Key 有效，只是配额用完了
            elif "API key not valid" in error_msg or "invalid" in error_msg.lower():
                raise InitializationError("API Key 无效，请检查配置")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                raise InitializationError("网络连接失败，请检查网络")
            else:
                raise InitializationError(f"AI 服务连接失败: {error_msg}")

