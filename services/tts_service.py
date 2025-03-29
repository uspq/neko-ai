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
        self.api_key = config.get("tts.fish_api_key", "")
        if not self.api_key:
            logger.error("未配置Fish Audio API密钥")
            self.enabled = False
            return
            
        # API配置
        self.base_url = "https://api.fish.audio/v1/tts"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 添加模型选择
        self.model = config.get("tts.model", "speech-1.6")  # 默认使用 speech-1.6 模型
        if self.model:
            self.headers["model"] = self.model
            logger.info(f"使用Fish Audio TTS模型: {self.model}")
        
        # 获取开发者ID（如果有）
        self.developer_id = config.get("tts.developer_id", "")
        if self.developer_id:
            self.headers["developer-id"] = self.developer_id
            logger.info(f"已设置Fish Audio开发者ID: {self.developer_id}")
        
        # 获取配置
        self.reference_id = config.get("tts.fish_reference_id", "")
        if not self.reference_id:
            logger.warning("未配置Fish Audio参考音色ID，将使用默认音色")
        else:
            logger.info(f"使用参考音色ID: {self.reference_id}")
        
        # 语音设置
        self.voice_settings = {
            "format": "mp3",
            "mp3_bitrate": 128,
            "chunk_length": 200,
            "normalize": True,
            "latency": "normal"
        }
        
        # 其他设置
        self.speed = config.get("tts.speed", 1.0)
        self.volume = config.get("tts.volume", 1.0)
        self.pitch = config.get("tts.pitch", 0.0)
        
        logger.info("TTS服务初始化成功（Fish Audio）")
    
    def _prepare_request_data(
        self,
        text: str,
        reference_id: Optional[str] = None,
        speed: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None
    ) -> Dict[str, Any]:
        """准备请求数据"""
        # 基本数据
        data = {
            "text": text,
            "format": "mp3",
            "mp3_bitrate": 128,
            "chunk_length": 200,
            "normalize": True,
            "latency": "normal"
        }
        
        # 添加参考音色ID
        ref_id = reference_id if reference_id else self.reference_id
        if ref_id:
            data["reference_id"] = ref_id
        
        return data
    
    def generate_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        speed: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None,
        output_path: Optional[str] = None
    ) -> bytes:
        """
        生成语音
        
        Args:
            text: 要转换的文本
            reference_id: 参考音色ID，不指定则使用默认值
            speed: 语速 (0.5-2.0)
            volume: 音量 (0.1-2.0)
            pitch: 音高 (-12.0-12.0)
            output_path: 输出文件路径，不指定则返回字节数据
            
        Returns:
            bytes: 音频数据
        """
        if not self.enabled:
            raise RuntimeError("TTS服务未启用")
            
        try:
            # 准备请求数据
            data = self._prepare_request_data(
                text=text, 
                reference_id=reference_id
            )
            
            url = self.base_url
            
            logger.info(f"正在调用Fish Audio API，URL: {url}")
            logger.info(f"请求数据: {data}")
            logger.info(f"请求头: {self.headers}")
            
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
        reference_id: Optional[str] = None,
        speed: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None
    ) -> Generator[bytes, None, None]:
        """
        流式生成语音
        
        Args:
            text: 要转换的文本
            reference_id: 参考音色ID，不指定则使用默认值
            speed: 语速 (0.5-2.0)
            volume: 音量 (0.1-2.0)
            pitch: 音高 (-12.0-12.0)
            
        Returns:
            generator: 音频数据生成器
        """
        if not self.enabled:
            raise RuntimeError("TTS服务未启用")
            
        try:
            # 准备请求数据
            data = self._prepare_request_data(
                text=text, 
                reference_id=reference_id
            )
            
            url = self.base_url
            
            logger.info(f"正在调用Fish Audio API，URL: {url}")
            logger.info(f"请求数据: {data}")
            logger.info(f"请求头: {self.headers}")
            
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