#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import asyncio
import json

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from services.chat_service import ChatService
from services.web_search_service import web_search_service
from utils.logger import logger

async def test_chat_with_web_search():
    """测试启用web搜索的聊天功能"""
    print("="*50)
    print("测试启用web搜索的聊天功能")
    print("="*50)
    
    # 初始化聊天服务
    chat_service = ChatService()
    
    # 测试消息
    test_message = "2024年人工智能的最新进展有哪些？"
    
    print(f"测试消息: {test_message}")
    print(f"Web搜索服务状态: 启用={web_search_service.enabled}, 可用={web_search_service.is_available()}")
    
    # 尝试获取聊天响应
    try:
        response = await chat_service.get_chat_response(
            message=test_message,
            use_memory=False,  # 禁用记忆功能，专注测试web搜索
            use_knowledge=False,  # 禁用知识库，专注测试web搜索
            use_web_search=True,  # 启用web搜索
            web_search_limit=3  # 限制结果数量
        )
        
        print("\n聊天响应成功!")
        print(f"输入tokens: {response.input_tokens}")
        print(f"输出tokens: {response.output_tokens}")
        print(f"总费用: {response.cost}")
        
        # 检查web_search_used字段
        if response.web_search_used:
            print("\n网络搜索结果:")
            for i, result in enumerate(response.web_search_used, 1):
                print(f"结果 {i}:")
                if isinstance(result, dict):
                    for key, value in result.items():
                        if key == 'snippet':
                            # 截断长文本
                            print(f"  {key}: {value[:100]}..." if len(value) > 100 else f"  {key}: {value}")
                        else:
                            print(f"  {key}: {value}")
                else:
                    print(f"  {result}")
            
            # 打印完整的搜索结果（JSON格式）
            print("\n完整的web_search_used (JSON格式):")
            print(json.dumps(response.web_search_used, ensure_ascii=False, indent=2))
        else:
            print("\n无网络搜索结果")
        
        # 打印回复内容（部分）
        print("\nAI回复 (前200字符):")
        print(f"{response.message[:200]}..." if len(response.message) > 200 else response.message)
        
    except Exception as e:
        print(f"聊天响应失败: {str(e)}")
    
    print("="*50)

if __name__ == "__main__":
    # 运行异步测试函数
    asyncio.run(test_chat_with_web_search()) 