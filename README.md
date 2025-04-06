# LampLighter

这个工具分析来自IP地址列表的网站，判断它们是否属于特定公司或企业。通过OpenAI API，工具能够智能分析网站内容并生成详细报告。

## 功能特点

- 从Excel文件的第二列读取IP地址/主机信息
- 获取网站内容（支持HTTP和HTTPS）
- 截图并进行OCR图像文本识别
- 使用OpenAI API对网站内容进行智能分析
- 支持自定义OpenAI模型选择
- 每次运行结果保存在带时间戳的独立目录中，避免覆盖
- 生成详细HTML报告，包含所有分析过程和结果
- 显示LLM交互过程和分析结果

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

## 使用方法

运行工具的命令:

```
python website_analyzer.py <excel文件> <目标公司名称> [--model <模型名称>]
```

### 参数说明:

- `<excel文件>`: 包含IP地址/主机信息的Excel文件路径（主机信息在第二列）
- `<目标公司名称>`: 要检查的目标公司名称
- `--model`: 可选参数，指定要使用的OpenAI模型，不指定则使用config.py中的默认模型

### 示例:

```
python website_analyzer.py "fofa查询结果-1743941795.xlsx" "腾讯"
```

使用特定模型的示例:

```
python website_analyzer.py "fofa查询结果-1743941795.xlsx" "腾讯" --model "gpt-4-turbo"
```

## 输出结果

该工具会:

1. 在控制台和`analysis.log`中生成日志信息
2. 在`output`目录下创建带时间戳的子目录（例如：`output/analysis_20231225_123456/`），其中包含:
   - `<目标公司>_analysis_results.xlsx`: 包含详细分析结果的Excel文件
   - `reports/`: 包含每个网站的HTML详细报告
   - `reports/<目标公司>_summary_report.html`: 所有分析结果的汇总HTML报告
   - `images/`: 网站截图和识别的图像

## 分析报告包含:

- IP地址/主机信息
- 是否可访问
- 页面标题
- 是否属于目标公司的判断
- 置信度分数(0-100)
- 判断依据
- 在页面上找到的公司标识
- 网站截图和源代码
- OCR提取的文本
- 与LLM的完整交互过程 