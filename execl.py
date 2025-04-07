#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import re

def extract_ip_from_column(df, col_index=3):
    """从指定列中提取IP地址"""
    ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    ip_set = set()
    
    for cell in df.iloc[:, col_index]:
        if pd.isna(cell):
            continue
        matches = re.findall(ip_pattern, str(cell))
        ip_set.update(matches)
    
    return ip_set

def filter_table_by_ip(df, ip_set, col_index=3):
    """根据IP集合过滤表格，去除包含这些IP的行"""
    ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    
    # 创建一个掩码，标记不包含任何IP的行
    mask = df.iloc[:, col_index].apply(
        lambda x: not any(ip in str(x) for ip in ip_set) if pd.notna(x) else True
    )
    
    return df[mask]

def process_tables(file1, file2, output_file=None):
    """处理两个表格文件"""
    # 读取两个Excel文件
    try:
        df1 = pd.read_excel(file1)
        df2 = pd.read_excel(file2)
    except Exception as e:
        print(f"读取文件错误: {e}")
        return None
    
    # 检查表格是否有足够的列
    if len(df1.columns) < 4 or len(df2.columns) < 4:
        print("错误: 至少一个表格没有4列")
        return None
    
    # 从第一个表格提取IP
    ip_set = extract_ip_from_column(df1)
    
    # 过滤第二个表格
    filtered_df = filter_table_by_ip(df2, ip_set)
    
    # 输出结果
    if output_file:
        filtered_df.to_excel(output_file, index=False)
        print(f"结果已保存到 {output_file}")
    else:
        print("处理后的表格:")
        print(filtered_df)
    
    return filtered_df

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='处理两个Excel表格，基于IP过滤')
    parser.add_argument('file1', help='第一个Excel文件路径')
    parser.add_argument('file2', help='第二个Excel文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径(可选)')
    
    args = parser.parse_args()
    
    process_tables(args.file1, args.file2, args.output)