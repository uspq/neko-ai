import os
import shutil
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple, BinaryIO
from datetime import datetime
import numpy as np
import pickle
import faiss
from fastapi import UploadFile, HTTPException

from core.config import settings
from utils.logger import logger
from models.knowledge import KnowledgeFile, KnowledgeChunk, KnowledgeSearchResult
from core.embedding import get_embedding

class KnowledgeService:
    """知识库服务"""
    
    # 支持的文件类型
    SUPPORTED_FILE_TYPES = {
        "text/plain": ".txt",
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-excel": ".xls",
        "text/markdown": ".md",
        "text/csv": ".csv",
        "application/json": ".json"
    }
    
    def __init__(self):
        """初始化知识库服务"""
        # 从配置获取路径和参数
        self.KNOWLEDGE_DIR = settings.KNOWLEDGE_DIR
        self.KNOWLEDGE_INDEX_PATH = settings.KNOWLEDGE_INDEX_PATH
        self.MAX_FILE_SIZE = settings.KNOWLEDGE_MAX_FILE_SIZE
        self.CHUNK_SIZE = settings.KNOWLEDGE_CHUNK_SIZE
        self.CHUNK_OVERLAP = settings.KNOWLEDGE_CHUNK_OVERLAP
        
        # 确保目录存在
        os.makedirs(self.KNOWLEDGE_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(self.KNOWLEDGE_INDEX_PATH), exist_ok=True)
        
        # 初始化文件索引
        self.files_index = {}
        self.chunks_index = {}
        
        # 初始化FAISS索引
        self.dimension = settings.EMBEDDING_DIMENSION
        self.index = None
        self.chunk_ids = []
        
        # 加载索引
        self._load_index()
    
    def _load_index(self):
        """加载知识库索引"""
        # 加载文件和块索引
        files_index_path = os.path.join(self.KNOWLEDGE_DIR, "files_index.json")
        chunks_index_path = os.path.join(self.KNOWLEDGE_DIR, "chunks_index.json")
        
        if os.path.exists(files_index_path):
            try:
                with open(files_index_path, 'r', encoding='utf-8') as f:
                    self.files_index = json.load(f)
                logger.info(f"已加载知识库文件索引，共 {len(self.files_index)} 个文件")
            except Exception as e:
                logger.error(f"加载知识库文件索引失败: {str(e)}")
                self.files_index = {}
        
        if os.path.exists(chunks_index_path):
            try:
                with open(chunks_index_path, 'r', encoding='utf-8') as f:
                    self.chunks_index = json.load(f)
                logger.info(f"已加载知识库文本块索引，共 {len(self.chunks_index)} 个文本块")
            except Exception as e:
                logger.error(f"加载知识库文本块索引失败: {str(e)}")
                self.chunks_index = {}
        
        # 加载FAISS索引
        if os.path.exists(self.KNOWLEDGE_INDEX_PATH):
            try:
                with open(self.KNOWLEDGE_INDEX_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.index = data['index']
                    self.chunk_ids = data.get('chunk_ids', [])
                logger.info(f"已加载知识库FAISS索引，包含 {len(self.chunk_ids)} 个文本块向量")
            except Exception as e:
                logger.error(f"加载知识库FAISS索引失败: {str(e)}")
                self._create_new_index()
        else:
            logger.info("知识库FAISS索引不存在，创建新索引")
            self._create_new_index()
    
    def _create_new_index(self):
        """创建新的FAISS索引"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunk_ids = []
        self._save_index()
    
    def _save_index(self):
        """保存知识库索引"""
        # 保存文件和块索引
        files_index_path = os.path.join(self.KNOWLEDGE_DIR, "files_index.json")
        chunks_index_path = os.path.join(self.KNOWLEDGE_DIR, "chunks_index.json")
        
        try:
            with open(files_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.files_index, f, ensure_ascii=False, indent=2)
            
            with open(chunks_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.chunks_index, f, ensure_ascii=False, indent=2)
            
            # 保存FAISS索引
            with open(self.KNOWLEDGE_INDEX_PATH, 'wb') as f:
                pickle.dump({'index': self.index, 'chunk_ids': self.chunk_ids}, f)
            
            logger.info(f"知识库索引已保存，文件数: {len(self.files_index)}, 文本块数: {len(self.chunks_index)}")
            return True
        except Exception as e:
            logger.error(f"保存知识库索引失败: {str(e)}")
            return False
    
    async def upload_file(self, file: UploadFile) -> KnowledgeFile:
        """上传文件到知识库
        
        Args:
            file: 上传的文件
            
        Returns:
            KnowledgeFile: 上传的文件信息
        """
        try:
            # 检查文件类型
            content_type = file.content_type
            if content_type not in self.SUPPORTED_FILE_TYPES:
                raise HTTPException(status_code=400, detail=f"不支持的文件类型: {content_type}")
            
            # 检查文件大小
            file_size = 0
            file_content = b''
            chunk = await file.read(1024)
            while chunk:
                file_size += len(chunk)
                file_content += chunk
                if file_size > self.MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail=f"文件过大，最大支持 {self.MAX_FILE_SIZE/1024/1024}MB")
                chunk = await file.read(1024)
            
            # 重置文件指针
            await file.seek(0)
            
            # 生成文件ID和保存路径
            file_id = KnowledgeFile.generate_file_id()
            file_ext = self.SUPPORTED_FILE_TYPES[content_type]
            filename = file.filename
            save_filename = f"{file_id}{file_ext}"
            save_path = os.path.join(self.KNOWLEDGE_DIR, save_filename)
            
            # 保存文件
            with open(save_path, "wb") as f:
                f.write(file_content)
            
            # 提取文件内容预览
            content_preview = self._extract_content_preview(save_path, content_type)
            
            # 创建文件记录
            upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_info = KnowledgeFile(
                file_id=file_id,
                filename=filename,
                file_type=content_type,
                file_size=file_size,
                content_preview=content_preview,
                upload_time=upload_time,
                embedding_status="pending"
            )
            
            # 更新文件索引
            self.files_index[file_id] = file_info.dict()
            self._save_index()
            
            # 异步处理文件内容
            # 注意：在实际应用中，这里应该使用后台任务处理
            # 为了简化，这里直接处理
            self._process_file(file_id, save_path, content_type)
            
            return file_info
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"上传文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")
    
    def _extract_content_preview(self, file_path: str, content_type: str, max_length: int = 200) -> str:
        """提取文件内容预览
        
        Args:
            file_path: 文件路径
            content_type: 文件类型
            max_length: 预览最大长度
            
        Returns:
            str: 文件内容预览
        """
        try:
            # 根据文件类型提取内容
            if content_type == "text/plain" or content_type == "text/markdown" or content_type == "text/csv":
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(max_length * 2)
                    return content[:max_length] + ("..." if len(content) > max_length else "")
            
            elif content_type == "application/json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    content = json.dumps(data, ensure_ascii=False)
                    return content[:max_length] + ("..." if len(content) > max_length else "")
            
            elif content_type == "application/pdf":
                # 这里需要使用PDF解析库，如PyPDF2或pdfplumber
                # 为简化示例，返回占位符
                return "[PDF文件内容预览]"
            
            elif "word" in content_type:
                # 这里需要使用Word解析库，如python-docx
                # 为简化示例，返回占位符
                return "[Word文件内容预览]"
            
            elif "excel" in content_type:
                # 这里需要使用Excel解析库，如pandas或openpyxl
                # 为简化示例，返回占位符
                return "[Excel文件内容预览]"
            
            else:
                return "[文件内容预览不可用]"
                
        except Exception as e:
            logger.error(f"提取文件内容预览失败: {str(e)}")
            return "[提取预览失败]"
    
    def _process_file(self, file_id: str, file_path: str, content_type: str):
        """处理文件内容，分块并生成嵌入向量
        
        Args:
            file_id: 文件ID
            file_path: 文件路径
            content_type: 文件类型
        """
        try:
            # 更新文件状态为处理中
            if file_id in self.files_index:
                self.files_index[file_id]["embedding_status"] = "processing"
                self._save_index()
            
            # 提取文件内容
            content = self._extract_file_content(file_path, content_type)
            
            # 分块处理
            chunks = self._split_text_into_chunks(content, self.CHUNK_SIZE, self.CHUNK_OVERLAP)
            
            # 创建文本块记录并生成嵌入向量
            chunk_count = 0
            for i, chunk_text in enumerate(chunks):
                if not chunk_text.strip():
                    continue
                
                # 生成块ID
                chunk_id = f"{file_id}_{i}"
                
                # 创建块记录
                chunk_info = KnowledgeChunk(
                    chunk_id=chunk_id,
                    file_id=file_id,
                    content=chunk_text,
                    chunk_index=i,
                    embedding_status="pending"
                )
                
                # 更新块索引
                self.chunks_index[chunk_id] = chunk_info.dict()
                
                # 生成嵌入向量
                try:
                    embedding = get_embedding(chunk_text)
                    
                    # 添加到FAISS索引
                    self.index.add(np.array([embedding]))
                    self.chunk_ids.append(chunk_id)
                    
                    # 更新块状态
                    self.chunks_index[chunk_id]["embedding_status"] = "completed"
                    chunk_count += 1
                    
                except Exception as e:
                    logger.error(f"生成文本块嵌入向量失败: {str(e)}")
                    self.chunks_index[chunk_id]["embedding_status"] = "failed"
            
            # 更新文件状态和块数量
            if file_id in self.files_index:
                self.files_index[file_id]["embedding_status"] = "completed"
                self.files_index[file_id]["chunks_count"] = chunk_count
            
            # 保存索引
            self._save_index()
            
            logger.info(f"文件 {file_id} 处理完成，生成了 {chunk_count} 个文本块")
            
        except Exception as e:
            logger.error(f"处理文件 {file_id} 失败: {str(e)}")
            # 更新文件状态为失败
            if file_id in self.files_index:
                self.files_index[file_id]["embedding_status"] = "failed"
                self._save_index()
    
    def _extract_file_content(self, file_path: str, content_type: str) -> str:
        """提取文件内容
        
        Args:
            file_path: 文件路径
            content_type: 文件类型
            
        Returns:
            str: 文件内容
        """
        try:
            # 根据文件类型提取内容
            if content_type == "text/plain" or content_type == "text/markdown" or content_type == "text/csv":
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            
            elif content_type == "application/json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return json.dumps(data, ensure_ascii=False)
            
            elif content_type == "application/pdf":
                # 这里需要使用PDF解析库，如PyPDF2或pdfplumber
                # 为简化示例，返回占位符
                return f"[PDF文件内容: {file_path}]"
            
            elif "word" in content_type:
                # 这里需要使用Word解析库，如python-docx
                # 为简化示例，返回占位符
                return f"[Word文件内容: {file_path}]"
            
            elif "excel" in content_type:
                # 这里需要使用Excel解析库，如pandas或openpyxl
                # 为简化示例，返回占位符
                return f"[Excel文件内容: {file_path}]"
            
            else:
                return f"[不支持的文件类型: {content_type}]"
                
        except Exception as e:
            logger.error(f"提取文件内容失败: {str(e)}")
            return f"[提取内容失败: {str(e)}]"
    
    def _split_text_into_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """将文本分割成块
        
        Args:
            text: 要分割的文本
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            
        Returns:
            List[str]: 文本块列表
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            # 计算当前块的结束位置
            end = min(start + chunk_size, text_length)
            
            # 如果不是最后一块，尝试在句子或段落边界分割
            if end < text_length:
                # 尝试在段落边界分割
                paragraph_end = text.rfind('\n\n', start, end)
                if paragraph_end > start + chunk_size // 2:
                    end = paragraph_end + 2
                else:
                    # 尝试在句子边界分割
                    sentence_end = text.rfind('. ', start, end)
                    if sentence_end > start + chunk_size // 2:
                        end = sentence_end + 2
            
            # 添加当前块
            chunks.append(text[start:end])
            
            # 更新下一块的起始位置
            start = end - chunk_overlap
            
            # 确保起始位置有效
            if start < 0 or start >= text_length:
                break
        
        return chunks
    
    def get_file_list(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取文件列表
        
        Args:
            page: 页码，从1开始
            page_size: 每页条数
            
        Returns:
            Dict: 包含分页数据和分页信息
        """
        try:
            # 获取所有文件
            files = list(self.files_index.values())
            
            # 按上传时间降序排序
            files.sort(key=lambda x: x["upload_time"], reverse=True)
            
            # 计算分页信息
            total = len(files)
            total_pages = (total + page_size - 1) // page_size
            
            # 获取当前页的数据
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total)
            
            page_items = files[start_idx:end_idx] if start_idx < total else []
            
            # 转换为KnowledgeFile对象
            file_objects = [KnowledgeFile(**item) for item in page_items]
            
            return {
                "files": file_objects,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error(f"获取文件列表失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")
    
    def get_file_detail(self, file_id: str) -> Dict[str, Any]:
        """获取文件详情
        
        Args:
            file_id: 文件ID
            
        Returns:
            Dict: 文件详情
        """
        try:
            # 检查文件是否存在
            if file_id not in self.files_index:
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
            
            # 获取文件信息
            file_info = self.files_index[file_id]
            file = KnowledgeFile(**file_info)
            
            # 获取文件的文本块
            chunks = []
            chunks_count = 0
            
            for chunk_id, chunk_info in self.chunks_index.items():
                if chunk_info["file_id"] == file_id:
                    chunks_count += 1
                    # 只返回前5个块的预览
                    if len(chunks) < 5:
                        chunks.append({
                            "chunk_id": chunk_id,
                            "content": chunk_info["content"][:200] + ("..." if len(chunk_info["content"]) > 200 else ""),
                            "chunk_index": chunk_info["chunk_index"],
                            "embedding_status": chunk_info["embedding_status"]
                        })
            
            return {
                "file": file,
                "chunks_count": chunks_count,
                "chunks_preview": chunks
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取文件详情失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取文件详情失败: {str(e)}")
    
    def delete_file(self, file_id: str) -> bool:
        """删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 检查文件是否存在
            if file_id not in self.files_index:
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
            
            # 获取文件信息
            file_info = self.files_index[file_id]
            file_type = file_info["file_type"]
            file_ext = self.SUPPORTED_FILE_TYPES[file_type]
            file_path = os.path.join(self.KNOWLEDGE_DIR, f"{file_id}{file_ext}")
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 删除文件索引
            del self.files_index[file_id]
            
            # 删除文件的文本块
            chunk_ids_to_delete = []
            for chunk_id, chunk_info in self.chunks_index.items():
                if chunk_info["file_id"] == file_id:
                    chunk_ids_to_delete.append(chunk_id)
            
            for chunk_id in chunk_ids_to_delete:
                del self.chunks_index[chunk_id]
            
            # 重建FAISS索引
            self._rebuild_faiss_index()
            
            # 保存索引
            self._save_index()
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
    
    def _rebuild_faiss_index(self):
        """重建FAISS索引"""
        try:
            # 创建新索引
            new_index = faiss.IndexFlatL2(self.dimension)
            new_chunk_ids = []
            
            # 遍历所有文本块
            for chunk_id, chunk_info in self.chunks_index.items():
                if chunk_info["embedding_status"] == "completed":
                    try:
                        # 重新生成嵌入向量
                        embedding = get_embedding(chunk_info["content"])
                        
                        # 添加到新索引
                        new_index.add(np.array([embedding]))
                        new_chunk_ids.append(chunk_id)
                        
                    except Exception as e:
                        logger.error(f"重建索引时生成嵌入向量失败: {str(e)}")
                        self.chunks_index[chunk_id]["embedding_status"] = "failed"
            
            # 更新索引
            self.index = new_index
            self.chunk_ids = new_chunk_ids
            
            logger.info(f"FAISS索引重建完成，包含 {len(self.chunk_ids)} 个文本块向量")
            
        except Exception as e:
            logger.error(f"重建FAISS索引失败: {str(e)}")
    
    def search_knowledge(self, query: str, limit: int = 10, file_ids: List[str] = None) -> List[KnowledgeSearchResult]:
        """搜索知识库
        
        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            file_ids: 限制搜索的文件ID列表
            
        Returns:
            List[KnowledgeSearchResult]: 搜索结果列表
        """
        try:
            # 检查索引是否为空
            if self.index.ntotal == 0:
                return []
            
            # 获取查询的嵌入向量
            query_embedding = get_embedding(query)
            
            # 搜索最相似的向量
            k = min(limit * 2, self.index.ntotal)  # 获取更多结果，以便过滤
            distances, indices = self.index.search(np.array([query_embedding]), k)
            
            results = []
            
            for i, idx in enumerate(indices[0]):
                if idx < len(self.chunk_ids):
                    chunk_id = self.chunk_ids[idx]
                    
                    # 检查文本块是否存在
                    if chunk_id not in self.chunks_index:
                        continue
                    
                    chunk_info = self.chunks_index[chunk_id]
                    file_id = chunk_info["file_id"]
                    
                    # 如果指定了文件ID列表，则只返回这些文件的结果
                    if file_ids and file_id not in file_ids:
                        continue
                    
                    # 检查文件是否存在
                    if file_id not in self.files_index:
                        continue
                    
                    file_info = self.files_index[file_id]
                    
                    # 将L2距离转换为相似度分数（0-1之间）
                    similarity = 1 / (1 + distances[0][i])
                    
                    # 创建搜索结果
                    result = KnowledgeSearchResult(
                        chunk_id=chunk_id,
                        file_id=file_id,
                        filename=file_info["filename"],
                        content=chunk_info["content"],
                        similarity=similarity,
                        metadata={
                            "file_type": file_info["file_type"],
                            "upload_time": file_info["upload_time"],
                            "chunk_index": chunk_info["chunk_index"]
                        }
                    )
                    
                    results.append(result)
                    
                    # 如果已经有足够的结果，则停止
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            logger.error(f"搜索知识库失败: {str(e)}")
            return []

# 创建全局知识库服务实例
knowledge_service = KnowledgeService()