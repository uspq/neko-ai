#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
启动脚本
"""

import os
import sys

# 将当前目录添加到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入app包
import app.main

# 执行
if __name__ == "__main__":
    app.main.start() 