from playwright.sync_api import sync_playwright
import pathlib

text = pathlib.Path('/Users/kawaguchishuusei/Documents/test/ai-assistant/api.py').read_text(encoding='utf-8')
start = text.find('<script>')
end = text.find('</script>', start)
script = text[start+8:end]
lines = script.split('\n')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('about:blank')

    def is_ok(n):
        code = '\n'.join(lines[:n])
        try:
            return page.evaluate('(code)=>{try{new Function(code); return true;}catch(e){return e.message;}}', code)
        except Exception as e:
            return str(e)

    lo, hi = 0, len(lines)
    bad = None
    while lo < hi:
        mid = (lo + hi) // 2
        res = is_ok(mid)
        if res is True:
            lo = mid + 1
        else:
            bad = res
            hi = mid

    print('first bad line index', lo, 'message', bad)
    if lo > 0:
        print('line content:', lines[lo-1])
    if lo < len(lines):
        print('next line content:', lines[lo])
    browser.close()
