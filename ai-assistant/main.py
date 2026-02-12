"""
Main AI Assistant - Integration of all components
"""
import logging
import sys
import json
import re
from pathlib import Path

from config import Config
from llm_manager import LLMManager
from skill_manager import SkillManager
from code_generator import CodeGenerator
from ui_generator import UIGenerator
from model_3d_generator import Model3DGenerator
from idle_mode import IdleMode
from vector_store import VectorStore
from patch_validator import PatchValidator

# Configure logging
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
for _h in list(_root_logger.handlers):
    _root_logger.removeHandler(_h)

_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_file_handler = logging.FileHandler(Config.LOGS_DIR / 'ai_assistant.log')
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(_formatter)

_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_console_handler)

logger = logging.getLogger(__name__)

class AIAssistant:
    def __init__(self):
        logger.info("Initializing AI Assistant...")
        
        # Initialize LLM Manager
        self.llm = LLMManager(model_name=Config.TEACHER_MODEL)
        
        # Check if Ollama is available
        if not self.llm.is_available():
            logger.warning("Warning: Ollama is not available. Please make sure Ollama is running.")
            print("⚠️  Ollamaが利用できません。Ollamaが起動していることを確認してください。")
            print("インストール: https://ollama.ai")
            print("起動: ollama serve")
            print()
        
        # Initialize Skill Manager
        self.skills = SkillManager()
        
        # Initialize Generators
        self.code_gen = CodeGenerator(self.llm)
        self.ui_gen = UIGenerator(self.llm)
        self.model_3d_gen = Model3DGenerator(self.llm)
        self.idle = IdleMode()
        self.vs = VectorStore()
        self._rag_cache = {}
        self._rag_cache_order = []
        
        logger.info("AI Assistant initialized successfully")
    
    def chat(self, user_input: str) -> str:
        """Chat with the AI"""
        logger.info(f"User input: {user_input}")
        response = self.llm.chat(user_input)
        logger.info(f"AI response: {response}")
        return response
    
    def generate_code(self, requirement: str, language: str = "python") -> str:
        """Generate code"""
        logger.info(f"Generating {language} code for: {requirement}")
        if language.lower() == "python":
            code = self.code_gen.generate_python(requirement)
        elif language.lower() == "javascript":
            code = self.code_gen.generate_javascript(requirement)
        elif language.lower() == "html":
            code = self.code_gen.generate_html(requirement)
        else:
            code = self.code_gen.generate_from_description(requirement, language)
        
        # Mark skill as used
        self.skills.improve_skill("code_generation", 0.05)
        return code
    
    def generate_ui(self, description: str) -> str:
        """Generate UI"""
        logger.info(f"Generating UI: {description}")
        html = self.ui_gen.generate_html_ui(description)
        self.skills.improve_skill("ui_generation", 0.05)
        return html
    
    def generate_3d_model(self, description: str) -> str:
        """Generate 3D model"""
        logger.info(f"Generating 3D model: {description}")
        model = self.model_3d_gen.generate_threejs_scene(description)
        self.skills.improve_skill("model_3d_generation", 0.05)
        return model

    def summarize_text(self, text: str) -> str:
        """Summarize a given text"""
        logger.info("Summarizing text")
        prompt = (
            "以下の文章を日本語で要約してください。重要な要点を3〜5個の箇条書きで示し、"
            "最後に1行の結論を付けてください。\n\n"
            f"文章:\n{text}\n\n要約："
        )
        return self.llm.generate(prompt, temperature=0.2, max_tokens=400)

    def generate_plan(self, requirement: str) -> str:
        """Generate a concise implementation plan"""
        logger.info("Generating plan")
        prompt = (
            "以下の要件に対する実装計画を日本語で作成してください。"
            "ステップ番号付きで、最小3ステップ〜最大8ステップにしてください。\n\n"
            f"要件:\n{requirement}\n\n計画："
        )
        return self.llm.generate(prompt, temperature=0.2, max_tokens=400)

    def rag_query(self, query: str, k: int = 4) -> str:
        """Retrieve relevant documents and ask LLM to answer using context (RAG)."""
        cache_key = f"{k}|{query}"
        cached = self._rag_cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            # ensure index loaded
            self.vs.load()
        except Exception:
            pass

        try:
            results = self.vs.query(query, k=k)
        except Exception:
            results = []

        context = ''
        for r in results:
            context += f"[Source: {r['meta'].get('source','')}]\n{r['text']}\n\n"

        prompt = f"以下の参考資料を参照して、ユーザーの質問に日本語で答えてください。\n\n参考資料:\n{context}\n質問:\n{query}\n\n回答："
        answer = self.llm.generate(prompt, temperature=0.2, max_tokens=800)
        self._rag_cache_set(cache_key, answer)
        return answer

    def _rag_cache_get(self, key: str):
        if key in self._rag_cache:
            try:
                self._rag_cache_order.remove(key)
            except ValueError:
                pass
            self._rag_cache_order.append(key)
            return self._rag_cache[key]
        return None

    def _rag_cache_set(self, key: str, value: str):
        if not value:
            return
        if key in self._rag_cache:
            self._rag_cache[key] = value
            try:
                self._rag_cache_order.remove(key)
            except ValueError:
                pass
            self._rag_cache_order.append(key)
            return
        self._rag_cache[key] = value
        self._rag_cache_order.append(key)
        limit = Config.RAG_CACHE_SIZE
        if limit and len(self._rag_cache_order) > limit:
            old = self._rag_cache_order.pop(0)
            self._rag_cache.pop(old, None)
    
    def get_status(self) -> dict:
        """Get AI status and skill information"""
        return {
            "llm_available": self.llm.is_available(),
            "skills": self.skills.get_status(),
            "memory_file": str(Config.MEMORY_FILE),
            "log_file": str(Config.LOGS_DIR / 'ai_assistant.log')
        }
    
    def interactive_chat(self):
        """Interactive chat mode"""
        print("\n🤖 AI Assistant - Interactive Mode")
        print("=" * 50)
        print("コマンド:")
        print("  /help        - ヘルプ表示")
        print("  /code        - コード生成モード")
        print("  /ui          - UI生成モード")
        print("  /3d          - 3Dモデル生成モード")
        print("  /status      - ステータス表示")
        print("  /patch-list  - 提案パッチ一覧")
        print("  /patch-approve <id> - パッチを承認")
        print("  /clear       - 会話履歴クリア")
        print("  /exit        - 終了")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\nあなた: ").strip()
                
                if not user_input:
                    continue
                
                if user_input == "/exit":
                    print("さようなら！")
                    break
                elif user_input in ("放置モードをオンにしてください", "放置モードを開始して", "/idle-on"):
                    res = self.idle.start_idle()
                    print(f"放置モード開始: {res}")
                elif user_input in ("放置モードを停止してください", "放置モードをオフにしてください", "/idle-off"):
                    res = self.idle.stop_idle()
                    print(f"放置モード停止: {res}")
                elif user_input in ("放置モードの状態を教えて", "/idle-status"):
                    st = self.idle.status()
                    print(f"放置モード状態: {st}")
                elif user_input == "/help":
                    self._show_help()
                elif user_input == "/status":
                    self._show_status()
                elif user_input.startswith("/patch-list"):
                    self._show_patch_list()
                elif user_input.startswith("/patch-approve"):
                    parts = user_input.split()
                    if len(parts) > 1:
                        patch_id = parts[1]
                        self._approve_patch(patch_id)
                    else:
                        print("用法: /patch-approve <patch_id>")
                elif user_input == "/clear":
                    self.llm.clear_history()
                    print("✅ 会話履歴をクリアしました")
                elif user_input == "/code":
                    self._code_generation_mode()
                elif user_input == "/ui":
                    self._ui_generation_mode()
                elif user_input == "/3d":
                    self._3d_generation_mode()
                else:
                    self._execute_and_apply(user_input)
                    
            except KeyboardInterrupt:
                print("\n\nさようなら！")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"❌ エラーが発生しました: {e}")
    
    def _code_generation_mode(self):
        """Code generation mode"""
        print("\n💻 Code Generation Mode")
        print("言語: python, javascript, html")
        language = input("言語を選択してください (python): ").strip() or "python"
        requirement = input("生成してほしいコードの説明: ").strip()
        
        if requirement:
            print("\n⏳ コードを生成中...")
            code = self.generate_code(requirement, language)
            print(f"\n生成されたコード:\n{code}")
    
    def _ui_generation_mode(self):
        """UI generation mode"""
        print("\n🎨 UI Generation Mode")
        description = input("UIの説明: ").strip()
        
        if description:
            print("\n⏳ UIを生成中...")
            html = self.generate_ui(description)
            print(f"\n生成されたUI:\n{html}")

    def _ui_apply_mode(self, instruction: str):
        """Apply UI improvements directly to api.py"""
        target = Config.PROJECT_ROOT / "api.py"
        if not target.exists():
            print("❌ api.py が見つかりません")
            return
        original = target.read_text(encoding="utf-8", errors="ignore")
        prompt = (
            "次のUIファイルを指定の指示で改良してください。出力はJSONのみ。\n"
            "制約: 既存機能を壊さない/変更はUI領域のみ/できるだけ小さく。\n"
            "形式: {\"title\":...,\"description\":...,\"files\":{\"api.py\":\"content\"}}\n"
            f"指示: {instruction}\n\n"
            "--- 現在の内容 ---\n"
            f"{original}\n"
        )
        print("\n⏳ UI改良を適用中...")
        response = self.llm.generate(prompt, temperature=0.2, max_tokens=900)
        data = self._extract_json(response)
        if not data:
            print("❌ JSON解析に失敗しました")
            return
        files = data.get("files") or {}
        if "api.py" not in files:
            print("❌ api.py の変更が含まれていません")
            return
        title = data.get("title") or "UI auto-improve"
        description = data.get("description") or instruction
        try:
            proposal = PatchValidator.create_and_validate(title, description, files, auto_propose=True)
            print(f"✅ 適用完了: {proposal.id} ({proposal.status})")
        except Exception as e:
            print(f"❌ 適用失敗: {e}")

    def _execute_and_apply(self, instruction: str):
        """Execute instruction by generating and applying a patch."""
        print("\n⏳ 指示を実行中...")
        candidates = self._find_relevant_files(instruction, max_files=4)
        if not candidates:
            print("❌ 関連ファイルが見つかりません")
            return

        file_blocks = []
        for path in candidates:
            try:
                content = (Config.PROJECT_ROOT / path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if len(content) > 20000:
                content = content[:20000]
            file_blocks.append(f"--- {path} ---\n{content}\n")

        prompt = (
            "次の指示を実行するため、必要最小限の変更を行ってください。出力はJSONのみ。\n"
            "制約: 既存機能を壊さない/変更は最小限/対象は提示されたファイルのみ。\n"
            "形式: {\"title\":...,\"description\":...,\"files\":{\"path\":\"content\"}}\n"
            f"指示: {instruction}\n\n"
            + "\n".join(file_blocks)
        )

        response = self.llm.generate(prompt, temperature=0.2, max_tokens=1200)
        data = self._extract_json(response)
        if not data:
            print("❌ JSON解析に失敗しました")
            return
        files = data.get("files") or {}
        if not isinstance(files, dict) or not files:
            print("❌ 変更ファイルがありません")
            return

        title = data.get("title") or "Auto execute"
        description = data.get("description") or instruction
        try:
            proposal = PatchValidator.create_and_validate(title, description, files, auto_propose=True)
            print(f"✅ 適用完了: {proposal.id} ({proposal.status})")
        except Exception as e:
            print(f"❌ 適用失敗: {e}")
    
    def _3d_generation_mode(self):
        """3D model generation mode"""
        print("\n🎪 3D Model Generation Mode")
        description = input("3Dモデルの説明: ").strip()
        
        if description:
            print("\n⏳ 3Dモデルを生成中...")
            model = self.generate_3d_model(description)
            print(f"\n生成された3Dモデル:\n{model}")
    
    def _show_help(self):
        """Show help"""
        help_text = """
🤖 AI Assistant ヘルプ

通常のチャット:
  AIに質問や指示を入力してください

コマンド:
  /code   - Python/JavaScript/HTMLコード生成モード
    /ui     - HTMLとCSSのUI生成モード
  /3d     - Three.jsの3Dモデル生成モード
  /status - AIの能力とステータスを表示
  /clear  - 会話履歴をクリア
  /help   - このヘルプを表示
  /exit   - 終了

機能:
  • 日本語での自然な会話
  • Pythonコード生成
  • JavaScriptコード生成
  • HTMLとCSS生成
  • Three.jsでの3Dモデル作成
  • 段階的な学習と改善
"""
        print(help_text)

    def _extract_json(self, text: str) -> dict | None:
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1].strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
        start = cleaned.find("{")
        while start != -1:
            end = cleaned.find("}", start)
            while end != -1:
                candidate = cleaned[start:end + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
                end = cleaned.find("}", end + 1)
            start = cleaned.find("{", start + 1)
        return None

    def _find_relevant_files(self, instruction: str, max_files: int = 4) -> list[str]:
        tokens = [t for t in re.split(r"\s+", instruction) if t]
        keywords = [t for t in tokens if len(t) >= 2][:8]
        exts = set(Config.AUTO_PATCH_CANDIDATE_EXTS or [".py"])
        exclude_dirs = set(Config.AUTO_PATCH_EXCLUDE_DIRS or [])
        hits = []

        for p in Config.PROJECT_ROOT.rglob("*"):
            if p.is_dir():
                if p.name in exclude_dirs:
                    continue
                continue
            if p.suffix not in exts:
                continue
            parts = set(p.parts)
            if parts.intersection(exclude_dirs):
                continue
            rel = p.relative_to(Config.PROJECT_ROOT).as_posix()
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            score = 0
            for kw in keywords:
                if kw in content or kw in rel:
                    score += 1
            if score > 0:
                hits.append((score, rel))
            if len(hits) > 200:
                break

        hits.sort(key=lambda x: x[0], reverse=True)
        return [h[1] for h in hits[:max_files]]
    
    def _show_status(self):
        """Show AI status"""
        status = self.get_status()
        print("\n📊 AI Assistant Status")
        print("=" * 50)
        print(f"LLM利用可能: {'✅ はい' if status['llm_available'] else '❌ いいえ'}")
        
        skills = status['skills']
        print(f"\n習得スキル数: {skills['learned_skills']}/{skills['total_skills']}")
        print(f"平均精度: {skills['average_accuracy']:.1%}")
        
        print("\nスキル詳細:")
        for skill_name, skill_info in skills['skills'].items():
            status_icon = "✅" if skill_info['is_learned'] else "❌"
            print(f"  {status_icon} {skill_name}: {skill_info['accuracy']:.1%} (使用回数: {skill_info['usage_count']})")
        
        print("=" * 50)

    def _show_patch_list(self):
        """Show list of patches"""
        proposals = PatchValidator.list_proposals()
        print("\n📋 パッチ提案一覧")
        print("=" * 70)
        if not proposals:
            print("パッチなし")
        else:
            for p in proposals:
                status_icon = "🆗" if p['status'] == 'APPROVED' else "⏳" if p['status'] == 'PROPOSED' else "❌"
                print(f"{status_icon} {p['id']}")
                print(f"   タイトル: {p['title']}")
                print(f"   ステータス: {p['status']}")
                print(f"   ファイル: {', '.join(p['files'])}")
                print()
        print("=" * 70)

    def _approve_patch(self, patch_id: str):
        """Approve a patch"""
        if PatchValidator.approve_proposal(patch_id):
            print(f"✅ パッチ {patch_id} を承認しました")
        else:
            print(f"❌ パッチ {patch_id} を承認できませんでした")

def main():
    """Main entry point"""
    assistant = AIAssistant()
    assistant.interactive_chat()

if __name__ == "__main__":
    main()
