import re
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Initialize engines once
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

SENSITIVE_PATTERNS = [
    ("Social Security Number", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("Credit Card Number", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("Bank Account / Routing Number", re.compile(r"\b(?:routing|account|acct|rtn)[\s#:=]*(\d{6,17})\b", re.IGNORECASE)),
    ("Password / PIN / Security Code", re.compile(r"\b(?:password|pin|cvv|cvc|passcode|secret)[\s#:=]*(?:is\s+)?([a-zA-Z0-9!@#$%^&*]{3,20})\b", re.IGNORECASE)),
]

def detect_sensitive_info(text: str) -> list[str]:
    """
    Detects if the user provided high-risk credentials or excessive personal info.
    """
    if not text:
        return []
    detected = []
    for label, pat in SENSITIVE_PATTERNS:
        if pat.search(text):
            detected.append(label)

    # Check Presidio entities
    res = analyzer.analyze(
        text=text,
        entities=["US_BANK_NUMBER", "CREDIT_CARD", "US_SSN", "US_PASSPORT", "US_DRIVER_LICENSE", "US_ITIN", "IBAN_CODE"],
        language="en"
    )
    for r in res:
        name = r.entity_type.replace("US_", "").replace("_", " ").title()
        if name not in detected:
            detected.append(name)

    return detected

def sanitize_text(text: str) -> str:
    """
    Scrubs extracted text and replaces sensitive entities and credentials with placeholders.
    """
    if not text:
        return ""

    cleaned = text
    for label, pat in SENSITIVE_PATTERNS:
        tag = f"<REDACTED_{label.replace(' ', '_').replace('/', '_').upper()}>"
        cleaned = pat.sub(tag, cleaned)

    # Call Presidio analyzer to catch names, emails, phones, and banks
    results = analyzer.analyze(
        text=cleaned,
        entities=["PERSON", "PHONE_NUMBER", "US_BANK_NUMBER", "CREDIT_CARD", "LOCATION", "EMAIL_ADDRESS", "US_SSN"],
        language="en"
    )

    # Anonymize
    anonymized_text = anonymizer.anonymize(text=cleaned, analyzer_results=results)
    return anonymized_text.text
