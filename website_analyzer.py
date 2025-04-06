import pandas as pd
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import argparse
import time
import sys
import logging
import json
import os
from urllib.parse import urlparse, urljoin
import config
import cv2
import pytesseract
import easyocr
from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analysis.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize OCR readers
ocr_reader = None
if hasattr(config, 'use_easyocr') and config.use_easyocr:
    try:
        logger.info(f"Initializing EasyOCR with languages: {config.easyocr_languages} (GPU disabled)")
        
        ocr_reader = easyocr.Reader(
            config.easyocr_languages if hasattr(config, 'easyocr_languages') else ['ch_sim', 'en'],
            gpu=False  # 强制不使用GPU
        )
        logger.info("EasyOCR initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing EasyOCR: {e}")
else:
    # Configure Tesseract OCR as fallback
    if hasattr(config, 'tesseract_cmd') and os.path.exists(config.tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd
        logger.info(f"Using Tesseract OCR from: {config.tesseract_cmd}")
    else:
        logger.warning("Tesseract OCR path not found or not configured. OCR may not work properly.")

class WebsiteAnalyzer:
    def __init__(self, output_dir=None):
        # Configure OpenAI client
        self.client = OpenAI(
            api_key=config.openai_key,
            base_url=config.api_base,
        )
        self.model = config.model
        self.timeout = config.timeout
        self.max_retries = config.max_retries
        
        # Setup output directory with timestamp
        if output_dir:
            self.output_dir = output_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = os.path.join('output', f'analysis_{timestamp}')
        
        # Create output directory structure
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'images'), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, 'reports'), exist_ok=True)
        
        # Setup browser for screenshots and full page rendering
        self.setup_browser()

    def setup_browser(self):
        """Setup headless browser for screenshots and rendering"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # 忽略SSL证书错误
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        try:
            # 使用配置文件中指定的ChromeDriver路径
            if os.path.exists(config.chrome_driver_path):
                logger.info(f"Using ChromeDriver from: {config.chrome_driver_path}")
                service = Service(executable_path=config.chrome_driver_path)
                self.driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )
            else:
                # 如果指定路径不存在，尝试自动下载
                logger.warning(f"ChromeDriver not found at: {config.chrome_driver_path}, trying automatic download")
                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
            logger.info("Browser setup successful")
        except Exception as e:
            logger.error(f"Browser setup failed: {e}")
            self.driver = None

    def read_excel(self, file_path):
        """Read IP addresses from an Excel file."""
        try:
            df = pd.read_excel(file_path)
            logger.info(f"Successfully read {len(df)} entries from {file_path}")
            
            # Use the second column as specified by the user
            if len(df.columns) > 1:
                ip_column = df.columns[1]  # Get the second column (index 1)
                logger.info(f"Using the second column '{ip_column}' for host information")
            else:
                logger.warning("Excel file has fewer than 2 columns. Using the first column.")
                ip_column = df.columns[0]
                
            return df[ip_column].tolist()
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            return []

    def get_website_content(self, ip):
        """Fetch website content from an IP address and take screenshot."""
        # Check if the IP/host already includes protocol
        if ip.startswith(('http://', 'https://')):
            urls = [ip]  # Already has protocol, use as is
        else:
            urls = [f"http://{ip}", f"https://{ip}"]  # Add protocols
            
        content = {
            "source_code": "", 
            "title": "", 
            "status_code": None,
            "screenshot_path": None,
            "images": [],
            "ocr_text": ""
        }
        
        for url in urls:
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Attempting to fetch {url} (Attempt {attempt+1}/{self.max_retries})")
                    
                    # Basic request to get source code
                    response = requests.get(url, timeout=self.timeout, verify=False)
                    content["status_code"] = response.status_code
                    
                    if response.status_code == 200:
                        content["source_code"] = response.text
                        soup = BeautifulSoup(response.text, 'html.parser')
                        content["title"] = soup.title.string if soup.title else "No title"
                        
                        # Save the source code for inspection
                        domain = urlparse(url).netloc
                        source_file = os.path.join(self.output_dir, 'reports', f"{domain}_source.html")
                        with open(source_file, 'w', encoding='utf-8') as f:
                            f.write(content["source_code"])
                        logger.info(f"Source code saved to {source_file}")
                        
                        # Get screenshot and extract text from images if browser setup was successful
                        if self.driver:
                            content = self.capture_visual_data(url, content, domain)
                        
                        return content, url
                    break
                except requests.RequestException as e:
                    logger.warning(f"Request error for {url}: {e}")
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to connect to {url} after {self.max_retries} attempts")
                    time.sleep(1)
                    continue
        
        return content, None

    def capture_visual_data(self, url, content, domain):
        """Capture screenshot and process images for OCR"""
        try:
            # Navigate to the URL
            self.driver.get(url)
            time.sleep(3)  # Wait for page to fully load
            
            # 检查是否遇到SSL警告页面，尝试点击"高级"和"继续访问"按钮
            try:
                # 尝试查找常见的SSL警告页面元素
                advanced_buttons = self.driver.find_elements("xpath", "//button[contains(text(), '高级') or contains(text(), 'Advanced')]")
                if advanced_buttons:
                    logger.info(f"Found SSL warning page, clicking advanced button")
                    advanced_buttons[0].click()
                    time.sleep(1)
                    
                    # 点击"继续访问"或"Proceed"按钮
                    proceed_buttons = self.driver.find_elements("xpath", 
                        "//a[contains(text(), '继续前往') or contains(text(), '继续访问') or contains(text(), 'Proceed')]")
                    if proceed_buttons:
                        proceed_buttons[0].click()
                        logger.info(f"Clicked proceed button, continuing to insecure site")
                        time.sleep(2)  # 等待页面加载
            except Exception as e:
                logger.warning(f"Error handling SSL warning page: {e}")
            
            # Take full page screenshot
            screenshot_path = os.path.join(self.output_dir, 'images', f"{domain}_screenshot.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
            content["screenshot_path"] = screenshot_path
            
            # Extract and download images for analysis
            image_elements = self.driver.find_elements("tag name", "img")
            logger.info(f"Found {len(image_elements)} images on the page")
            image_ocr_text = []
            
            for i, img in enumerate(image_elements[:10]):  # Limit to first 10 images
                try:
                    img_src = img.get_attribute('src')
                    if not img_src:
                        continue
                    
                    # 跳过base64编码的小图片和图标
                    if img_src.startswith('data:image') and len(img_src) < 1000:
                        continue
                        
                    # Handle relative URLs
                    if not img_src.startswith(('http://', 'https://')):
                        img_src = urljoin(url, img_src)
                    
                    logger.info(f"Processing image {i}: {img_src[:100]}...")
                    
                    # Download and save image
                    try:
                        img_response = requests.get(img_src, timeout=self.timeout, verify=False)
                        if img_response.status_code == 200:
                            img_path = os.path.join(self.output_dir, 'images', f"{domain}_image_{i}.png")
                            with open(img_path, 'wb') as img_file:
                                img_file.write(img_response.content)
                            logger.info(f"Saved image to {img_path}")
                            
                            # 验证图像是否正确保存
                            if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
                                # Perform OCR on image
                                ocr_text = self.extract_text_from_image(img_path)
                                if ocr_text and ocr_text.strip():
                                    logger.info(f"OCR Success: Extracted {len(ocr_text.strip())} chars from image {i}")
                                    image_ocr_text.append(ocr_text)
                                    content["images"].append({
                                        "path": img_path,
                                        "ocr_text": ocr_text,
                                        "size": f"{size['width']}x{size['height']}"
                                    })
                                else:
                                    logger.warning(f"OCR returned empty text for image {img_path}")
                            else:
                                logger.warning(f"Image file is invalid or empty: {img_path}")
                    except Exception as e:
                        logger.warning(f"Error downloading image {img_src}: {e}")
                except Exception as e:
                    logger.warning(f"Error processing image {i}: {e}")
            
            # 如果没有从图像中提取到文本，尝试从截图中提取
            if not image_ocr_text and os.path.exists(screenshot_path):
                logger.info("No text extracted from individual images, trying full screenshot OCR")
                screenshot_text = self.extract_text_from_image(screenshot_path)
                if screenshot_text and screenshot_text.strip():
                    image_ocr_text.append(screenshot_text)
                    logger.info(f"Extracted {len(screenshot_text.strip())} chars from full screenshot")
            
            # Combine OCR text from all images
            content["ocr_text"] = "\n\n".join(image_ocr_text)
            logger.info(f"Total OCR text length: {len(content['ocr_text'])}")
            
            return content
        except Exception as e:
            logger.error(f"Error capturing visual data: {e}")
            return content

    def extract_text_from_image(self, image_path):
        """Extract text from image using OCR"""
        try:
            # 验证图像文件
            if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
                logger.warning(f"Image file is missing or empty: {image_path}")
                return ""
            
            # 使用EasyOCR进行识别
            if ocr_reader is not None:
                try:
                    logger.info(f"Using EasyOCR to extract text from {image_path}")
                    # 直接使用EasyOCR读取图像
                    result = ocr_reader.readtext(image_path)
                    
                    # 提取文本内容并合并
                    if result:
                        texts = [text[1] for text in result]  # 每个元素的格式是: [[坐标], 文本内容, 置信度]
                        full_text = '\n'.join(texts)
                        
                        # 输出识别结果统计
                        char_count = len(full_text)
                        text_count = len(texts)
                        logger.info(f"EasyOCR extracted {text_count} text blocks, {char_count} characters from {image_path}")
                        
                        if char_count > 0:
                            # 记录部分内容作为示例
                            sample = full_text[:100] + "..." if len(full_text) > 100 else full_text
                            logger.info(f"Sample text: {sample}")
                            return full_text
                except Exception as e:
                    logger.error(f"EasyOCR error: {e}")
            
            # 如果EasyOCR失败或未配置，回退到Tesseract
            logger.info(f"Falling back to Tesseract OCR for {image_path}")
            # 检查Tesseract配置
            if not hasattr(pytesseract.pytesseract, 'tesseract_cmd') or not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
                logger.error(f"Tesseract OCR not properly configured. Path: {pytesseract.pytesseract.tesseract_cmd}")
                return ""
                
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                try:
                    # 尝试用PIL读取
                    pil_img = Image.open(image_path)
                    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                except Exception as e:
                    logger.error(f"Failed to read image: {e}")
                    return ""
            
            # 使用Tesseract提取文本
            ocr_lang = config.tesseract_lang if hasattr(config, 'tesseract_lang') else 'eng'
            text = pytesseract.image_to_string(img, lang=ocr_lang)
            
            if text.strip():
                logger.info(f"Tesseract extracted {len(text.strip())} characters from {image_path}")
            else:
                logger.warning(f"Tesseract failed to extract text from {image_path}")
                
            return text
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""

    def analyze_website(self, content, target_company, url=None):
        """Use OpenAI to analyze if website belongs to target company."""
        if not content["source_code"]:
            return {"belongs_to_target": False, "confidence": 0, "reasoning": "Could not access website"}
        
        prompt = f"""
        Analyze this website and determine if it belongs to or is associated with {target_company}.
        
        Website URL: {url if url else 'Unknown'}
        Website Title: {content['title']}
        
        Key indicators to look for:
        1. Company name or variations in the title, headers, or content
        2. Copyright information
        3. Contact information matching the company
        4. Brand-specific language or terminology
        5. Product or service offerings matching the company
        
        Text extracted from images (OCR):
        {content['ocr_text'][:1000] if content['ocr_text'] else "No text extracted from images"}
        
        Provide your analysis in this JSON format:
        {{
            "belongs_to_target": true/false,
            "confidence": 0-100,
            "reasoning": "Your detailed reasoning here",
            "company_identifiers_found": ["list", "of", "identifiers"]
        }}
        """
        
        # Log the prompt for inspection
        prompt_log_path = os.path.join(self.output_dir, 'reports', f"{urlparse(url).netloc if url else 'unknown'}_prompt.txt")
        with open(prompt_log_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        logger.info(f"Analysis prompt saved to {prompt_log_path}")
        
        try:
            # API call using OpenAI
            logger.info(f"Sending analysis request to OpenAI API for {url}")
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert web analyst who can determine if a website belongs to a specific company based on its content. Respond only with the requested JSON."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Get response
            result = response.choices[0].message.content
            elapsed_time = time.time() - start_time
            logger.info(f"OpenAI analysis completed for {url if url else 'unknown URL'} in {elapsed_time:.2f} seconds")
            
            # Save the response for inspection
            response_log_path = os.path.join(self.output_dir, 'reports', f"{urlparse(url).netloc if url else 'unknown'}_response.json")
            with open(response_log_path, 'w', encoding='utf-8') as f:
                f.write(result)
            logger.info(f"OpenAI response saved to {response_log_path}")
            
            return result
        except Exception as e:
            logger.error(f"Error during OpenAI analysis: {e}")
            return {"belongs_to_target": False, "confidence": 0, "reasoning": f"Error during analysis: {str(e)}"}

    def run_analysis(self, excel_file, target_company):
        """Run the complete analysis process."""
        ip_addresses = self.read_excel(excel_file)
        results = []
        
        logger.info(f"Starting analysis of {len(ip_addresses)} IP addresses for company: {target_company}")
        logger.info(f"Using OpenAI API with model: {self.model}")
        
        for i, ip in enumerate(ip_addresses):
            logger.info(f"Analyzing {ip} ({i+1}/{len(ip_addresses)})")
            
            content, url = self.get_website_content(ip)
            if not content["source_code"]:
                logger.warning(f"Could not fetch content from {ip}")
                results.append({
                    "ip": ip,
                    "url": url,
                    "accessible": False,
                    "title": "N/A",
                    "belongs_to_target": False,
                    "confidence": 0,
                    "reasoning": "Could not access website",
                    "screenshot_path": None,
                    "ocr_text": ""
                })
                continue
                
            analysis = self.analyze_website(content, target_company, url)
            
            # Process analysis result
            try:
                if isinstance(analysis, str):
                    analysis_dict = json.loads(analysis)
                else:
                    analysis_dict = analysis
            except Exception as e:
                logger.error(f"Could not parse LLM response as JSON for {ip}: {e}")
                analysis_dict = {
                    "belongs_to_target": False,
                    "confidence": 0,
                    "reasoning": "Error parsing analysis result"
                }
            
            # Create result entry with all fields
            result_entry = {
                "ip": ip,
                "url": url,
                "accessible": True,
                "title": content["title"],
                "belongs_to_target": analysis_dict.get("belongs_to_target", False),
                "confidence": analysis_dict.get("confidence", 0),
                "reasoning": analysis_dict.get("reasoning", "No reasoning provided"),
                "identifiers": analysis_dict.get("company_identifiers_found", []),
                "screenshot_path": content.get("screenshot_path"),
                "ocr_text": content.get("ocr_text", "")
            }
            
            results.append(result_entry)
            
            # Generate detailed HTML report for this site
            self.generate_site_report(ip, url, content, analysis_dict, target_company)
        
        # Save results to Excel
        result_df = pd.DataFrame(results)
        output_file = os.path.join(self.output_dir, f"{target_company}_analysis_results.xlsx")
        result_df.to_excel(output_file, index=False)
        logger.info(f"Analysis complete. Results saved to {output_file}")
        
        # Generate summary HTML report
        self.generate_summary_report(results, target_company)
        
        return results

    def generate_site_report(self, ip, url, content, analysis, target_company):
        """Generate detailed HTML report for a single site"""
        if not url:
            return
            
        domain = urlparse(url).netloc
        report_path = os.path.join(self.output_dir, 'reports', f"{domain}_report.html")
        
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <title>Analysis Report: {domain}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 1200px; margin: 0 auto; }}
                h1, h2, h3 {{ color: #333; }}
                .container {{ display: flex; flex-wrap: wrap; }}
                .column {{ flex: 1; min-width: 300px; padding: 10px; }}
                .result {{ padding: 15px; background-color: #f5f5f5; border-radius: 5px; margin-bottom: 20px; }}
                .confidence {{ font-size: 24px; font-weight: bold; }}
                .screenshot {{ max-width: 100%; border: 1px solid #ddd; margin: 10px 0; }}
                .source-code {{ height: 400px; overflow: auto; background-color: #f8f8f8; padding: 10px; border: 1px solid #ddd; }}
                pre {{ white-space: pre-wrap; }}
                .belongs-true {{ color: green; }}
                .belongs-false {{ color: red; }}
                .image-container {{ display: flex; flex-wrap: wrap; }}
                .image-item {{ margin: 10px; max-width: 200px; }}
                .image-item img {{ max-width: 100%; }}
            </style>
        </head>
        <body>
            <h1>Website Analysis Report</h1>
            <p><strong>Target Company:</strong> {target_company}</p>
            <p><strong>URL:</strong> <a href="{url}" target="_blank">{url}</a></p>
            <p><strong>IP/Host:</strong> {ip}</p>
            
            <div class="container">
                <div class="column">
                    <h2>Analysis Results</h2>
                    <div class="result">
                        <h3 class="belongs-{'true' if analysis.get('belongs_to_target') else 'false'}">
                            Belongs to {target_company}: {analysis.get('belongs_to_target', False)}
                        </h3>
                        <p class="confidence">Confidence: {analysis.get('confidence', 0)}%</p>
                        <h4>Reasoning:</h4>
                        <p>{analysis.get('reasoning', 'No reasoning provided')}</p>
                        
                        <h4>Identifiers Found:</h4>
                        <ul>
                            {"".join([f"<li>{identifier}</li>" for identifier in analysis.get('company_identifiers_found', []) or ['None found']])}
                        </ul>
                    </div>
                    
                    <h2>Screenshot</h2>
                    <img src="../images/{os.path.basename(content.get('screenshot_path', ''))}" alt="Website Screenshot" class="screenshot"/>
                </div>
                
                <div class="column">
                    <h2>Source Code (excerpt)</h2>
                    <div class="source-code">
                        <pre>{content['source_code'][:5000].replace('<', '&lt;').replace('>', '&gt;')}</pre>
                    </div>
                    
                    <h2>OCR Text From Images</h2>
                    <pre>{content.get('ocr_text', 'No text extracted')}</pre>
                    
                    <h2>Images Analyzed</h2>
                    <div class="image-container">
                        {"".join([f'<div class="image-item"><img src="../images/{os.path.basename(img["path"])}" alt="Image {i}"/><p>{img["ocr_text"][:100]}...</p></div>' for i, img in enumerate(content.get('images', []))])}
                    </div>
                </div>
            </div>
            
            <div>
                <h2>LLM Interaction</h2>
                <p>View the complete interaction log with the AI model:</p>
                <ul>
                    <li><a href="{urlparse(url).netloc if url else 'unknown'}_prompt.txt" target="_blank">Original Prompt</a></li>
                    <li><a href="{urlparse(url).netloc if url else 'unknown'}_response.json" target="_blank">Model Response</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Site report generated: {report_path}")

    def generate_summary_report(self, results, target_company):
        """Generate summary HTML report for all analyzed sites"""
        report_path = os.path.join(self.output_dir, 'reports', f"{target_company}_summary_report.html")
        
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <title>Summary Analysis Report: {target_company}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 1200px; margin: 0 auto; }}
                h1, h2 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .belongs-true {{ color: green; font-weight: bold; }}
                .belongs-false {{ color: red; }}
                .site-link {{ margin-right: 10px; }}
            </style>
        </head>
        <body>
            <h1>Website Analysis Summary</h1>
            <p><strong>Target Company:</strong> {target_company}</p>
            <p><strong>Total Sites Analyzed:</strong> {len(results)}</p>
            <p><strong>Sites Belonging to Target:</strong> {sum(1 for r in results if r.get('belongs_to_target'))}</p>
            <p><strong>Analysis Method:</strong> OpenAI API with model: {self.model}</p>
            
            <h2>Results Table</h2>
            <table>
                <tr>
                    <th>IP/Host</th>
                    <th>URL</th>
                    <th>Title</th>
                    <th>Belongs to Target</th>
                    <th>Confidence</th>
                    <th>Reports</th>
                </tr>
                {"".join([f'''
                <tr>
                    <td>{r.get('ip', 'N/A')}</td>
                    <td><a href="{r.get('url', '#')}" target="_blank">{r.get('url', 'N/A')}</a></td>
                    <td>{r.get('title', 'N/A')}</td>
                    <td class="belongs-{'true' if r.get('belongs_to_target') else 'false'}">{r.get('belongs_to_target', False)}</td>
                    <td>{r.get('confidence', 0)}%</td>
                    <td>
                        <a href="{urlparse(r.get('url', '')).netloc if r.get('url') else 'unknown'}_report.html" class="site-link">Detailed Report</a>
                        <a href="{urlparse(r.get('url', '')).netloc if r.get('url') else 'unknown'}_source.html" class="site-link">Source</a>
                    </td>
                </tr>''' for r in results])}
            </table>
        </body>
        </html>
        """
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Summary report generated: {report_path}")

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")


def main():
    parser = argparse.ArgumentParser(description="Analyze websites to determine if they belong to a specific company")
    parser.add_argument("excel_file", help="Path to Excel file containing IP addresses")
    parser.add_argument("target_company", help="The target company name to check for")
    parser.add_argument("--model", help="OpenAI model to use for analysis", default=config.model)
    args = parser.parse_args()
    
    # Create timestamp-based output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join('output', f'analysis_{timestamp}')
    
    analyzer = WebsiteAnalyzer(output_dir=output_dir)
    analyzer.model = args.model  # Set the model from command line argument
    
    try:
        analyzer.run_analysis(args.excel_file, args.target_company)
    finally:
        analyzer.cleanup()
    
    logger.info(f"Analysis completed. Reports available in: {output_dir}")
    print(f"\nAnalysis completed successfully!")
    print(f"- Results are saved in: {os.path.join(output_dir, f'{args.target_company}_analysis_results.xlsx')}")
    print(f"- Detailed HTML reports available in: {os.path.join(output_dir, 'reports')}")
    print(f"- Summary report: {os.path.join(output_dir, 'reports', f'{args.target_company}_summary_report.html')}")
    print(f"- Using OpenAI API with model: {args.model}")


if __name__ == "__main__":
    # Disable InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main() 