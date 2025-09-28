import pypdf
import re
import pdfplumber
import fitz  # PyMuPDF
    
def extract_text_from_pdf(file_path: str, method: str = 'auto') -> str:
    """
    Extract text from PDF using different methods.

    Args:
        file_path: Path to PDF file
        method: 'auto', 'pdfplumber', 'pymupdf', or 'pypdf'

    Returns:
        Extracted text as string
    """

    if method == 'auto':
        # Try methods in order of preference
        for extract_method in ['pdfplumber', 'pymupdf', 'pypdf']:
            try:
                return extract_text_from_pdf(file_path, extract_method)
            except Exception as e:
                print(f"Method {extract_method} failed: {str(e)}")
                continue
        raise Exception("All extraction methods failed")

    elif method == 'pdfplumber':
        return _extract_with_pdfplumber(file_path)

    elif method == 'pymupdf':
        return _extract_with_pymupdf(file_path)

    elif method == 'pypdf':
        return _extract_with_pypdf(file_path)

    else:
        # Fallback to pypdf
        return _extract_with_pypdf(file_path)


def _extract_with_pypdf(file_path: str) -> str:
    """Original pypdf extraction method"""
    with open(file_path, 'rb') as file:
        reader = pypdf.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text


def _extract_with_pdfplumber(file_path: str) -> str:
    """Extract using pdfplumber for better layout handling"""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def _extract_with_pymupdf(file_path: str) -> str:
    """Extract using PyMuPDF for robust extraction"""
    doc = fitz.open(file_path)
    text = ""
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text += page.get_text() + "\n"
    doc.close()
    return text


def clean_basic_artifacts(text):
    # Remove page numbers (standalone numbers)
    text = re.sub(r'\n\d+\n', '\n', text)

    # Remove excessive whitespace/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # Fix broken word hyphenation
    text = re.sub(r'-\n(\w)', r'\1', text)

    return text.strip()


def clean_structure(text):
    # Remove table of contents patterns
    text = re.sub(r'\.{3,}\d+', '', text)

    # Remove figure/table references
    text = re.sub(r'Figure \d+[:\.].*?\n', '', text)
    text = re.sub(r'Table \d+[:\.].*?\n', '', text)

    # Clean citation patterns
    text = re.sub(r'\[\d+\]', '', text)

    return text


class NumberNormalizer:
    def __init__(self):
        # Mapping dictionaries for different number formats
        self.emoji_numbers = {
            '1️⃣': '1', '2️⃣': '2', '3️⃣': '3', '4️⃣': '4', '5️⃣': '5',
            '6️⃣': '6', '7️⃣': '7', '8️⃣': '8', '9️⃣': '9', '0️⃣': '0'
        }

        self.circled_numbers = {
            '①': '1', '②': '2', '③': '3', '④': '4', '⑤': '5',
            '⑥': '6', '⑦': '7', '⑧': '8', '⑨': '9', '⑩': '10',
            '⑪': '11', '⑫': '12', '⑬': '13', '⑭': '14', '⑮': '15',
            '⑯': '16', '⑰': '17', '⑱': '18', '⑲': '19', '⑳': '20'
        }

        self.parenthesized_numbers = {
            '⑴': '1', '⑵': '2', '⑶': '3', '⑷': '4', '⑸': '5',
            '⑹': '6', '⑺': '7', '⑻': '8', '⑼': '9', '⑽': '10',
            '⑾': '11', '⑿': '12', '⒀': '13', '⒁': '14', '⒂': '15'
        }

        self.double_circled_numbers = {
            '⓵': '1', '⓶': '2', '⓷': '3', '⓸': '4', '⓹': '5',
            '⓺': '6', '⓻': '7', '⓼': '8', '⓽': '9', '⓾': '10'
        }

        self.fullwidth_numbers = {
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9'
        }

        # Combine all mappings
        self.all_mappings = {
            **self.emoji_numbers,
            **self.circled_numbers,
            **self.parenthesized_numbers,
            **self.double_circled_numbers,
            **self.fullwidth_numbers
        }

    def normalize_numbers(self, text: str) -> str:
        """Convert all special number formats to regular digits"""
        result = text

        # Replace all special number formats
        for special_num, regular_num in self.all_mappings.items():
            result = result.replace(special_num, f" {regular_num}. ")

        return result

    def normalize_list_markers(self, text: str) -> str:
        """Specifically handle list markers like ①, 1., (1), etc."""
        # Pattern to match various list marker formats
        patterns = [
            # Circled numbers at start of line
            (r'^([①-⑳])\s*', r'\1. '),
            # Emoji numbers at start of line  
            (r'^([0-9]️⃣)\s*', lambda m: f"{self.emoji_numbers.get(m.group(1), m.group(1))}. "),
            # Parenthesized numbers
            (r'^([⑴-⒂])\s*', lambda m: f"{self.parenthesized_numbers.get(m.group(1), m.group(1))}. "),
            # Double circled numbers
            (r'^([⓵-⓾])\s*', lambda m: f"{self.double_circled_numbers.get(m.group(1), m.group(1))}. "),
        ]

        result = text
        for pattern, replacement in patterns:
            if callable(replacement):
                result = re.sub(pattern, replacement, result, flags=re.MULTILINE)
            else:
                # First normalize the numbers, then apply the pattern
                temp = self.normalize_numbers(result)
                result = re.sub(pattern, replacement, temp, flags=re.MULTILINE)

        # Final normalization pass
        return self.normalize_numbers(result)