"""
UI Generator - Generates HTML and CSS for UI components
"""
import re
import logging
from typing import Dict
from llm_manager import LLMManager

logger = logging.getLogger(__name__)

class UIGenerator:
    def __init__(self, llm_manager: LLMManager):
        self.llm = llm_manager
    
    def generate_html_ui(self, description: str) -> str:
        """Generate HTML UI based on description"""
        prompt = f"""ユーザーの説明に基づいて、モダンで美しいHTMLを生成してください。

説明: {description}

以下のフォーマットで応答してください：
```html
[ここにHTMLを記述]
```

要件：
- セマンティックなHTML5を使用
- アクセシビリティを考慮
- レスポンシブデザイン対応"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=1500)
        return self._extract_code_block(response, "html")
    
    def generate_css(self, description: str) -> str:
        """Generate CSS styling"""
        prompt = f"""ユーザーの説明に基づいて、モダンで美しいCSSを生成してください。

説明: {description}

以下のフォーマットで応答してください：
```css
[ここにCSSを記述]
```

要件：
- モダンなデザイン
- 適切なカラースキーム
- レスポンシブメディアクエリを含める
- アニメーション効果を検討"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=1500)
        return self._extract_code_block(response, "css")
    
    def generate_component(self, component_type: str, specification: str) -> Dict[str, str]:
        """
        Generate complete UI component (HTML + CSS + JS)
        
        component_type: 'button', 'card', 'navbar', 'form', etc.
        """
        prompt = f"""以下の仕様で{component_type}UIコンポーネントを作成してください：

仕様: {specification}

HTMLとCSSの両方を含めてください。以下のフォーマットで応答：

HTML:
```html
[ここにHTMLを記述]
```

CSS:
```css
[ここにCSSを記述]
```"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=2000)
        
        html = self._extract_code_block(response, "html")
        css = self._extract_code_block(response, "css")
        
        return {
            "html": html,
            "css": css,
            "type": component_type
        }
    
    def generate_responsive_layout(self, layout_description: str) -> str:
        """Generate responsive HTML/CSS layout"""
        prompt = f"""レスポンシブなレイアウトを作成してください：

説明: {layout_description}

以下のフォーマットで、HTML + CSSを含めて応答：
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Layout</title>
    <style>
    [ここにCSSを記述]
    </style>
</head>
<body>
    [ここにHTMLを記述]
</body>
</html>
```

要件：
- モバイル、タブレット、デスクトップで適応
- FlexboxまたはCSSグリッドを使用
- 実装可能で実行可能"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=2000)
        return self._extract_code_block(response, "html")
    
    def _extract_code_block(self, response: str, language: str = None) -> str:
        """Extract code block from response"""
        if language:
            pattern = rf'```{language}\n(.*?)```'
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        pattern = r'```\n?(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return response.strip()
    
    def generate_landing_page(self, title: str, description: str, features: list) -> str:
        """Generate complete landing page"""
        features_text = "\n".join([f"- {f}" for f in features])
        
        prompt = f"""
プロフェッショナルなランディングページを作成してください。

タイトル: {title}
説明: {description}
機能:
{features_text}

完全なHTML（CSSを含む）を以下のフォーマットで提供：
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
    [ここにCSSを記述]
    </style>
</head>
<body>
    [ここにHTMLを記述]
</body>
</html>
```

要件：
- モダンで魅力的なデザイン
- 全機能をハイライト
- CTA（Call To Action）ボタンを含める
- レスポンシブ対応"""
        
        response = self.llm.generate(prompt, temperature=0.6, max_tokens=3000)
        return self._extract_code_block(response, "html")
