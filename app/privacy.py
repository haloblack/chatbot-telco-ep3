import re

# Replace identifiers before publishing any message to an external LLM.
PATTERNS = [
    (re.compile(r'(?i)\b(?:rut\s*[:#]?\s*)?\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[0-9k]\b'), '[RUT]'),
    (re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'(?<!\w)(?:\+?56\s*)?9\s*\d{4}\s*\d{4}(?!\w)'), '[TELEFONO]'),
    (re.compile(r'(?i)\b(?:tarjeta\s*(?:de\s*)?(?:credito|débito)?\s*)?(?:\d[ -]?){13,19}\b'), '[TARJETA]'),
    (re.compile(r'(?i)\b(?:mi nombre es|soy)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,2}'), '[NOMBRE]'),
    (re.compile(r'(?i)\b(?:vivo en|mi dirección es|direccion:)\s+[^,.!?;]+'), '[DIRECCION]'),
]

def anonymize(text: str) -> str:
    result = text or ''
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result
