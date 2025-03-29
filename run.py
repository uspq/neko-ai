#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
启动脚本
"""

import os
import sys

# 将当前目录添加到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 初始化数据库
from utils.db_init import init_all_databases
print("正在初始化数据库...")
init_result = init_all_databases()
if not init_result:
    print("警告: 数据库初始化未完全成功，服务可能无法正常工作")
else:
    print("数据库初始化成功")
# 清理日志
from utils.clean_logs import clean_logs
print("正在清理日志文件...")
clean_logs()
print("日志清理完成")


# 导入main模块
import main

# 执行
if __name__ == "__main__":
    main.start() 