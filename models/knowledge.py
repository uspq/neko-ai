from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class KnowledgeFile(BaseModel):
    """知识库文件模型"""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    content_preview: str
    upload_time: str
    embedding_status: str = "pending"  # pending, processing, completed, failed
    chunks_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @staticmethod
    def generate_file_id() -> str:
        """生成唯一的文件ID
        
        Returns:
            str: 格式化的时间戳字符串 (YYYY-MM-DD-HH-MM-SS-ffffff)
        """
        return datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")

class KnowledgeChunk(BaseModel):
    """知识库文本块模型"""
    chunk_id: str
    file_id: str
    content: str
    chunk_index: int
    metadata: Optional[Dict[str, Any]] = None
    embedding_status: str = "pending"  # pending, completed, failed

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    upload_time: str
    status: str
    message: str

class FileListResponse(BaseModel):
    """文件列表响应"""
    files: List[KnowledgeFile]
    total: int
    page: int
    page_size: int
    total_pages: int

class FileDetailResponse(BaseModel):
    """文件详情响应"""
    file: KnowledgeFile
    chunks_count: int
    chunks_preview: List[Dict[str, Any]]

class KnowledgeSearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str
    limit: int = 10
    file_ids: Optional[List[str]] = None

class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果项"""
    chunk_id: str
    file_id: str
    filename: str
    content: str
    similarity: float
    metadata: Optional[Dict[str, Any]] = None

class KnowledgeSearchResponse(BaseModel):
    """知识库搜索响应"""
    results: List[KnowledgeSearchResult]
    count: int