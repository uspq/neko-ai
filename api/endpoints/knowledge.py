from fastapi import APIRouter, HTTPException, Path, Query, UploadFile, File, BackgroundTasks
from typing import List, Dict, Any, Optional
import json

from models.knowledge import FileUploadResponse, FileListResponse, FileDetailResponse, KnowledgeSearchRequest, KnowledgeSearchResponse
from services.knowledge_service import knowledge_service
from utils.logger import get_logger

router = APIRouter()

api_logger = get_logger("api")

@router.post("/upload", response_model=FileUploadResponse, summary="上传文件到知识库")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件到知识库
    
    - **file**: 要上传的文件
    
    返回上传的文件信息
    """
    try:
        file_info = await knowledge_service.upload_file(file)
        
        api_logger.info(f"文件上传成功: {file_info.filename}, ID: {file_info.file_id}")
        
        # 构建详细的使用说明
        usage_message = (
            "文件上传成功！您可以在聊天时通过以下方式使用该文件："
            f"\n1. 使用文件ID: 在聊天请求中设置 knowledge_query='{file_info.file_id}'"
            f"\n2. 使用文件名: 在聊天请求中设置 knowledge_query='{file_info.filename}'"
            "\n3. 设置 use_knowledge=true 启用知识库查询"
        )
        
        return FileUploadResponse(
            file_id=file_info.file_id,
            filename=file_info.filename,
            file_type=file_info.file_type,
            file_size=file_info.file_size,
            upload_time=file_info.upload_time,
            status="success",
            message=usage_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.get("/files", response_model=FileListResponse, summary="获取知识库文件列表")
async def get_file_list(
    page: int = Query(1, description="页码，从1开始", ge=1),
    page_size: int = Query(10, description="每页条数", ge=1, le=100)
):
    """
    获取知识库文件列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页条数，最大100
    
    返回分页的文件列表
    """
    try:
        result = knowledge_service.get_file_list(page=page, page_size=page_size)
        
        api_logger.info(f"获取知识库文件列表成功: 第{page}页，每页{page_size}条")
        return FileListResponse(
            files=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"]
        )
        
    except Exception as e:
        api_logger.error(f"获取知识库文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识库文件列表失败: {str(e)}")

@router.get("/files/{file_id}", response_model=FileDetailResponse, summary="获取知识库文件详情")
async def get_file_detail(file_id: str = Path(..., description="文件ID")):
    """
    获取知识库文件详情
    
    - **file_id**: 文件ID
    
    返回文件详情和文本块预览
    """
    try:
        result = knowledge_service.get_file_detail(file_id)
        
        api_logger.info(f"获取知识库文件详情成功: {file_id}")
        return FileDetailResponse(
            file=result["file"],
            chunks_count=result["chunks_count"],
            chunks_preview=result["chunks_preview"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取知识库文件详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取知识库文件详情失败: {str(e)}")

@router.delete("/files/{file_id}", summary="删除知识库文件")
async def delete_file(file_id: str = Path(..., description="文件ID")):
    """
    删除知识库文件
    
    - **file_id**: 文件ID
    
    返回操作是否成功
    """
    try:
        success = knowledge_service.delete_file(file_id)
        
        if success:
            api_logger.info(f"删除知识库文件成功: {file_id}")
            return {"message": f"文件 {file_id} 已删除", "success": True}
        else:
            api_logger.warning(f"删除知识库文件失败: {file_id}")
            return {"message": f"删除文件 {file_id} 失败", "success": False}
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"删除知识库文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除知识库文件失败: {str(e)}")

@router.post("/search", response_model=KnowledgeSearchResponse, summary="搜索知识库")
async def search_knowledge(request: KnowledgeSearchRequest):
    """
    搜索知识库
    
    - **query**: 搜索查询
    - **limit**: 返回结果数量限制
    - **file_ids**: 限制搜索的文件ID列表
    
    返回匹配的知识库内容
    """
    try:
        # 记录请求体
        request_dict = request.dict()
        api_logger.info(f"搜索知识库请求，查询: {request.query}, 限制: {request.limit}, 文件IDs: {request.file_ids}")
        api_logger.info(f"请求体: {json.dumps(request_dict, ensure_ascii=False)}")
        
        results = knowledge_service.search_knowledge(
            query=request.query,
            limit=request.limit,
            file_ids=request.file_ids
        )
        
        # 构建响应
        response = KnowledgeSearchResponse(
            results=results,
            count=len(results)
        )
        
        # 记录完整响应体，不做截断处理
        api_logger.info(f"搜索知识库成功，查询: {request.query}, 找到: {len(results)} 条")
        api_logger.info(f"响应体: {json.dumps(response.dict(), ensure_ascii=False)}")
        
        return response
        
    except Exception as e:
        api_logger.error(f"搜索知识库失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索知识库失败: {str(e)}")