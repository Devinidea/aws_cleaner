#!/usr/bin/env python3
"""
脚本用于过滤AWS清理日志文件
只保留WARNING级别、Successfully和Completed相关的日志条目，删除其他不需要的信息
"""

import os
import re
import glob
import sys
from datetime import datetime

def filter_log_file(file_path):
    """
    过滤日志文件，只保留关键信息
    """
    print(f"处理日志文件: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 计算原始日志行数
        original_lines = content.splitlines()
        original_count = len(original_lines)
        print(f"  原始日志行数: {original_count}")
        
        # 创建一个新的日志文件名，包含时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.{timestamp}.bak"
        
        # 备份原始日志文件
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  已将原始日志备份到: {backup_path}")
        
        # 过滤出需要保留的行
        filtered_lines = []
        for line in original_lines:
            # 将"Completed"相关的INFO日志转换为WARNING级别
            if " - INFO - Completed" in line:
                # 替换INFO为WARNING
                modified_line = line.replace(" - INFO - ", " - WARNING - ")
                filtered_lines.append(modified_line)
            # 保留所有WARNING级别的日志
            elif " - WARNING -" in line:
                filtered_lines.append(line)
            # 保留包含"Successfully"的日志(应该已经是WARNING级别)
            elif "Successfully" in line:
                filtered_lines.append(line)
        
        # 计算过滤后的行数
        filtered_count = len(filtered_lines)
        removed_count = original_count - filtered_count
        
        # 将过滤后的内容写回原始文件
        filtered_content = "\n".join(filtered_lines)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(filtered_content)
        
        # 统计转换后的日志级别数量
        warning_count = len(re.findall(r' - WARNING -', filtered_content))
        
        # 输出过滤结果统计
        print(f"\n  日志过滤结果:")
        print(f"    原始日志行数: {original_count}")
        print(f"    过滤后行数: {filtered_count}")
        print(f"    移除行数: {removed_count} ({removed_count/original_count*100:.1f}%)")
        print(f"    WARNING级别日志数量: {warning_count}")
        print(f"    保留的信息类型: WARNING级别、包含Successfully和Completed的日志")
        print(f"    原始日志已备份到: {backup_path}")
        
    except Exception as e:
        print(f"  处理文件 {file_path} 时出错: {str(e)}")

def main():
    """
    主函数，处理日志文件
    """
    # 打印当前工作目录和脚本位置
    print(f"当前工作目录: {os.getcwd()}")
    print(f"脚本位置: {os.path.abspath(__file__)}")
    
    # 尝试多种方式查找日志文件
    # 1. 首先尝试直接在当前目录查找
    log_file = os.path.join(os.getcwd(), 'aws_cleanup.log')
    if os.path.exists(log_file):
        print(f"在当前目录找到日志文件: {log_file}")
        filter_log_file(log_file)
        print("日志处理完成！")
        return
    
    # 2. 尝试在上级目录查找
    parent_dir = os.path.dirname(os.getcwd())
    log_file = os.path.join(parent_dir, 'aws_cleanup.log')
    if os.path.exists(log_file):
        print(f"在上级目录找到日志文件: {log_file}")
        filter_log_file(log_file)
        print("日志处理完成！")
        return
    
    # 3. 搜索当前目录及其所有子目录
    print("在当前目录及其子目录中搜索日志文件...")
    log_files = []
    for root, dirs, files in os.walk(os.getcwd()):
        for file in files:
            if file == 'aws_cleanup.log':
                log_path = os.path.join(root, file)
                log_files.append(log_path)
    
    if log_files:
        print(f"找到 {len(log_files)} 个日志文件:")
        for file_path in log_files:
            print(f" - {file_path}")
            filter_log_file(file_path)
        print("日志处理完成！")
        return
    
    # 4. 尝试通过命令行参数指定
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        print(f"使用命令行参数指定的日志文件: {sys.argv[1]}")
        filter_log_file(sys.argv[1])
        print("日志处理完成！")
        return
    
    print("\n*** 未找到aws_cleanup.log文件 ***")
    print("请使用以下方式运行脚本:")
    print("1. 在存在aws_cleanup.log的目录中运行脚本")
    print("2. 或者指定日志文件路径: python update_logging.py /path/to/aws_cleanup.log")
    print("日志查找失败!")

if __name__ == "__main__":
    main() 