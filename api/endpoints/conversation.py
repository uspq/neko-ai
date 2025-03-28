from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from typing import List, Optional

from models.conversation import (
    Conversation, ConversationCreate, ConversationUpdate,
    ConversationList, ConversationMessage, ConversationMessageList,
    generate_conversation_id
)
from models.memory import MemoryClearRequest
from services.conversation_service import conversation_service
from utils.logger import api_logger

router = APIRouter()

@router.post("", response_model=Conversation, summary="创建新对话")
async def create_conversation(request: ConversationCreate):
    """
    创建新的对话
    
    - **title**: 对话标题
    - **description**: 对话描述(可选)
    - **settings**: 对话设置(可选)
    - **files**: 关联的文件ID列表(可选)
    
    返回创建的对话信息
    """
    try:
        # 创建新对话
        conversation_id = conversation_service.create_conversation(request)
        
        if not conversation_id:
            raise HTTPException(status_code=500, detail="创建对话失败")
            
        # 获取创建的对话
        conversation = conversation_service.get_conversation(conversation_id)
        
        # 如果有关联文件，保存文件关联
        if request.files:
            conversation_service.update_conversation_files(
                conversation_id=conversation_id,
                file_ids=request.files
            )
            # 更新返回的对话对象
            conversation["files"] = request.files
        
        api_logger.info(f"创建对话成功: ID={conversation_id}, 标题={request.title}")
        return conversation
        
    except Exception as e:
        api_logger.error(f"创建对话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建对话失败: {str(e)}")

@router.get("/conversations", response_model=ConversationList, summary="获取对话列表")
async def get_conversations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """
    获取对话列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，默认20
    
    返回分页的对话列表
    """
    try:
        api_logger.info(f"获取对话列表请求: 页码 {page}, 每页 {page_size}")
        
        result = conversation_service.get_all_conversations(page, page_size)
        return result
        
    except Exception as e:
        api_logger.error(f"获取对话列表请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")

@router.get("/conversations/{conversation_id}", response_model=Conversation, summary="获取对话详情")
async def get_conversation(conversation_id: int):
    """
    获取对话详情
    
    - **conversation_id**: 对话ID
    
    返回指定对话的详细信息
    """
    try:
        api_logger.info(f"获取对话详情请求: {conversation_id}")
        
        conversation = conversation_service.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在")
            
        return conversation
        
    except HTTPException:
        raise
        
    except Exception as e:
        api_logger.error(f"获取对话详情请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对话详情失败: {str(e)}")

@router.put("/conversations/{conversation_id}", response_model=Conversation, summary="更新对话")
async def update_conversation(conversation_id: int, update_data: ConversationUpdate):
    """
    更新对话信息
    
    - **conversation_id**: 对话ID
    - **title**: 对话标题（可选）
    - **description**: 对话描述（可选）
    - **settings**: 对话设置（可选）
    
    成功更新后返回更新后的对话详情
    """
    try:
        api_logger.info(f"更新对话请求: {conversation_id}")
        
        success = conversation_service.update_conversation(conversation_id, update_data)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在或更新失败")
            
        conversation = conversation_service.get_conversation(conversation_id)
        return conversation
        
    except ValueError as ve:
        api_logger.error(f"更新对话请求验证失败: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
        
    except HTTPException:
        raise
        
    except Exception as e:
        api_logger.error(f"更新对话请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新对话失败: {str(e)}")

@router.delete("/conversations/{conversation_id}", summary="删除对话")
async def delete_conversation(conversation_id: int):
    """
    删除对话及其所有消息和记忆
    
    - **conversation_id**: 对话ID
    
    删除成功返回成功消息
    """
    try:
        api_logger.info(f"删除对话请求: {conversation_id}")
        
        success = conversation_service.delete_conversation(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在或删除失败")
            
        return {"message": f"对话 {conversation_id} 已成功删除"}
        
    except Exception as e:
        api_logger.error(f"删除对话请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除对话失败: {str(e)}")

@router.get("/conversations/{conversation_id}/messages", response_model=ConversationMessageList, summary="获取对话消息")
async def get_conversation_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_asc: bool = Query(False, description="是否按时间升序排序（从旧到新）")
):
    """
    获取对话消息历史
    
    - **conversation_id**: 对话ID
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，默认20
    - **sort_asc**: 是否按时间升序排序，默认false（从新到旧）
    
    返回分页的对话消息列表
    """
    try:
        api_logger.info(f"获取对话消息请求: {conversation_id}, 页码 {page}, 每页 {page_size}, 升序: {sort_asc}")
        
        result = conversation_service.get_conversation_messages(
            conversation_id, 
            page, 
            page_size,
            sort_asc
        )
        
        if result["total"] == 0 and page == 1:
            # 检查对话是否存在
            conversation = conversation_service.get_conversation(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在")
        
        return result
        
    except HTTPException:
        raise
        
    except Exception as e:
        api_logger.error(f"获取对话消息请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对话消息失败: {str(e)}")

@router.delete("/conversations/{conversation_id}/messages", summary="清除对话消息")
async def clear_conversation_messages(conversation_id: int, request: MemoryClearRequest):
    """
    清除对话的所有消息和记忆
    
    - **conversation_id**: 对话ID
    - **confirm**: 确认清除 (必须设置为true才能执行清除操作)
    
    清除成功返回成功消息
    """
    try:
        if not request.confirm:
            raise HTTPException(status_code=400, detail="必须确认清除操作")
            
        api_logger.info(f"清除对话消息请求: {conversation_id}")
        
        success = conversation_service.clear_conversation_messages(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在或清除失败")
            
        return {"message": f"对话 {conversation_id} 的所有消息和记忆已成功清除"}
        
    except HTTPException:
        raise
        
    except Exception as e:
        api_logger.error(f"清除对话消息请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清除对话消息失败: {str(e)}")

@router.put("/{conversation_id}/files", response_model=Conversation, summary="更新对话关联的文件")
async def update_conversation_files(
    conversation_id: int = Path(..., description="对话ID"),
    files: List[str] = Body(..., description="文件ID列表")
):
    """
    更新对话关联的文件ID列表
    
    - **conversation_id**: 对话ID
    - **files**: 文件ID列表，如需清空文件关联，请传递空列表[]
    
    返回更新后的对话信息
    """
    try:
        # 检查对话是否存在
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"对话 {conversation_id} 不存在")
        
        # 更新文件关联
        success = conversation_service.update_conversation_files(
            conversation_id=conversation_id,
            file_ids=files
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"更新对话文件关联失败")
        
        # 获取更新后的对话
        updated_conversation = conversation_service.get_conversation(conversation_id)
        
        api_logger.info(f"更新对话 {conversation_id} 的文件关联成功: {files}")
        return updated_conversation
        
    except Exception as e:
        api_logger.error(f"更新对话文件关联失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新对话文件关联失败: {str(e)}") 