"""
Code Generator - Generates Python, JavaScript, and other code
"""
import re
import logging
from typing import Dict, List, Tuple
from llm_manager import LLMManager

logger = logging.getLogger(__name__)

class CodeGenerator:
    def __init__(self, llm_manager: LLMManager):
        self.llm = llm_manager
    
    def generate_python(self, requirement: str) -> str:
        """Generate Python code based on requirement"""
        prompt = f"""ユーザーの要件に基づいてPythonコードを生成してください。

要件: {requirement}

以下のフォーマットで応答してください：
```python
[ここにコードを記述]
```

コードは実行可能で、エラーハンドリングを含め、適切にコメント化されている必要があります。"""
        
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1000)
        return self._extract_code_block(response, "python")
    
    def generate_javascript(self, requirement: str) -> str:
        """Generate JavaScript code based on requirement"""
        prompt = f"""ユーザーの要件に基づいてJavaScriptコードを生成してください。

要件: {requirement}

以下のフォーマットで応答してください：
```javascript
[ここにコードを記述]
```

コードは実行可能で、適切にコメント化されている必要があります。"""
        
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1000)
        return self._extract_code_block(response, "javascript")
    
    def generate_html(self, requirement: str) -> str:
        """Generate HTML code based on requirement"""
        prompt = f"""ユーザーの要件に基づいてHTMLコードを生成してください。

要件: {requirement}

以下のフォーマットで応答してください：
```html
[ここにコードを記述]
```

HTMLは完全で、適切にコメント化されている必要があります。"""
        
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1000)
        return self._extract_code_block(response, "html")
    
    def fix_code(self, code: str, error: str) -> str:
        """Fix broken code"""
        prompt = f"""以下のコードにエラーがあります。修正してください。

エラー: {error}

元のコード:
```
{code}
```

修正済みコードを以下のフォーマットで提供してください：
```
[修正済みコード]
```"""
        
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1000)
        return self._extract_code_block(response)
    
    def explain_code(self, code: str) -> str:
        """Explain what code does in Japanese"""
        prompt = f"""以下のコードについて、日本語で説明してください。

```
{code}
```

説明："""
        
        return self.llm.generate(prompt, temperature=0.5, max_tokens=500)
    
    def _extract_code_block(self, response: str, language: str = None) -> str:
        """
        Extract code block from response
        Handles: ```python ... ``` or ``` ... ``` or just raw code
        """
        # Try to extract code block with language specifier
        if language:
            pattern = rf'```{language}\n(.*?)```'
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Try to extract code block without language specifier
        pattern = r'```\n?(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # If no code block found, return the response as is (might be raw code)
        return response.strip()
    
    def generate_from_description(self, description: str, language: str = "python") -> str:
        """Generate code from natural language description"""
        if language.lower() == "python":
            return self.generate_python(description)
        elif language.lower() == "javascript":
            return self.generate_javascript(description)
        elif language.lower() == "html":
            return self.generate_html(description)
        else:
            logger.warning(f"Language '{language}' not supported")
            return self.generate_python(description)
