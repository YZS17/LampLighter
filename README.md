# LampLighter 1.0
LampLighter是一个网络安全信息收集与分析工具，此工具分析来自IP地址列表的网站，判断它们是否属于特定公司或企业。基于大语言模型，工具能够智能分析网站内容并生成详细报告。
集成了多种功能，包括FOFA查询、网站分析、漏洞扫描等。部分fofa代码参照FofaMap项目进行二开。
## 设置

1. 安装所需依赖:
   ```
   pip install -r requirements.txt
   ```

2. 配置保存在`config.py`中，包括:
   - OpenAI API配置（API密钥、默认模型等）
   - OCR设置
   - 分析设置（如超时时间）
   
   **重要**: 使用前请确保在`config.py`中填入您的OpenAI API密钥。

3. 请确保正确配置`fofa.ini`文件，
- 包含以下内容：

```ini
[logger]
logger = on

[full]
full = true

[fast_check]
check_alive = on
timeout = 5

[excel]
sheet_merge = on

[page]
start_page = 1
end_page = 2

[size]
size = 100

[fields]
fields = title,ip,port,protocol,domain,icp,province,city
```

## 功能特点
- 从Excel文件的第二列读取IP地址/主机信息
- 获取网站内容（支持HTTP和HTTPS）
- 截图并进行OCR图像文本识别
- 使用OpenAI API对网站内容进行智能分析
- 支持自定义OpenAI模型选择
- 每次运行结果保存在带时间戳的独立目录中，避免覆盖
- 生成详细HTML报告，包含所有分析过程和结果
- 显示LLM交互过程和分析结果
- **FOFA查询**：支持多种查询方式，包括关键词查询、批量查询、聚合查询等
- **网站分析**：分析网站内容，判断网站是否属于特定公司
- **漏洞扫描**：集成Nuclei引擎进行漏洞扫描
- **数据导出**：支持多种格式的数据导出，包括Excel、文本等
- **组合处理**：支持Excel文件处理和IP地址提取

## 使用方法

### 基本查询

```bash
# 关键词查询
python LampLighter.py -q "title=\"beijing\""

# 指定查询字段
python LampLighter.py -q "title=\"beijing\"" -f "title,ip,port,protocol,domain,icp,province,city"

# 指定输出文件
python LampLighter.py -q "title=\"beijing\"" -o "beijing_results.xlsx"
```

### 批量查询

```bash
# 批量查询
python LampLighter.py -bq "batch_query.txt"

# 批量主机查询
python LampLighter.py -bhq "batch_host.txt"
```

### 聚合查询

```bash
# 主机聚合查询
python LampLighter.py -hq "example.com"

# 统计聚合查询
python LampLighter.py -cq "title=\"beijing\"" -f "title,ip,port,protocol,domain,icp,province,city"
```

### 网站图标查询

```bash
# 网站图标查询
python LampLighter.py -ico "https://example.com"
```

### 漏洞扫描

```bash
# 使用Nuclei进行漏洞扫描
python LampLighter.py -q "title=\"beijing\"" -s -n

# 更新Nuclei
python LampLighter.py -up
```

### 组合脚本处理

```bash
# 处理两个Excel文件并提取CIDR
python LampLighter.py --combined --file1 first.xlsx --file2 second.xlsx --city 北京

# 指定输出文件
python LampLighter.py --combined --file1 first.xlsx --file2 second.xlsx --city 北京 -e filtered.xlsx -t output.txt
```

### 网站分析

```bash
# 分析网站是否属于特定公司
python LampLighter.py --analyze --outfile targets.xlsx --target_company "目标公司"

# 指定OpenAI模型
python LampLighter.py --analyze --outfile targets.xlsx --target_company "目标公司" --model "gpt-4"
```

## 参数说明

### 基本参数

- `-q, --query`: FOFA查询语句
- `-hq, --host_query`: 主机聚合查询
- `-bq, --bat_query`: FOFA批量查询
- `-bhq, --bat_host_query`: FOFA批量主机查询
- `-cq, --count_query`: FOFA统计查询
- `-f, --query_fields`: FOFA查询字段，默认为"title"
- `-i, --include`: 指定包含的HTTP协议状态码
- `-kw, --key_word`: 过滤用户指定内容
- `-ico, --icon_query`: FOFA网站图标查询
- `-s, --scan_format`: 输出扫描格式
- `-o, --outfile`: 文件保存名称，默认为"fofa查询结果.xlsx"
- `-n, --nuclie`: 使用Nuclei扫描目标
- `-up, --update`: 一键更新Nuclei引擎和模板

### 组合脚本参数

- `--combined`: 运行组合脚本处理
- `--file1`: 第一个Excel文件路径（包含要排除的IP）
- `--file2`: 第二个Excel文件路径（要处理的文件）
- `--city`: 城市名称（用于CIDR输出）
- `-e, --excel_output`: 过滤后的Excel输出路径
- `-t, --text_output`: CIDR结果输出路径

### 网站分析参数

- `--analyze`: 运行网站分析
- `--target_company`: 目标公司名称
- `--model`: 用于分析的OpenAI或deepseek等模型

## 输出示例

### FOFA查询结果

```
======查询内容=======
[+] 查询语句：title="beijing"
[+] 查询参数：title,ip,port,protocol,domain,icp,province,city
[+] 查询页数：1-2

======查询结果=======
+----+------------------+------+----------+--------+------+---------+--------+
| ID |      title      |  ip  |   port   |protocol|domain|  icp    |province|
+----+------------------+------+----------+--------+------+---------+--------+
|  1 | 北京市政府网站  | 1.2.3.4| 80      | http   | gov.cn| 京ICP备 | 北京   |
+----+------------------+------+----------+--------+------+---------+--------+
```

### 网站分析结果

网站分析结果将保存在`output/analysis_YYYYMMDD_HHMMSS`目录下，包括：

- 详细的分析报告（HTML格式）
- 截图和图像分析
- Excel格式的结果汇总

## 注意事项

1. 使用前请确保已正确配置FOFA API密钥
2. 网站分析功能需要OpenAI API密钥
3. 漏洞扫描功能需要安装Nuclei引擎
4. 部分功能可能需要管理员权限

## 许可证

MIT License

## 作者

XU17 