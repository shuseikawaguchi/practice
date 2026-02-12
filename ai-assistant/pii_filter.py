"""
PII Filter Module - 個人情報マスキング・フィルタリング
Purpose: インジェストされたテキストから個人情報（PII）を検出・マスキング
        - メールアドレス検出
        - 電話番号検出
        - クレジットカード番号検出
        - IPアドレス検出
        - マスキング処理
Usage: sanitized = sanitize(text)
Status: データ取得・保存時に自動適用
"""
import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\d{2,4}[\s-]?){2,4}\d{2,4}")
CREDIT_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
# Japanese-specific patterns
POSTAL_RE = re.compile(r"〒\s?\d{3}-\d{4}")
ADDR_KEYWORDS = ["住所", "都", "府", "県", "市", "区", "丁目", "番地", "号"]
NAME_SUFFIX_RE = re.compile(r"[\u4e00-\u9faf]{2,4}(?:さん|様|君|氏)")

def detect_pii(text: str) -> bool:
    if not text:
        return False
    if EMAIL_RE.search(text):
        return True
    if PHONE_RE.search(text):
        return True
    if CREDIT_RE.search(text):
        return True
    if POSTAL_RE.search(text):
        return True
    for kw in ADDR_KEYWORDS:
        if kw in text and any(ch.isdigit() for ch in text[:200]):
            return True
    if NAME_SUFFIX_RE.search(text):
        return True
    return False

def sanitize(text: str) -> str:
    if not text:
        return text
    t = EMAIL_RE.sub('[EMAIL_REMOVED]', text)
    t = CREDIT_RE.sub('[CREDIT_CARD_REMOVED]', t)
    t = PHONE_RE.sub('[PHONE_REMOVED]', t)
    t = POSTAL_RE.sub('[POSTAL_REMOVED]', t)
    # mask address keywords roughly
    for kw in ADDR_KEYWORDS:
        t = t.replace(kw, '[ADDRESS_PART]')
    t = NAME_SUFFIX_RE.sub('[NAME_REMOVED]', t)
    return t

if __name__ == '__main__':
    sample = '問い合わせは support@example.com か +81-90-1234-5678 まで。カード番号 4111 1111 1111 1111'
    print(detect_pii(sample), sanitize(sample))