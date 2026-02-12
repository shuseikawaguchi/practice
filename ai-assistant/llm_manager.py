"""
LLM Manager Module - ローカル LLM 管理・推論エンジン
Purpose: Ollama経由でローカル LLM と通信し、テキスト生成・推論を実行
        - モデル選択
        - プロンプト送信
        - テキスト生成
        - 温度・パラメータ調整
        - エラーハンドリング
Usage: llm = LLMManager(...); response = llm.generate(prompt)
Status: ワーカー・トレーナー・エボルバーから継続呼び出し
"""
import requests
import json
import logging
import time
from typing import Optional, List, Dict
from config import Config
from src.utils.provider_selector import select_provider

logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self, model_name: str = "llama2", base_url: str = Config.OLLAMA_BASE_URL):
        self.model_name = model_name
        self.base_url = base_url
        self.provider = "ollama"
        self.conversation_history: List[Dict] = []
        self._cache: Dict[str, str] = {}
        self._cache_order: List[str] = []
        self._model_checked = False

    def _resolve_provider(self):
        provider = select_provider("llm", "ollama")
        if provider != self.provider:
            self.provider = provider
            self._model_checked = False
        if self.provider == "internal" and Config.INTERNAL_LLM_BASE_URL:
            self.base_url = Config.INTERNAL_LLM_BASE_URL
        else:
            self.base_url = Config.OLLAMA_BASE_URL
        
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = None, use_cache: bool = True) -> str:
        """
        Generate response from Llama 2
        """
        try:
            self._resolve_provider()
            if self.provider == "internal" and not Config.INTERNAL_LLM_BASE_URL:
                return "エラー: 内部LLMが未設定です。"
            if not self._ensure_model_available():
                return "エラー: モデルが未取得です。Ollamaでモデルを取得してください。"
            cache_key = f"{self.model_name}|{temperature}|{max_tokens}|{prompt}"
            if use_cache:
                cached = self._cache_get(cache_key)
                if cached is not None:
                    return cached

            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "temperature": temperature,
                "top_p": Config.LLM_TOP_P,
                "repeat_penalty": Config.LLM_REPEAT_PENALTY,
            }
            if max_tokens is None:
                max_tokens = Config.LLM_MAX_TOKENS
            # Ollama uses num_predict for max tokens
            payload["num_predict"] = max_tokens
            
            response = requests.post(url, json=payload, timeout=Config.LLM_TIMEOUT_SECONDS)
            response.raise_for_status()
            
            result = response.json()
            text = result.get("response", "").strip()
            if use_cache:
                self._cache_set(cache_key, text)
            return text
            
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to Ollama at {self.base_url}")
            return "エラー: Ollamaに接続できません。Ollamaが起動していることを確認してください。"
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"エラーが発生しました: {str(e)}"
    
    def chat(self, user_message: str, system_prompt: str = None) -> str:
        """
        Chat interface with conversation history
        """
        if system_prompt is None:
            system_prompt = """あなたは高度なAIアシスタントです。
以下の能力があります：
- 日本語の複雑なニュアンスを理解する
- Pythonやjavascriptなどのプログラムコードを作成する
- HTMLやCSSでUIを設計する
- 3Dモデルをthree.jsで作成する
- ユーザーの意図を正確に理解する

応答は具体的・実用的にし、同じ表現の繰り返しを避けてください。
抽象的な一般論ではなく、手順・設定・例を示してください。
不足情報がある場合は確認質問を1〜2個だけ行ってください。
必ず日本語で返答し、英語は出力しないでください。"""
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Build conversation context
        context = system_prompt + "\n\n"
        for msg in self.conversation_history[-Config.LLM_HISTORY_TURNS:]:  # Keep last N messages
            role_prefix = "ユーザー: " if msg["role"] == "user" else "アシスタント: "
            context += role_prefix + msg["content"] + "\n"
        
        context += "アシスタント: "
        
        # Generate response
        response = self.generate(
            context,
            temperature=Config.LLM_CHAT_TEMPERATURE,
            max_tokens=Config.LLM_CHAT_MAX_TOKENS,
            use_cache=False
        )

        # If response contains a lot of ASCII letters, force Japanese-only retry
        if self._needs_japanese_retry(response):
            retry_prompt = (
                context
                + "\n\n【重要】英語は使わず、日本語だけで簡潔に回答してください。"
                + "\n【重要】英語の単語・文章を一切含めないでください。"
            )
            response = self.generate(retry_prompt, temperature=0.2, max_tokens=200, use_cache=False)

        # Final fallback: return a short Japanese-only response if still English-heavy
        if self._needs_japanese_retry(response):
            response = "日本語で回答します。目的や条件を1〜2点だけ教えてください。"

        # If response is identical to last assistant response, force a different perspective
        if len(self.conversation_history) >= 2:
            last = self.conversation_history[-1].get("content")
            if last and response.strip() == last.strip():
                alt_prompt = context + "\n\n別の観点で、箇条書きで具体策を3つ述べてください。"
                response = self.generate(
                    alt_prompt,
                    temperature=0.6,
                    max_tokens=Config.LLM_CHAT_MAX_TOKENS,
                    use_cache=False
                )
        
        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

    def _needs_japanese_retry(self, text: str) -> bool:
        if not text:
            return False
        # count ASCII letters
        ascii_letters = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        # count Japanese characters (hiragana/katakana/kanji)
        jp_chars = sum(1 for c in text if (
            '\u3040' <= c <= '\u309F' or  # hiragana
            '\u30A0' <= c <= '\u30FF' or  # katakana
            '\u4E00' <= c <= '\u9FFF'     # kanji
        ))
        # retry if ASCII letters dominate or Japanese is too sparse
        return ascii_letters > 10 and jp_chars < 20
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self._cache.clear()
        self._cache_order = []
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _cache_get(self, key: str) -> Optional[str]:
        if key in self._cache:
            # refresh order
            try:
                self._cache_order.remove(key)
            except ValueError:
                pass
            self._cache_order.append(key)
            return self._cache[key]
        return None

    def _cache_set(self, key: str, value: str):
        if not value:
            return
        if key in self._cache:
            self._cache[key] = value
            try:
                self._cache_order.remove(key)
            except ValueError:
                pass
            self._cache_order.append(key)
            return
        self._cache[key] = value
        self._cache_order.append(key)
        limit = Config.LLM_CACHE_SIZE
        if limit and len(self._cache_order) > limit:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)

    def _ensure_model_available(self) -> bool:
        if self._model_checked:
            return True
        try:
            def _has_model() -> bool:
                tags = requests.get(f"{self.base_url}/api/tags", timeout=10)
                if tags.status_code == 200:
                    data = tags.json()
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return self.model_name in models
                return False

            if _has_model():
                self._model_checked = True
                return True

            # attempt pull
            pull = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model_name, "stream": False},
                timeout=Config.LLM_TIMEOUT_SECONDS
            )
            if pull.status_code not in (200, 201):
                return False

            # wait for model to appear
            wait_seconds = 0
            max_wait = min(180, Config.LLM_TIMEOUT_SECONDS)
            while wait_seconds < max_wait:
                time.sleep(2)
                wait_seconds += 2
                if _has_model():
                    self._model_checked = True
                    return True
            return False
        except Exception as e:
            logger.error(f"Model check/pull failed: {e}")
            return False
