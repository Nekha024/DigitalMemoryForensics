import os
import fitz

def detect_file_type(file_name):
    ext = os.path.splitext(file_name)[1].lower()
    if ext == '.pdf':
        return 'pdf'
    elif ext == '.txt':
        return 'txt'
    elif ext == '.docx':
        return 'docx'
    return 'other'

def extract_text_from_pdf(file_path):
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
        text += "\n"
    doc.close()
    return text.strip()

def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read().strip()

def extract_text(file_path, file_type):
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type == 'txt':
        return extract_text_from_txt(file_path)
    return "Extraction for this file type is not supported in Milestone 1."