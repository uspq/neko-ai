from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
import os

from services.tts_service import tts_service
from utils.logger import get_logger

router = APIRouter(prefix="/tts", tags=["文本转语音"])
logger = get_logger("api.tts")

class TTSRequest(BaseModel):
    """TTS请求模型"""
    text: str

@router.post("/generate", summary="生成语音")
async def generate_speech(request: TTSRequest):
    """
    将文本转换为语音
    
    Args:
        request: TTS请求参数，只需要提供文本内容
        
    Returns:
        音频文件
    """
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            audio = tts_service.generate_speech(
                text=request.text,
                output_path=temp_file.name
            )
            
        # 返回音频文件
        return FileResponse(
            temp_file.name,
            media_type="audio/mpeg",
            filename="speech.mp3",
            background=None  # 同步删除临时文件
        )
        
    except Exception as e:
        logger.error(f"生成语音失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream", summary="流式生成语音")
async def stream_speech(request: TTSRequest):
    """
    流式生成语音
    
    Args:
        request: TTS请求参数，只需要提供文本内容
        
    Returns:
        音频流
    """
    try:
        audio_stream = tts_service.stream_speech(
            text=request.text
        )
        
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'attachment; filename="speech.mp3"'}
        )
        
    except Exception as e:
        logger.error(f"流式生成语音失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 