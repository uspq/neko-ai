import os
import pickle
import numpy as np
import faiss
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from core.config import settings
from utils.logger import logger
from models.memory import Memory

class FAISSMemoryStore:
    def __init__(self, dimension=None, index_type=None, index_path=None):
        self.dimension = dimension or settings.FAISS_DIMENSION
        self.index_type = index_type or settings.FAISS_INDEX_TYPE
        self.index_path = index_path or settings.FAISS_INDEX_PATH
        self.texts = []
        
        # 尝试加载现有索引
        if os.path.exists(self.index_path):
            try:
                logger.info(f"加载FAISS索引文件: {self.index_path}")
                with open(self.index_path, 'rb') as f:
                    data = pickle.load(f)
                    self.index = data['index']
                    self.texts = data.get('texts', [])
                logger.info(f"FAISS索引加载成功，包含 {len(self.texts)} 条记忆")
            except Exception as e:
                logger.error(f"加载FAISS索引失败: {str(e)}")
                self._create_new_index()
        else:
            logger.info(f"FAISS索引文件不存在，创建新索引")
            self._create_new_index()
            # 立即保存空索引，避免下次启动时再次提示
            self.save_index()
            logger.info(f"已创建并保存新的FAISS索引")
    
    def _create_new_index(self):
        """创建新的FAISS索引"""
        if self.index_type.lower() == "flat":
            self.index = faiss.IndexFlatL2(self.dimension)
        elif self.index_type.lower() == "ivf":
            # IVF索引需要训练，这里使用简单的随机数据
            quantizer = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            # 生成随机训练数据
            np.random.seed(42)
            train_data = np.random.random((1000, self.dimension)).astype('float32')
            self.index.train(train_data)
        else:
            # 默认使用Flat索引
            self.index = faiss.IndexFlatL2(self.dimension)
        
        self.texts = []

    def save_index(self):
        """保存索引到文件"""
        try:
            # 确保目录存在
            index_dir = os.path.dirname(self.index_path)
            if index_dir and not os.path.exists(index_dir):
                os.makedirs(index_dir)
                
            with open(self.index_path, 'wb') as f:
                pickle.dump({'index': self.index, 'texts': self.texts}, f)
            logger.info(f"FAISS索引已保存，包含 {len(self.texts)} 条记忆")
            return True
        except Exception as e:
            logger.error(f"保存FAISS索引失败: {str(e)}", exc_info=True)
            return False

    def add_text(self, text: str, embedding: np.ndarray, timestamp: str, conversation_id: int = None):
        """添加新的记忆到FAISS索引
        
        Args:
            text: 完整对话文本 (格式: "用户: xxx\n助手: xxx")
            embedding: 文本的向量表示
            timestamp: 时间戳，作为唯一标识
            conversation_id: 对话ID，默认为None表示全局记忆
        """
        try:
            logger.info(f"添加新记忆到FAISS，时间戳: {timestamp}, 对话ID: {conversation_id or '全局'}")
            logger.debug(f"记忆文本长度: {len(text)}, 向量维度: {embedding.shape if hasattr(embedding, 'shape') else 'unknown'}")
            
            # 确保存储完整对话内容以及对话ID
            self.texts.append({
                "text": text,
                "timestamp": timestamp,
                "conversation_id": conversation_id
            })
            
            # 确保embedding是正确的numpy数组格式
            if not isinstance(embedding, np.ndarray):
                logger.warning(f"向量不是numpy数组，正在转换，类型: {type(embedding)}")
                embedding = np.array(embedding, dtype=np.float32)
                
            if len(embedding.shape) == 1:
                embedding = embedding.reshape(1, -1)
                
            if embedding.dtype != np.float32:
                embedding = embedding.astype(np.float32)
                
            # 检查维度
            if embedding.shape[1] != self.dimension:
                logger.warning(f"向量维度不匹配，预期: {self.dimension}, 实际: {embedding.shape[1]}")
                if embedding.shape[1] > self.dimension:
                    embedding = embedding[:, :self.dimension]
                else:
                    # 填充向量
                    padding = np.zeros((1, self.dimension - embedding.shape[1]), dtype=np.float32)
                    embedding = np.hstack((embedding, padding))
                
            # 添加到索引
            self.index.add(embedding)
            
            # 每100个记忆保存一次索引，或总数量小于100时每次保存
            total_memories = len(self.texts)
            if total_memories % 100 == 0 or total_memories < 100:
                save_success = self.save_index()
                if save_success:
                    logger.info(f"成功保存FAISS索引，总记忆数: {total_memories}")
                else:
                    logger.error(f"保存FAISS索引失败，总记忆数: {total_memories}")
            
            logger.info(f"已保存新记忆，当前共有 {len(self.texts)} 条记忆，对话ID: {conversation_id or '全局'}")
            return True
            
        except Exception as e:
            logger.error(f"添加文本到FAISS索引失败: {str(e)}", exc_info=True)
            return False
            
    def add_texts_batch(self, texts: List[str], embeddings: np.ndarray, timestamps: List[str], 
                        conversation_ids: List[Optional[int]] = None):
        """批量添加记忆到FAISS索引
        
        Args:
            texts: 完整对话文本列表
            embeddings: 文本的向量表示矩阵（二维numpy数组）
            timestamps: 时间戳列表
            conversation_ids: 对话ID列表，None元素表示全局记忆
            
        Returns:
            bool: 操作是否成功
        """
        try:
            if conversation_ids is None:
                conversation_ids = [None] * len(texts)
                
            logger.info(f"批量添加 {len(texts)} 条记忆到FAISS")
            
            # 确保embeddings是二维数组
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)
                
            # 确保数据类型正确
            if embeddings.dtype != np.float32:
                embeddings = embeddings.astype(np.float32)
                
            # 检查维度
            if embeddings.shape[1] != self.dimension:
                logger.warning(f"批量向量维度不匹配，预期: {self.dimension}, 实际: {embeddings.shape[1]}")
                if embeddings.shape[1] > self.dimension:
                    embeddings = embeddings[:, :self.dimension]
                else:
                    # 填充向量
                    padding = np.zeros((embeddings.shape[0], self.dimension - embeddings.shape[1]), dtype=np.float32)
                    embeddings = np.hstack((embeddings, padding))
            
            # 添加文本记录
            for i, (text, timestamp, conv_id) in enumerate(zip(texts, timestamps, conversation_ids)):
                self.texts.append({
                    "text": text,
                    "timestamp": timestamp,
                    "conversation_id": conv_id
                })
                
            # 添加到索引
            self.index.add(embeddings)
            
            # 保存索引
            save_success = self.save_index()
            if save_success:
                logger.info(f"批量添加成功并保存索引，当前总记忆数: {len(self.texts)}")
            else:
                logger.error(f"批量添加成功但保存索引失败，当前总记忆数: {len(self.texts)}")
                
            return True
            
        except Exception as e:
            logger.error(f"批量添加文本到FAISS索引失败: {str(e)}", exc_info=True)
            return False

    def search(self, query_embedding: np.ndarray, k=3, conversation_id: int = None) -> List[Memory]:
        """搜索相似记忆
        
        Args:
            query_embedding: 查询向量
            k: 返回结果数量
            conversation_id: 限定搜索范围的对话ID，None表示搜索全部
            
        Returns:
            List[Memory]: 相似记忆列表
        """
        if self.index.ntotal == 0:
            logger.info("FAISS索引为空，无法搜索")
            return []
            
        logger.info(f"FAISS搜索: k={k}, 对话ID={conversation_id or '全部'}, 索引大小={self.index.ntotal}")
        
        try:
            # 确保查询向量的维度正确
            original_shape = query_embedding.shape
            
            # 如果是1D数组，转换为2D
            if len(original_shape) == 1:
                logger.debug(f"将1D查询向量 {original_shape} 转换为2D")
                query_embedding = query_embedding.reshape(1, -1)
                
            # 检查维度并处理不匹配情况
            if query_embedding.shape[1] != self.dimension:
                logger.warning(f"查询向量维度不匹配。预期: {self.dimension}, 实际: {query_embedding.shape[1]}")
                
                # 尝试调整维度
                if query_embedding.shape[1] > self.dimension:
                    # 截断维度
                    logger.info(f"截断查询向量维度从 {query_embedding.shape[1]} 到 {self.dimension}")
                    query_embedding = query_embedding[:, :self.dimension]
                else:
                    # 填充维度
                    logger.info(f"填充查询向量维度从 {query_embedding.shape[1]} 到 {self.dimension}")
                    padding = np.zeros((1, self.dimension - query_embedding.shape[1]), dtype=np.float32)
                    query_embedding = np.hstack((query_embedding, padding))
            
            # 确保数据类型正确
            if query_embedding.dtype != np.float32:
                logger.debug(f"将查询向量类型从 {query_embedding.dtype} 转换为 float32")
                query_embedding = query_embedding.astype(np.float32)
            
            # 搜索最相似的k个向量
            search_k = min(k * 3, self.index.ntotal)  # 多搜索一些，后面可能会过滤
            logger.debug(f"FAISS搜索 k={search_k} (原始k={k})")
            
            distances, indices = self.index.search(query_embedding, search_k)
            
            # 预处理结果
            search_results = []
            
            for i, idx in enumerate(indices[0]):
                if idx < len(self.texts) and idx >= 0:
                    text = self.texts[idx]["text"]
                    timestamp = self.texts[idx]["timestamp"]
                    item_conversation_id = self.texts[idx].get("conversation_id")
                    
                    # 将L2距离转换为相似度分数（0-1之间）
                    distance = distances[0][i]
                    similarity = 1.0 / (1.0 + distance)
                    
                    # 如果指定了对话ID，只返回对应对话的记忆
                    if conversation_id is not None and item_conversation_id != conversation_id:
                        logger.debug(f"跳过不匹配对话ID的记忆: {timestamp}, 对话ID={item_conversation_id}")
                        continue
                        
                    # 解析存储的文本
                    parts = text.split("\n助手: ")
                    if len(parts) == 2:
                        user_message = parts[0].replace("用户: ", "")
                        ai_response = parts[1]
                        
                        memory = Memory(
                            user_message=user_message,
                            ai_response=ai_response,
                            timestamp=timestamp,
                            similarity=similarity,
                            conversation_id=item_conversation_id
                        )
                        search_results.append(memory)
                        
                        logger.debug(f"FAISS找到记忆: {timestamp}, 相似度={similarity:.4f}, 距离={distance:.4f}")
                else:
                    logger.warning(f"FAISS索引不匹配: {idx} >= {len(self.texts)} 或 {idx} < 0")
            
            # 按相似度从高到低排序
            search_results.sort(key=lambda x: x.similarity, reverse=True)
            
            # 限制返回数量
            final_results = search_results[:k]
            
            logger.info(f"FAISS搜索完成: 找到 {len(final_results)}/{len(search_results)} 条相关记忆")
            
            return final_results
            
        except Exception as e:
            logger.error(f"FAISS搜索失败: {str(e)}", exc_info=True)
            return []

    def clear_memory(self, conversation_id: Optional[int] = None):
        """清除记忆数据
        
        Args:
            conversation_id: 指定要清除的对话ID，None表示清除所有记忆
        """
        if conversation_id is None:
            # 清除所有记忆
            self.index = faiss.IndexFlatL2(self.dimension)
            self.texts = []
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            logger.info("已清除所有FAISS记忆数据")
        else:
            # 只清除指定对话的记忆
            # 需要重建索引，先找出要保留的记忆
            retained_texts = []
            retained_embeddings = []
            
            for i, item in enumerate(self.texts):
                item_conversation_id = item.get("conversation_id")
                # 保留不匹配的对话ID或全局记忆(None)
                if item_conversation_id != conversation_id:
                    retained_texts.append(item)
                    
                    # 从FAISS索引中获取对应的向量
                    if i < self.index.ntotal:
                        vector = np.array([self.index.reconstruct(i)])  # 获取原始向量
                        retained_embeddings.append(vector)
            
            # 创建新索引并添加保留的向量
            self._create_new_index()
            if retained_embeddings:
                retained_embeddings = np.vstack(retained_embeddings)
                self.index.add(retained_embeddings)
            
            # 更新文本记录
            self.texts = retained_texts
            self.save_index()
            
            logger.info(f"已清除对话 {conversation_id} 的FAISS记忆数据，保留 {len(retained_texts)} 条记忆")

    def get_memory_by_timestamp(self, timestamp: str) -> Optional[Memory]:
        """根据时间戳获取完整记忆
        
        Args:
            timestamp: 记忆的时间戳
            
        Returns:
            Optional[Memory]: 找到的记忆对象，未找到则返回None
        """
        for item in self.texts:
            if item.get("timestamp") == timestamp:
                text = item["text"]
                conversation_id = item.get("conversation_id")
                parts = text.split("\n助手: ")
                if len(parts) == 2:
                    user_message = parts[0].replace("用户: ", "")
                    ai_response = parts[1]
                    return Memory(
                        user_message=user_message,
                        ai_response=ai_response,
                        timestamp=timestamp,
                        conversation_id=conversation_id
                    )
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """获取FAISS存储统计信息"""
        stats = {
            "count": len(self.texts),
            "size_mb": 0,
            "conversation_counts": {}
        }
        
        # 统计每个对话的记忆数量
        for item in self.texts:
            conversation_id = item.get("conversation_id") or "global"
            if conversation_id in stats["conversation_counts"]:
                stats["conversation_counts"][conversation_id] += 1
            else:
                stats["conversation_counts"][conversation_id] = 1
        
        if os.path.exists(self.index_path):
            stats["size_mb"] = os.path.getsize(self.index_path) / (1024 * 1024)
        
        return stats

    def get_paged_memories(self, page: int = 1, page_size: int = 10, 
                          sort_by: str = "timestamp", sort_desc: bool = True,
                          conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """分页获取记忆
        
        Args:
            page: 页码，从1开始
            page_size: 每页条数
            sort_by: 排序字段，可选值: timestamp, similarity
            sort_desc: 是否降序排序
            conversation_id: 对话ID过滤
            
        Returns:
            Dict: 包含分页数据和分页信息
        """
        if not self.texts:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "conversation_id": conversation_id
            }
        
        # 确保页码有效
        if page < 1:
            page = 1
            
        # 确保每页条数有效
        if page_size < 1:
            page_size = 10
        
        # 限制每页最大条数
        max_page_size = getattr(settings, "RETRIEVAL_MAX_PAGE_SIZE", 100)
        if page_size > max_page_size:
            page_size = max_page_size
            
        # 创建全部记忆的列表并提取信息
        memories = []
        for item in self.texts:
            # 如果指定了对话ID过滤，则跳过不匹配的记忆
            if conversation_id is not None and item.get("conversation_id") != conversation_id:
                continue
                
            text = item["text"]
            timestamp = item["timestamp"]
            item_conversation_id = item.get("conversation_id")
            parts = text.split("\n助手: ")
            
            if len(parts) == 2:
                user_message = parts[0].replace("用户: ", "")
                ai_response = parts[1]
                
                memory = {
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "timestamp": timestamp,
                    "conversation_id": item_conversation_id
                }
                memories.append(memory)
        
        # 按指定字段排序
        if sort_by not in ["timestamp"]:  # 目前只支持按时间戳排序
            sort_by = "timestamp"
            
        memories.sort(key=lambda x: x[sort_by], reverse=sort_desc)
        
        # 计算分页信息
        total = len(memories)
        total_pages = (total + page_size - 1) // page_size
        
        # 获取当前页的数据
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)
        
        page_items = memories[start_idx:end_idx] if start_idx < total else []
        
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "conversation_id": conversation_id
        }

# 创建全局FAISS存储实例
memory_store = FAISSMemoryStore() 