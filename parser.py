import requests
import tempfile
import pdfplumber
import pytesseract
from PIL import Image
import io

def process_media(media_url: str) -> str:
    """
    Downloads the file securely to memory and extracts text.
    Handles PDFs and images (OCR).
    """
    try:
        response = requests.get(media_url, stream=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')

        extracted_text = ""

        if 'pdf' in content_type.lower() or media_url.lower().endswith('.pdf'):
            with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file.flush()
                
                with pdfplumber.open(temp_file.name) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
        
        elif 'image' in content_type.lower() or any(media_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
            image = Image.open(io.BytesIO(response.content))
            extracted_text = pytesseract.image_to_string(image)
        
        else:
            extracted_text = "[Unsupported file format attached]"

        return extracted_text

    except Exception as e:
        print(f"Error processing media: {e}")
        return ""
