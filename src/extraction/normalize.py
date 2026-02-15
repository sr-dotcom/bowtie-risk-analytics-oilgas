"""Text normalization for extracted PDF text."""
import re
import unicodedata

# Smart quote replacements
_QUOTE_MAP: dict[str, str] = {
    "\u201c": '"',   # left double
    "\u201d": '"',   # right double
    "\u2018": "'",   # left single
    "\u2019": "'",   # right single
    "\u00ab": '"',   # left guillemet
    "\u00bb": '"',   # right guillemet
}

# Collapse runs of 3+ spaces (not newlines) to a single space
_MULTI_SPACE = re.compile(r"[^\S\n]{3,}")

# Collapse 3+ consecutive blank lines to 2
_MULTI_BLANK_LINES = re.compile(r"\n{4,}")


def normalize_text(text: str) -> str:
    """Normalize extracted text for downstream NLP.

    Operations (in order):
    1. Replace NBSP with regular space
    2. Replace smart quotes with ASCII equivalents
    3. Remove control characters (preserve newline, tab, carriage return)
    4. Collapse excessive inline whitespace
    5. Collapse excessive blank lines
    6. Strip leading/trailing whitespace per line
    """
    if not text:
        return ""

    # 1. NBSP -> space
    text = text.replace("\u00a0", " ")

    # 2. Smart quotes -> ASCII
    for fancy, plain in _QUOTE_MAP.items():
        text = text.replace(fancy, plain)

    # 3. Remove control chars (keep \n \r \t)
    cleaned_chars = []
    for ch in text:
        if ch in ("\n", "\r", "\t"):
            cleaned_chars.append(ch)
        elif unicodedata.category(ch).startswith("C"):
            continue  # skip control chars
        else:
            cleaned_chars.append(ch)
    text = "".join(cleaned_chars)

    # 4. Collapse excessive inline whitespace
    text = _MULTI_SPACE.sub("  ", text)

    # 5. Collapse excessive blank lines
    text = _MULTI_BLANK_LINES.sub("\n\n\n", text)

    # 6. Strip per line
    lines = text.split("\n")
    lines = [line.strip() for line in lines]
    text = "\n".join(lines)

    # Final strip
    text = text.strip()

    return text
