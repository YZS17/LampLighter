#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import re
import argparse

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
    # 创建一个掩码，标记不包含任何IP的行
    mask = df.iloc[:, col_index].apply(
        lambda x: not any(ip in str(x) for ip in ip_set) if pd.notna(x) else True
    )
    
    return df[mask]

def extract_and_format_ips(df, city, col_index=3):
    """从表格中提取IP地址并转换为CIDR格式"""
    # Extract IPv4 addresses and convert to CIDR notation
    ip_cidrs = set()  # Use a set to automatically remove duplicates
    
    ipv4_pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    
    for cell in df.iloc[:, col_index]:
        if not isinstance(cell, str) and not pd.isna(cell):
            cell = str(cell)
            
        if pd.isna(cell):
            continue
            
        matches = re.findall(ipv4_pattern, cell)
        for ip in matches:
            # Split IP into octets and replace the last one with "0/24"
            octets = ip.split('.')
            if len(octets) == 4:
                cidr = f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
                ip_cidrs.add(cidr)
    
    # Format the output
    if not ip_cidrs:
        return "No IPv4 addresses found"
    
    ip_output = " || ".join([f'ip="{cidr}"' for cidr in sorted(ip_cidrs)])
    output = f"{ip_output} && status_code=\"200\" && domain=\"\" && city=\"{city}\""
    return output

def process_excel(file1, file2, excel_output=None):
    """仅执行execl.py的功能：从第一个表格提取IP并过滤第二个表格"""
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
    
    # 从第一个表格提取IP并过滤第二个表格
    ip_set = extract_ip_from_column(df1)
    filtered_df = filter_table_by_ip(df2, ip_set)
    
    # 保存过滤后的Excel (如果需要)
    if excel_output:
        filtered_df.to_excel(excel_output, index=False)
        print(f"过滤后的Excel已保存到 {excel_output}")
    else:
        print("过滤后的表格:")
        print(filtered_df)
    
    return filtered_df

def process_extract(file, city, text_output=None):
    """仅执行extract_ip_cidr.py的功能：从表格提取IP并转换为CIDR"""
    # 读取Excel文件
    try:
        df = pd.read_excel(file)
    except Exception as e:
        print(f"读取文件错误: {e}")
        return None
    
    # 检查表格是否有足够的列
    if len(df.columns) < 4:
        print("错误: 表格没有4列")
        return None
    
    # 从表格提取IP并转换为CIDR
    cidr_result = extract_and_format_ips(df, city)
    
    # 保存CIDR结果 (如果需要)
    if text_output:
        with open(text_output, 'w', encoding='utf-8') as f:
            f.write(cidr_result)
        print(f"CIDR结果已保存到 {text_output}")
    else:
        print("CIDR结果:")
        print(cidr_result)
    
    return cidr_result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='处理Excel表格并提取CIDR格式IP')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # Excel过滤功能命令
    excel_parser = subparsers.add_parser('excel', help='仅执行Excel过滤功能')
    excel_parser.add_argument('file1', help='第一个Excel文件路径（包含要排除的IP）')
    excel_parser.add_argument('file2', help='第二个Excel文件路径（要处理的文件）')
    excel_parser.add_argument('-o', '--output', help='过滤后的Excel输出路径（可选）')
    
    # CIDR提取功能命令
    extract_parser = subparsers.add_parser('extract', help='仅执行CIDR提取功能')
    extract_parser.add_argument('file', help='Excel文件路径')
    extract_parser.add_argument('--city', required=True, help='城市名称（用于CIDR输出）')
    extract_parser.add_argument('-o', '--output', help='CIDR结果输出路径（可选）')
    
    args = parser.parse_args()
    
    if args.command == 'excel':
        process_excel(args.file1, args.file2, args.output)
    elif args.command == 'extract':
        process_extract(args.file, args.city, args.output)
    else:
        parser.print_help() 