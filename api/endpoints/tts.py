from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any, List
import tempfile
import os
import time
import json

from services.tts_service import tts_service
from utils.logger import get_logger

router = APIRouter(prefix="/tts", tags=["文本转语音"])
logger = get_logger("api.tts")

class TTSRequest(BaseModel):
    """TTS请求模型"""
    text: str
    reference_id: Optional[str] = None
    speed: Optional[float] = None
    volume: Optional[float] = None
    pitch: Optional[float] = None

class TTSStatusResponse(BaseModel):
    """TTS状态响应模型"""
    enabled: bool
    api_status: Dict[str, Any]
    config: Dict[str, Any]
    reference_id_status: Optional[Dict[str, Any]] = None
    models: List[Dict[str, Any]]

@router.get("/status", response_model=TTSStatusResponse, summary="获取TTS服务状态")
async def get_tts_status(req: Request):
    """
    获取TTS服务状态信息
    
    返回TTS服务的详细状态，包括：
    - 服务是否启用
    - API连接状态
    - 当前配置
    - 参考音色ID的有效性
    - 可用的TTS模型列表
    
    这个端点可用于诊断TTS相关问题
    """
    # 生成请求ID
    request_id = f"api_{int(time.time())}"
    start_time = time.time()
    
    logger.info(f"[{request_id}] TTS状态请求开始 - /status")
    logger.info(f"[{request_id}] 客户端IP: {req.client.host}")
    
    try:
        # 检查TTS服务是否启用
        if not tts_service.enabled:
            return JSONResponse(
                status_code=200,
                content={
                    "enabled": False,
                    "api_status": {"status": False, "message": "TTS服务未启用"},
                    "config": {},
                    "reference_id_status": None,
                    "models": []
                }
            )
        
        # 获取API状态
        api_status_ok, api_status_msg = tts_service.check_api_status()
        
        # 获取配置
        config_info = {
            "model": tts_service.model,
            "reference_id": tts_service.reference_id,
            "has_developer_id": bool(tts_service.developer_id),
            "voice_settings": tts_service.voice_settings
        }
        
        # 验证参考音色ID
        reference_id_status = None
        if tts_service.reference_id:
            is_valid, message = tts_service.validate_reference_id(tts_service.reference_id)
            reference_id_status = {
                "reference_id": tts_service.reference_id,
                "valid": is_valid,
                "message": message
            }
        
        # 获取可用模型列表
        models = tts_service.list_available_models()
        
        # 构建响应
        response_data = {
            "enabled": tts_service.enabled,
            "api_status": {
                "status": api_status_ok,
                "message": api_status_msg
            },
            "config": config_info,
            "reference_id_status": reference_id_status,
            "models": models
        }
        
        duration = time.time() - start_time
        logger.info(f"[{request_id}] TTS状态请求完成，耗时: {duration:.2f}秒")
        
        return response_data
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] 获取TTS状态失败: {str(e)}, 耗时: {duration:.2f}秒")
        raise HTTPException(status_code=500, detail=f"获取TTS状态失败: {str(e)}")

@router.post("/generate", summary="生成语音")
async def generate_speech(request: TTSRequest, req: Request):
    """
    将文本转换为语音
    
    Args:
        request: TTS请求参数
            - text: 要转换的文本
            - reference_id: 可选，参考音色ID
            - speed: 可选，语速 (0.5-2.0)
            - volume: 可选，音量 (0.1-2.0)
            - pitch: 可选，音高 (-12.0-12.0)
            
    Help:音色id是什么？https://fish.audio/zh-CN/m/7f92f8afb8ec43bf81429cc1c9199cb1/ 中7f92f8afb8ec43bf81429cc1c9199cb1就是音色id
    
    Returns:
        音频文件
    """
    # 生成请求ID
    request_id = f"api_{int(time.time())}"
    start_time = time.time()
    
    # 记录请求头信息
    headers = dict(req.headers.items())
    # 敏感信息处理
    if 'authorization' in headers:
        headers['authorization'] = "Bearer ***"
    if 'cookie' in headers:
        headers['cookie'] = "***"
    
    # 记录完整请求体，不做截断处理
    request_dict = request.model_dump()
    
    logger.info(f"[{request_id}] TTS请求开始 - /generate")
    logger.info(f"[{request_id}] 客户端IP: {req.client.host}")
    logger.info(f"[{request_id}] 请求头: {json.dumps(headers, ensure_ascii=False)}")
    logger.info(f"[{request_id}] 请求体: {json.dumps(request_dict, ensure_ascii=False)}")
    
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            audio = tts_service.generate_speech(
                text=request.text,
                reference_id=request.reference_id,
                speed=request.speed,
                volume=request.volume,
                pitch=request.pitch,
                output_path=temp_file.name
            )
        
        duration = time.time() - start_time
        logger.info(f"[{request_id}] TTS生成成功，耗时: {duration:.2f}秒，临时文件: {temp_file.name}")
            
        # 返回音频文件
        response = FileResponse(
            temp_file.name,
            media_type="audio/mpeg",
            filename="speech.mp3",
            background=None  # 同步删除临时文件
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] 生成语音失败: {str(e)}, 耗时: {duration:.2f}秒")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream", summary="流式生成语音")
async def stream_speech(request: TTSRequest, req: Request):
    """
    流式生成语音
    
    Args:
        request: TTS请求参数
            - text: 要转换的文本
            - reference_id: 可选，参考音色ID
            - speed: 可选，语速 (0.5-2.0)
            - volume: 可选，音量 (0.1-2.0)
            - pitch: 可选，音高 (-12.0-12.0)
        
    Returns:
        音频流
    """
    # 生成请求ID
    request_id = f"api_{int(time.time())}"
    start_time = time.time()
    
    # 记录请求头信息
    headers = dict(req.headers.items())
    # 敏感信息处理
    if 'authorization' in headers:
        headers['authorization'] = "Bearer ***"
    if 'cookie' in headers:
        headers['cookie'] = "***"
    
    # 记录完整请求体，不做截断处理
    request_dict = request.model_dump()
    
    logger.info(f"[{request_id}] TTS请求开始 - /stream")
    logger.info(f"[{request_id}] 客户端IP: {req.client.host}")
    logger.info(f"[{request_id}] 请求头: {json.dumps(headers, ensure_ascii=False)}")
    logger.info(f"[{request_id}] 请求体: {json.dumps(request_dict, ensure_ascii=False)}")
    
    try:
        audio_stream = tts_service.stream_speech(
            text=request.text,
            reference_id=request.reference_id,
            speed=request.speed,
            volume=request.volume,
            pitch=request.pitch
        )
        
        # 这里无法准确记录总耗时，因为流式传输会持续一段时间
        prepare_time = time.time() - start_time
        logger.info(f"[{request_id}] TTS流式生成准备完成，准备耗时: {prepare_time:.2f}秒")
        
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'attachment; filename="speech.mp3"'}
        )
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{request_id}] 流式生成语音失败: {str(e)}, 耗时: {duration:.2f}秒")
        raise HTTPException(status_code=500, detail=str(e)) 