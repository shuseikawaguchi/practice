"""
3D Model Generator - Generates Three.js 3D models
"""
import re
import logging
from llm_manager import LLMManager

logger = logging.getLogger(__name__)

class Model3DGenerator:
    def __init__(self, llm_manager: LLMManager):
        self.llm = llm_manager
    
    def generate_threejs_scene(self, description: str) -> str:
        """Generate Three.js scene based on description"""
        prompt = f"""Three.jsを使用して3Dシーンを作成してください。

説明: {description}

以下のフォーマットで完全なHTMLページを応答してください：
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Scene</title>
    <style>
        body {{ margin: 0; }}
        canvas {{ display: block; }}
    </style>
</head>
<body>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
    [ここにJavaScriptを記述]
    </script>
</body>
</html>
```

要件：
- Three.jsを使用
- ライティングと影を含める
- マウスでの回転に対応
- アニメーション効果を考慮"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=2500)
        return self._extract_code_block(response, "html")
    
    def generate_geometric_shape(self, shape_type: str, parameters: dict) -> str:
        """Generate specific geometric shape"""
        params_text = "\n".join([f"{k}: {v}" for k, v in parameters.items()])
        
        prompt = f"""Three.jsで{shape_type}を作成してください。

パラメータ:
{params_text}

以下のフォーマットでJavaScriptコードを提供：
```javascript
[ここにコードを記述]
```

要件：
- Three.js用のコード
- シーン、カメラ、レンダラーを初期化
- ジオメトリとマテリアルを作成
- アニメーションループを含める"""
        
        response = self.llm.generate(prompt, temperature=0.4, max_tokens=1500)
        return self._extract_code_block(response, "javascript")
    
    def generate_animated_model(self, model_description: str, animation_description: str) -> str:
        """Generate animated 3D model"""
        prompt = f"""Three.jsでアニメーション付き3Dモデルを作成してください。

モデル説明: {model_description}
アニメーション: {animation_description}

完全なHTMLページを以下のフォーマットで応答：
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Animated 3D Model</title>
    <style>
        body {{ margin: 0; overflow: hidden; }}
        canvas {{ display: block; }}
        #info {{ position: absolute; top: 10px; left: 10px; color: white; }}
    </style>
</head>
<body>
    <div id="info">アニメーション3Dモデル</div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
    [ここにJavaScriptを記述]
    </script>
</body>
</html>
```

要件：
- スムーズなアニメーション
- 適切なライティング
- マウスコントロール対応"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=3000)
        return self._extract_code_block(response, "html")
    
    def generate_interactive_scene(self, scene_type: str, interactions: list) -> str:
        """Generate interactive 3D scene"""
        interactions_text = "\n".join([f"- {i}" for i in interactions])
        
        prompt = f"""Three.jsでインタラクティブな3Dシーンを作成してください。

シーンタイプ: {scene_type}

インタラクション:
{interactions_text}

完全なHTMLページを提供：
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive 3D</title>
    <style>
        body {{ margin: 0; font-family: Arial; }}
        canvas {{ display: block; }}
        #controls {{ position: absolute; bottom: 20px; left: 20px; 
                      background: rgba(0,0,0,0.7); color: white; 
                      padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div id="controls">
        <h3>操作方法</h3>
        [ここにコントロール説明を記述]
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
    [ここにJavaScriptを記述]
    </script>
</body>
</html>
```

要件：
- マウス/キーボードインタラクション対応
- リアルタイム更新
- パフォーマンス最適化"""
        
        response = self.llm.generate(prompt, temperature=0.5, max_tokens=3000)
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
