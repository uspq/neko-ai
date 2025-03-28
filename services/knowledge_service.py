import os
import json
import shutil
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pickle
import numpy as np
from fastapi import UploadFile, HTTPException

# LangChain导入
from langchain_community.document_loaders import (
    PyPDFLoader, 
    TextLoader, 
    Docx2txtLoader,
    CSVLoader, 
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    JSONLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

# 使用自定义嵌入模块
from core.embedding import get_embedding, get_embeddings
from core.config import settings
from utils.logger import logger
from models.knowledge import KnowledgeFile, KnowledgeChunk, KnowledgeSearchResult

# 创建自定义Embeddings类，封装我们的嵌入函数以兼容LangChain
class CustomEmbeddings(Embeddings):
    """自定义嵌入类，将我们的嵌入函数封装为LangChain兼容格式"""
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """将多个文本转换为嵌入向量"""
        embeddings = get_embeddings(texts)
        # 将numpy数组转换为普通列表
        return [embedding.tolist() for embedding in embeddings]
    
    def embed_query(self, text: str) -> List[float]:
        """将查询文本转换为嵌入向量"""
        embedding = get_embedding(text)
        # 将numpy数组转换为普通列表
        return embedding.tolist()

class KnowledgeService:
    """知识库服务 - 使用LangChain实现"""
    
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
    
    # 文件类型到加载器的映射
    FILE_LOADERS = {
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".doc": Docx2txtLoader,  # 使用相同的加载器
        ".xlsx": UnstructuredExcelLoader,
        ".xls": UnstructuredExcelLoader,  # 使用相同的加载器
        ".md": UnstructuredMarkdownLoader,
        ".csv": CSVLoader,
        ".json": JSONLoader
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
        
        # 初始化嵌入模型 - 使用自定义嵌入类
        self.embedding_model = CustomEmbeddings()
        
        # 初始化文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.CHUNK_SIZE,
            chunk_overlap=self.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # 初始化向量存储
        self.vectorstore = None
        
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
        
        # 加载FAISS向量存储
        if os.path.exists(self.KNOWLEDGE_INDEX_PATH):
            try:
                self.vectorstore = FAISS.load_local(
                    folder_path=os.path.dirname(self.KNOWLEDGE_INDEX_PATH),
                    index_name=os.path.basename(self.KNOWLEDGE_INDEX_PATH).split('.')[0],
                    embeddings=self.embedding_model,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"已加载知识库向量索引")
            except Exception as e:
                logger.error(f"加载知识库向量索引失败: {str(e)}")
                self._create_new_index()
        else:
            logger.info("知识库向量索引不存在，创建新索引")
            self._create_new_index()
    
    def _create_new_index(self):
        """创建新的向量索引"""
        try:
            # 创建空的FAISS索引，使用占位文本避免空列表错误
            placeholder_text = "初始化占位文本"
            placeholder_embedding = self.embedding_model.embed_query(placeholder_text)
            
            # 创建带有占位文本的索引
            self.vectorstore = FAISS.from_texts(
                texts=[placeholder_text],
                embedding=self.embedding_model,
                metadatas=[{"file_id": "initial", "chunk_id": "initial"}]
            )
            
            # 保存索引
            self._save_index()
            logger.info("创建了新的FAISS索引")
        except Exception as e:
            logger.error(f"创建FAISS索引失败: {str(e)}")
            # 如果创建失败，设置为None，后续可以重试
            self.vectorstore = None
    
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
            if self.vectorstore:
                index_dir = os.path.dirname(self.KNOWLEDGE_INDEX_PATH)
                index_name = os.path.basename(self.KNOWLEDGE_INDEX_PATH).split('.')[0]
                self.vectorstore.save_local(index_dir, index_name)
            
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
            self._process_file(file_id, save_path, file_ext)
            
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
            file_ext = self.SUPPORTED_FILE_TYPES[content_type]
            
            # 使用合适的加载器加载文件
            try:
                loader_cls = self.FILE_LOADERS.get(file_ext)
                if loader_cls:
                    # 对于需要特殊处理的加载器
                    if file_ext in ['.xlsx', '.xls']:
                        loader = loader_cls(file_path, mode="elements")
                    elif file_ext == '.json':
                        # JSON加载器需要jq_schema参数
                        loader = loader_cls(file_path, jq_schema=".", text_content=True)
                    else:
                        loader = loader_cls(file_path)
                    
                    docs = loader.load()
                    if docs:
                        content = docs[0].page_content
                        return content[:max_length] + ("..." if len(content) > max_length else "")
            except Exception as e:
                logger.warning(f"使用LangChain加载器提取预览失败: {str(e)}，使用备用方法")
            
            # 备用方法: 直接读取文件
            if file_ext in ['.txt', '.md', '.csv']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(max_length * 2)
                    return content[:max_length] + ("..." if len(content) > max_length else "")
            
            elif file_ext == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    content = json.dumps(data, ensure_ascii=False)
                    return content[:max_length] + ("..." if len(content) > max_length else "")
            
            elif file_ext == '.pdf':
                return "[PDF文件内容预览]"
            
            elif file_ext in ['.docx', '.doc']:
                return "[Word文件内容预览]"
            
            elif file_ext in ['.xlsx', '.xls']:
                return "[Excel文件内容预览]"
            
            else:
                return "[文件内容预览不可用]"
                
        except Exception as e:
            logger.error(f"提取文件内容预览失败: {str(e)}")
            return "[提取预览失败]"
    
    def _process_file(self, file_id: str, file_path: str, file_ext: str):
        """处理文件内容，使用LangChain加载文档、分块并生成嵌入向量
        
        Args:
            file_id: 文件ID
            file_path: 文件路径
            file_ext: 文件扩展名
        """
        try:
            # 更新文件状态为处理中
            if file_id in self.files_index:
                self.files_index[file_id]["embedding_status"] = "processing"
                self._save_index()
            
            # 使用LangChain加载文档
            loader_cls = self.FILE_LOADERS.get(file_ext)
            if not loader_cls:
                raise ValueError(f"不支持的文件类型: {file_ext}")
                
            # 对于需要特殊处理的加载器
            if file_ext in ['.xlsx', '.xls']:
                loader = loader_cls(file_path, mode="elements")
            elif file_ext == '.json':
                # JSON加载器需要jq_schema参数，使用"."可以加载整个JSON
                loader = loader_cls(file_path, jq_schema=".", text_content=True)
            else:
                loader = loader_cls(file_path)
                
            documents = loader.load()
            
            # 分割文档
            chunks = self.text_splitter.split_documents(documents)
            
            # 处理文档块
            texts = []
            metadatas = []
            chunk_count = 0
            
            for i, chunk in enumerate(chunks):
                if not chunk.page_content.strip():
                    continue
                    
                # 生成块ID
                chunk_id = f"{file_id}_{i}"
                
                # 保存块信息
                chunk_info = {
                    "chunk_id": chunk_id,
                    "file_id": file_id,
                    "content": chunk.page_content,
                    "chunk_index": i,
                    "embedding_status": "completed",
                    "metadata": {
                        "source": chunk.metadata.get("source", file_path),
                        "page": chunk.metadata.get("page", None)
                    }
                }
                
                self.chunks_index[chunk_id] = chunk_info
                
                # 准备向量存储数据
                texts.append(chunk.page_content)
                metadata = {
                    "chunk_id": chunk_id,
                    "file_id": file_id,
                    "chunk_index": i
                }
                metadatas.append(metadata)
                
                chunk_count += 1
            
            # 添加到向量存储
            if texts:
                if self.vectorstore is None:
                    # 创建新的向量存储
                    self.vectorstore = FAISS.from_texts(
                        texts=texts,
                        embedding=self.embedding_model,
                        metadatas=metadatas
                    )
                else:
                    # 添加到现有向量存储
                    self.vectorstore.add_texts(texts=texts, metadatas=metadatas)
                
                # 保存索引
                index_dir = os.path.dirname(self.KNOWLEDGE_INDEX_PATH)
                index_name = os.path.basename(self.KNOWLEDGE_INDEX_PATH).split('.')[0]
                self.vectorstore.save_local(index_dir, index_name)
            
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
                "items": file_objects,
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
                            "embedding_status": chunk_info.get("embedding_status", "unknown")
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
            
            # 删除文件的文本块和向量
            chunk_ids_to_delete = []
            for chunk_id, chunk_info in self.chunks_index.items():
                if chunk_info["file_id"] == file_id:
                    chunk_ids_to_delete.append(chunk_id)
            
            for chunk_id in chunk_ids_to_delete:
                del self.chunks_index[chunk_id]
            
            # 重建向量存储（LangChain的FAISS实现不支持直接删除向量）
            self._rebuild_vectorstore()
            
            # 保存索引
            self._save_index()
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
    
    def _rebuild_vectorstore(self):
        """重建向量存储"""
        try:
            # 收集所有文本块
            texts = []
            metadatas = []
            
            for chunk_id, chunk_info in self.chunks_index.items():
                texts.append(chunk_info["content"])
                metadatas.append({
                    "chunk_id": chunk_id,
                    "file_id": chunk_info["file_id"],
                    "chunk_index": chunk_info["chunk_index"]
                })
            
            # 创建新的向量存储
            if texts:
                self.vectorstore = FAISS.from_texts(
                    texts=texts,
                    embedding=self.embedding_model,
                    metadatas=metadatas
                )
            else:
                # 如果没有文本，创建空的向量存储
                self.vectorstore = FAISS.from_texts(
                    texts=["Empty index placeholder"],
                    embedding=self.embedding_model,
                    metadatas=[{"chunk_id": "empty", "file_id": "empty", "chunk_index": 0}]
                )
                # 然后删除占位符
                if hasattr(self.vectorstore, 'index') and hasattr(self.vectorstore.index, 'ntotal') and self.vectorstore.index.ntotal > 0:
                    # 创建全新的空索引
                    self.vectorstore = FAISS.from_texts(
                        texts=[],
                        embedding=self.embedding_model,
                        metadatas=[]
                    )
            
            # 保存索引
            index_dir = os.path.dirname(self.KNOWLEDGE_INDEX_PATH)
            index_name = os.path.basename(self.KNOWLEDGE_INDEX_PATH).split('.')[0]
            self.vectorstore.save_local(index_dir, index_name)
            
            logger.info(f"向量存储重建完成，包含 {len(texts)} 个文本块向量")
            
        except Exception as e:
            logger.error(f"重建向量存储失败: {str(e)}")
    
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
            # 检查向量存储是否为空
            if self.vectorstore is None:
                return []
            
            # 使用LangChain向量检索
            search_kwargs = {}
            
            # 如果有文件ID限制，使用过滤器
            if file_ids:
                search_kwargs["filter"] = lambda metadata: metadata["file_id"] in file_ids
            
            # 执行检索
            search_results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=limit,
                **search_kwargs
            )
            
            results = []
            
            for doc, score in search_results:
                # 获取元数据
                metadata = doc.metadata
                chunk_id = metadata.get("chunk_id")
                file_id = metadata.get("file_id")
                
                # 检查文本块是否存在
                if chunk_id not in self.chunks_index:
                    continue
                
                # 检查文件是否存在
                if file_id not in self.files_index:
                    continue
                
                chunk_info = self.chunks_index[chunk_id]
                file_info = self.files_index[file_id]
                
                # 计算相似度 (转换距离为相似度分数)
                similarity = 1 / (1 + score)
                
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
            
            return results
            
        except Exception as e:
            logger.error(f"搜索知识库失败: {str(e)}")
            return []

# 创建全局知识库服务实例
knowledge_service = KnowledgeService()