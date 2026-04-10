import io
import re
from PIL import Image

def compress(data):
    img = Image.open(io.BytesIO(data))
    if img.width > 1600:
        ratio = 1600 / img.width
        img = img.resize((1600, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70, optimize=True)
    return buf.getvalue()

def safe_upper(text):
    return text.strip().upper()

def safe_label(text):
    text = safe_upper(text)
    text = re.sub(r'[^A-Z0-9_]+','_',text)
    return text[:30]