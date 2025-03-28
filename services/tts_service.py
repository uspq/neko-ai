import os
import requests
from typing import Optional, Generator, Dict, Any
from core.config import config
from utils.logger import get_logger

logger = get_logger("tts")

class TTSService:
    """文本转语音服务类"""
    
    def __init__(self):
        """初始化TTS服务"""
        self.enabled = config.get("tts.enabled", False)
        if not self.enabled:
            logger.warning("TTS服务未启用")
            return
            
        # 设置API密钥
        self.api_key = config.get("tts.api_key", "")
        if not self.api_key:
            logger.error("未配置ElevenLabs API密钥")
            self.enabled = False
            return
            
        # API配置
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json"
        }
        
        # 获取配置
        self.model_id = config.get("tts.model_id", "eleven_multilingual_v2")
        self.voice_id = config.get("tts.voice_id", "21m00Tcm4TlvDq8ikWAM")
        
        # 语音设置
        self.voice_settings = {
            "stability": config.get("tts.stability", 0.5),
            "similarity_boost": config.get("tts.similarity_boost", 0.75),
            "style": config.get("tts.style", 0.0),
            "use_speaker_boost": config.get("tts.use_speaker_boost", True)
        }
        
        logger.info("TTS服务初始化成功")
    
    def _prepare_request_data(
        self,
        text: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """准备请求数据"""
        return {
            "text": text,
            "model_id": model_id or self.model_id,
            "voice_settings": self.voice_settings
        }
    
    def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> bytes:
        """
        生成语音
        
        Args:
            text: 要转换的文本
            voice_id: 语音ID，不指定则使用默认值
            model_id: 模型ID，不指定则使用默认值
            output_path: 输出文件路径，不指定则返回字节数据
            
        Returns:
            bytes: 音频数据
        """
        if not self.enabled:
            raise RuntimeError("TTS服务未启用")
            
        try:
            # 使用默认voice_id如果没有提供或提供的是None或空字符串
            voice_id = voice_id if voice_id else self.voice_id
            
            # 准备请求数据
            data = self._prepare_request_data(text, model_id)
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            
            logger.info(f"正在调用ElevenLabs API，URL: {url}")
            logger.info(f"请求数据: {data}")
            
            # 发送请求
            response = requests.post(url, json=data, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            # 获取音频数据
            audio = response.content
            
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio)
                logger.info(f"语音已保存到: {output_path}")
                
            return audio
            
        except Exception as e:
            logger.error(f"生成语音失败: {str(e)}")
            raise
    
    def stream_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Generator[bytes, None, None]:
        """
        流式生成语音
        
        Args:
            text: 要转换的文本
            voice_id: 语音ID，不指定则使用默认值
            model_id: 模型ID，不指定则使用默认值
            
        Returns:
            generator: 音频数据生成器
        """
        if not self.enabled:
            raise RuntimeError("TTS服务未启用")
            
        try:
            # 使用默认voice_id如果没有提供或提供的是None或空字符串
            voice_id = voice_id if voice_id else self.voice_id
            
            # 准备请求数据
            data = self._prepare_request_data(text, model_id)
            url = f"{self.base_url}/text-to-speech/{voice_id}/stream"
            
            logger.info(f"正在调用ElevenLabs流式API，URL: {url}")
            logger.info(f"请求数据: {data}")
            
            # 发送请求并获取流式响应
            response = requests.post(url, json=data, headers=self.headers, stream=True)
            
            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            # 返回数据流
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
                    
        except Exception as e:
            logger.error(f"流式生成语音失败: {str(e)}")
            raise

# 创建全局TTS服务实例
tts_service = TTSService() 