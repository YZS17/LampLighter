#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import pandas as pd
import argparse

def extract_and_format_ips(excel_file):
    # Read the Excel file
    df = pd.read_excel(excel_file)
    
    # Get the 4th column (index 3)
    if len(df.columns) < 4:
        print("Error: Excel file doesn't have at least 4 columns")
        return ""
    
    ip_column = df.iloc[:, 3]  # 4th column (0-indexed)
    
    # Extract IPv4 addresses and convert to CIDR notation
    ip_cidrs = set()  # Use a set to automatically remove duplicates
    
    ipv4_pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    
    for cell in ip_column:
        if not isinstance(cell, str):
            continue
            
        matches = re.findall(ipv4_pattern, str(cell))
        for ip in matches:
            # Split IP into octets and replace the last one with "0/24"
            octets = ip.split('.')
            if len(octets) == 4:
                cidr = f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
                ip_cidrs.add(cidr)
    
    # Format the output
    if not ip_cidrs:
        return "No IPv4 addresses found"
    
    output = " || ".join([f'ip="{cidr}"' for cidr in sorted(ip_cidrs)])
    return output

def main():
    parser = argparse.ArgumentParser(description='Extract IPv4 addresses from Excel and convert to CIDR notation')
    parser.add_argument('excel_file', help='Path to the Excel file')
    parser.add_argument('-o', '--output', help='Output file path (optional)')
    
    args = parser.parse_args()
    
    result = extract_and_format_ips(args.excel_file)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Results written to {args.output}")
    else:
        print(result)

if __name__ == "__main__":
    main() 