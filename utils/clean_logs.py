#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
清理日志文件脚本
在每次运行前清空logs目录中的所有日志文件
"""

import os
import sys
import glob

def clean_logs():
    """清理logs目录中的所有日志文件"""
    # 获取根目录
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    logs_dir = os.path.join(root_dir, "logs")
    
    if not os.path.exists(logs_dir):
        print(f"创建logs目录: {logs_dir}")
        os.makedirs(logs_dir)
        return
    
    # 获取所有日志文件
    log_files = glob.glob(os.path.join(logs_dir, "*.log"))
    log_files.extend(glob.glob(os.path.join(logs_dir, "*.log.*")))
    
    if not log_files:
        print("没有找到需要清理的日志文件")
        return
    
    # 清空每个日志文件
    for log_file in log_files:
        try:
            # 打开文件并清空内容
            with open(log_file, 'w', encoding='utf-8') as f:
                f.truncate(0)
            print(f"已清空日志文件: {os.path.basename(log_file)}")
        except Exception as e:
            print(f"清空日志文件 {os.path.basename(log_file)} 失败: {str(e)}")

if __name__ == "__main__":
    print("开始清理日志文件...")
    clean_logs()
    print("日志清理完成") 