import os
import requests
import json
import time
from typing import Optional, Generator, Dict, Any, Tuple, List
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
        self.api_base_url = "https://api.fish.audio/v1"
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
            # 启动时验证参考音色ID
            try:
                is_valid, message = self.validate_reference_id(self.reference_id)
                if is_valid:
                    logger.info(f"参考音色ID验证成功: {message}")
                else:
                    logger.warning(f"参考音色ID验证失败: {message}")
            except Exception as e:
                logger.warning(f"参考音色ID验证过程出错: {str(e)}")
        
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
        
        # 初始化时检查API状态
        try:
            status, message = self.check_api_status()
            if status:
                logger.info(f"Fish Audio API 状态正常: {message}")
            else:
                logger.warning(f"Fish Audio API 状态异常: {message}")
        except Exception as e:
            logger.warning(f"检查Fish Audio API状态出错: {str(e)}")
        
        logger.info("TTS服务初始化成功（Fish Audio）")
    
    def validate_reference_id(self, reference_id: str) -> Tuple[bool, str]:
        """
        验证参考音色ID是否有效
        
        Args:
            reference_id: 参考音色ID
            
        Returns:
            (bool, str): 是否有效，消息
        """
        if not reference_id:
            return False, "音色ID为空"
            
        try:
            # 构建音色验证请求URL
            url = f"{self.api_base_url}/reference/{reference_id}"
            logger.debug(f"验证音色ID，请求URL: {url}")
            
            # 发送请求
            response = requests.get(url, headers=self.headers)
            
            # 处理响应
            if response.status_code == 200:
                data = response.json()
                if "reference_id" in data and data["reference_id"] == reference_id:
                    return True, f"音色ID有效，名称: {data.get('name', '未知')}"
                else:
                    return True, "音色ID有效，但返回数据格式不完整"
            elif response.status_code == 404:
                return False, "音色ID不存在"
            else:
                return False, f"验证请求失败，状态码: {response.status_code}, 错误: {response.text}"
                
        except Exception as e:
            logger.error(f"验证音色ID出错: {str(e)}")
            return False, f"验证过程出错: {str(e)}"
    
    def check_api_status(self) -> Tuple[bool, str]:
        """
        检查Fish Audio API的状态
        
        Returns:
            (bool, str): 是否正常，消息
        """
        try:
            # 构建状态检查请求URL（使用模型列表端点作为健康检查）
            url = f"{self.api_base_url}/models"
            logger.debug(f"检查API状态，请求URL: {url}")
            
            # 发送请求
            response = requests.get(url, headers=self.headers)
            
            # 处理响应
            if response.status_code == 200:
                data = response.json()
                if "data" in data and isinstance(data["data"], list):
                    models = data["data"]
                    model_names = [model.get("id", "未知") for model in models]
                    return True, f"API正常，可用模型: {', '.join(model_names)}"
                else:
                    return True, "API正常，但返回数据格式不完整"
            else:
                return False, f"API状态异常，状态码: {response.status_code}, 错误: {response.text}"
                
        except Exception as e:
            logger.error(f"检查API状态出错: {str(e)}")
            return False, f"状态检查过程出错: {str(e)}"
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """
        获取可用的TTS模型列表
        
        Returns:
            List[Dict[str, Any]]: 模型列表
        """
        try:
            url = f"{self.api_base_url}/models"
            logger.debug(f"获取模型列表，请求URL: {url}")
            
            # 发送请求
            response = requests.get(url, headers=self.headers)
            
            # 处理响应
            if response.status_code == 200:
                data = response.json()
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
                else:
                    logger.warning("获取模型列表成功，但返回数据格式不完整")
                    return []
            else:
                logger.error(f"获取模型列表失败，状态码: {response.status_code}, 错误: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"获取模型列表出错: {str(e)}")
            return []
    
    def _prepare_request_data(
        self,
        text: str,
        reference_id: Optional[str] = None,
        speed: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None
    ) -> Dict[str, Any]:
        """准备TTS请求数据"""
        
        # 预处理文本
        text = text.strip()
        if not text:
            raise ValueError("文本不能为空")
        
        # 准备请求数据
        data = {"text": text}
        
        # 添加参数（如果指定）
        if speed is not None:
            data["speed"] = max(0.5, min(2.0, speed))
        if volume is not None:
            data["volume"] = max(0.1, min(2.0, volume))
        if pitch is not None:
            data["pitch"] = max(-12.0, min(12.0, pitch))
        
        # 设置参考音色ID
        ref_id = reference_id if reference_id else self.reference_id
        if ref_id:
            data["reference_id"] = ref_id
            
        # 记录完整的请求数据，不做截断
        logger.debug(f"准备TTS请求数据: {json.dumps(data, ensure_ascii=False)}")
        
        return data
    
    def _log_request_response(self, url: str, headers: Dict[str, str], data: Dict[str, Any], response, duration: float):
        """记录请求和响应详情"""
        request_id = f"req_{int(time.time())}_{hash(data['text']) % 10000:04d}"
        
        # 记录完整请求详情，不做截断
        log_data = data.copy()
        
        # 屏蔽API密钥
        log_headers = headers.copy()
        if 'Authorization' in log_headers:
            auth_parts = log_headers['Authorization'].split(' ')
            if len(auth_parts) > 1:
                log_headers['Authorization'] = f"{auth_parts[0]} {'*' * 10}"
        
        logger.info(f"[{request_id}] 请求详情:")
        logger.info(f"[{request_id}] URL: {url}")
        logger.info(f"[{request_id}] 请求头: {json.dumps(log_headers, ensure_ascii=False)}")
        logger.info(f"[{request_id}] 请求体: {json.dumps(log_data, ensure_ascii=False)}")
        logger.info(f"[{request_id}] 请求耗时: {duration:.2f}秒")
        
        # 记录响应详情
        if hasattr(response, 'status_code'):
            logger.info(f"[{request_id}] 响应状态码: {response.status_code}")
            
            # 尝试记录响应头
            if hasattr(response, 'headers'):
                logger.info(f"[{request_id}] 响应头: {dict(response.headers)}")
            
            # 尝试记录完整响应内容（如果不是二进制数据）
            if not response.headers.get('Content-Type', '').startswith('audio/'):
                try:
                    if hasattr(response, 'text') and response.text:
                        logger.info(f"[{request_id}] 响应内容: {response.text}")
                    elif hasattr(response, 'content'):
                        logger.info(f"[{request_id}] 响应内容大小: {len(response.content)} 字节")
                except Exception as e:
                    logger.warning(f"[{request_id}] 无法记录响应内容: {str(e)}")
            else:
                logger.info(f"[{request_id}] 响应内容: 二进制音频数据，大小: {len(response.content)} 字节")
    
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
            
            # 如果指定了参考音色ID，验证其有效性
            ref_id = reference_id if reference_id else self.reference_id
            if ref_id:
                is_valid, message = self.validate_reference_id(ref_id)
                if not is_valid:
                    logger.warning(f"参考音色ID无效: {message}")
                else:
                    logger.info(f"参考音色ID有效: {message}")
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送请求
            response = requests.post(url, json=data, headers=self.headers)
            
            # 计算请求耗时
            duration = time.time() - start_time
            
            # 详细记录请求和响应
            self._log_request_response(url, self.headers, data, response, duration)
            
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
            
            logger.info(f"正在调用Fish Audio API（流式），URL: {url}")
            
            # 如果指定了参考音色ID，验证其有效性
            ref_id = reference_id if reference_id else self.reference_id
            if ref_id:
                is_valid, message = self.validate_reference_id(ref_id)
                if not is_valid:
                    logger.warning(f"参考音色ID无效: {message}")
                else:
                    logger.info(f"参考音色ID有效: {message}")
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送请求并获取流式响应
            response = requests.post(url, json=data, headers=self.headers, stream=True)
            
            # 计算初始请求耗时
            initial_duration = time.time() - start_time
            logger.info(f"初始请求耗时: {initial_duration:.2f}秒，等待流式数据中...")
            
            # 详细记录请求和初始响应
            self._log_request_response(url, self.headers, data, response, initial_duration)
            
            if response.status_code != 200:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                response.raise_for_status()
            
            # 流式数据计数
            total_bytes = 0
            chunk_count = 0
            
            # 返回数据流
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    total_bytes += len(chunk)
                    chunk_count += 1
                    if chunk_count % 10 == 0:  # 每10个块记录一次
                        logger.debug(f"已接收 {chunk_count} 个数据块，共 {total_bytes} 字节")
                    yield chunk
            
            # 记录总体情况
            total_duration = time.time() - start_time
            logger.info(f"流式传输完成，总共接收 {chunk_count} 个数据块，{total_bytes} 字节，总耗时: {total_duration:.2f}秒")
                    
        except Exception as e:
            logger.error(f"流式生成语音失败: {str(e)}")
            raise

# 创建全局TTS服务实例
tts_service = TTSService() 