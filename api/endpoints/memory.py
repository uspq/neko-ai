from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from typing import List, Dict, Any, Optional

from models.memory import MemoryCreate, MemoryResponse, MemorySearchRequest, MemorySearchResponse, MemoryStatistics
from services.memory_service import MemoryService
from utils.logger import get_logger

api_logger = get_logger("api")

router = APIRouter()

@router.post("/create", response_model=str, summary="创建新记忆")
async def create_memory(memory: MemoryCreate):
    """
    创建新的记忆
    
    - **user_message**: 用户消息
    - **ai_response**: AI回复
    
    返回创建的记忆时间戳
    """
    try:
        timestamp = MemoryService.save_conversation(
            user_message=memory.user_message,
            ai_response=memory.ai_response
        )
        
        api_logger.info(f"创建记忆成功，时间戳: {timestamp}")
        return timestamp
        
    except Exception as e:
        api_logger.error(f"创建记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建记忆失败: {str(e)}")

@router.get("/get/{timestamp}", response_model=MemoryResponse, summary="获取记忆")
async def get_memory(timestamp: str = Path(..., description="记忆时间戳")):
    """
    根据时间戳获取记忆
    
    - **timestamp**: 记忆时间戳
    
    返回记忆详情
    """
    try:
        memory = MemoryService.get_memory_by_timestamp(timestamp)
        
        if not memory:
            api_logger.warning(f"记忆不存在: {timestamp}")
            raise HTTPException(status_code=404, detail=f"记忆不存在: {timestamp}")
            
        api_logger.info(f"获取记忆成功: {timestamp}")
        return memory
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取记忆失败: {str(e)}")

@router.post("/search", response_model=MemorySearchResponse, summary="搜索记忆")
async def search_memories(request: MemorySearchRequest):
    """
    搜索记忆
    
    - **keyword**: 搜索关键词
    - **limit**: 返回结果数量限制
    
    返回匹配的记忆列表
    """
    try:
        memories = MemoryService.search_memories(
            keyword=request.keyword,
            limit=request.limit
        )
        
        api_logger.info(f"搜索记忆成功，关键词: {request.keyword}, 找到: {len(memories)} 条")
        return MemorySearchResponse(
            results=memories,
            count=len(memories)
        )
        
    except Exception as e:
        api_logger.error(f"搜索记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索记忆失败: {str(e)}")

@router.get("/statistics", response_model=MemoryStatistics, summary="获取记忆统计信息")
async def get_memory_statistics():
    """
    获取记忆统计信息
    
    返回记忆统计信息，包括数量、大小、主题分布等
    """
    try:
        statistics = MemoryService.get_memory_statistics()
        api_logger.info("获取记忆统计信息成功")
        return statistics
        
    except Exception as e:
        api_logger.error(f"获取记忆统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取记忆统计信息失败: {str(e)}")

@router.delete("/clear", summary="清除所有记忆")
async def clear_all_memories():
    """
    清除所有记忆数据
    
    返回操作是否成功
    """
    try:
        success = MemoryService.clear_all_memories()
        
        if success:
            api_logger.info("清除所有记忆成功")
            return {"message": "所有记忆已清除", "success": True}
        else:
            api_logger.warning("清除所有记忆失败")
            return {"message": "清除记忆失败", "success": False}
        
    except Exception as e:
        api_logger.error(f"清除记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清除记忆失败: {str(e)}")

@router.delete("/clear/{keyword}", summary="根据关键词清除记忆")
async def clear_memories_by_keyword(keyword: str = Path(..., description="要清除的记忆关键词")):
    """
    根据关键词清除记忆
    
    - **keyword**: 要清除的记忆关键词
    
    返回清除的记忆数量
    """
    try:
        deleted_count, timestamps = MemoryService.clear_memories_by_keyword(keyword)
        
        api_logger.info(f"根据关键词 '{keyword}' 清除了 {deleted_count} 条记忆")
        return {
            "message": f"已清除 {deleted_count} 条包含关键词 '{keyword}' 的记忆",
            "deleted_count": deleted_count,
            "timestamps": timestamps
        }
        
    except Exception as e:
        api_logger.error(f"根据关键词清除记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"根据关键词清除记忆失败: {str(e)}")

@router.post("/backup", summary="备份记忆数据")
async def backup_memories(background_tasks: BackgroundTasks, backup_dir: Optional[str] = None):
    """
    备份所有记忆数据
    
    - **backup_dir**: 备份目录，默认为配置中的备份目录
    
    返回备份文件路径
    """
    try:
        # 在后台任务中执行备份
        def do_backup():
            try:
                backup_path = MemoryService.backup_memories(backup_dir)
                api_logger.info(f"记忆数据备份成功: {backup_path}")
            except Exception as e:
                api_logger.error(f"记忆数据备份失败: {str(e)}")
        
        background_tasks.add_task(do_backup)
        
        return {"message": "记忆数据备份已开始，将在后台执行"}
        
    except Exception as e:
        api_logger.error(f"启动记忆数据备份失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动记忆数据备份失败: {str(e)}")

@router.post("/restore", summary="恢复记忆数据")
async def restore_memories(backup_path: str):
    """
    从备份恢复记忆数据
    
    - **backup_path**: 备份文件路径
    
    返回操作是否成功
    """
    try:
        success = MemoryService.restore_memories(backup_path)
        
        if success:
            api_logger.info(f"从 {backup_path} 恢复记忆数据成功")
            return {"message": f"记忆数据已从 {backup_path} 恢复", "success": True}
        else:
            api_logger.warning(f"从 {backup_path} 恢复记忆数据失败")
            return {"message": f"从 {backup_path} 恢复记忆数据失败", "success": False}
        
    except Exception as e:
        api_logger.error(f"恢复记忆数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"恢复记忆数据失败: {str(e)}")

@router.get("/paged", summary="分页获取记忆")
async def get_paged_memories(
    page: int = Query(1, description="页码，从1开始", ge=1),
    page_size: int = Query(10, description="每页条数", ge=1, le=100),
    sort_by: str = Query("timestamp", description="排序字段(timestamp)"),
    sort_desc: bool = Query(True, description="是否降序排序")
):
    """
    分页获取记忆列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页条数，最大100
    - **sort_by**: 排序字段，目前只支持timestamp
    - **sort_desc**: 是否降序排序
    
    返回分页的记忆列表
    """
    try:
        result = MemoryService.get_paged_memories(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
        
        api_logger.info(f"分页获取记忆成功: 第{page}页，每页{page_size}条")
        return result
        
    except Exception as e:
        api_logger.error(f"分页获取记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分页获取记忆失败: {str(e)}") 