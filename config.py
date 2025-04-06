# LLM API Configuration
# OpenAI API配置
model = "XXXX"  # 默认模型
api_base = "XXXXX"
openai_key = "XXXXX"

# Browser Settings
chrome_driver_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe'

# OCR Settings
use_easyocr = True  # 使用EasyOCR进行图像识别
easyocr_languages = ['ch_sim', 'en']  # EasyOCR语言列表: 中文简体和英文
use_gpu = False  # 不使用GPU加速EasyOCR

# Tesseract OCR设置（作为备用）
tesseract_cmd = r'E:\XU\APP\OCR\tesseract.exe'
tesseract_lang = 'chi_sim+eng'

# Analysis Settings
timeout = 10  # seconds for HTTP requests
max_retries = 3 