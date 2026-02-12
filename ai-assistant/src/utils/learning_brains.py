"""
Learning brains - 学習用タスクの多様化
"""
from typing import List, Dict


def get_brain_tasks() -> List[Dict[str, str]]:
    """Return diverse learning tasks with task_type tags."""
    base = [
        {"task_type": "summary", "prompt": "このドキュメントを要約して、要点を3〜5個の箇条書きで示してください。"},
        {"task_type": "analysis", "prompt": "この内容の背景・目的・影響を整理して分析してください。"},
        {"task_type": "howto", "prompt": "この記事の利用方法をステップバイステップで示してください。"},
        {"task_type": "comparison", "prompt": "関連する他手法と比較し、メリット/デメリットを整理してください。"},
        {"task_type": "ai_paper", "prompt": "AI/機械学習の文献として、目的・手法・結果・限界を整理してください。"},
        {"task_type": "ai_eval", "prompt": "評価方法・指標・再現性の観点で要点を整理してください。"},
        {"task_type": "ai_alignment", "prompt": "安全性・バイアス・運用上の注意点を整理してください。"},
        {"task_type": "ai_prompting", "prompt": "有効なプロンプト設計の原則を3つに整理し、例を示してください。"},
        {"task_type": "ai_tooling", "prompt": "他のAIツールの良い点を抽象化し、自分に取り込むべき設計原則を3つ示してください。"},
        {"task_type": "checklist", "prompt": "この内容のチェックリストを10項目で作成してください。"},
        {"task_type": "faq", "prompt": "よくある質問と回答を5つ作成してください。"},
        {"task_type": "code", "prompt": "具体的なコード例と、動作確認の手順を示してください。"},
        {"task_type": "trend", "prompt": "この領域の最近の傾向を3点に整理してください。"},
        {"task_type": "clarify", "prompt": "初心者向けに重要点を3つに絞って説明してください。"},
        {"task_type": "expert", "prompt": "上級者向けに落とし穴と回避策を整理してください。"},
        {"task_type": "improve", "prompt": "改善案を3つ提案し、優先度を付けてください。"},
        {"task_type": "risk", "prompt": "導入時のリスクと対応策を整理してください。"}
    ]

    topics = [
        "LLM", "RAG", "エージェント", "プロンプト設計", "評価ベンチマーク",
        "安全性", "蒸留", "量子化", "推論最適化", "マルチモーダル"
    ]
    expanded = []
    for t in topics:
        expanded.append({"task_type": "topic_summary", "prompt": f"{t}の要点を3〜5個で要約してください。"})
        expanded.append({"task_type": "topic_howto", "prompt": f"{t}を実務に適用する手順を簡潔に示してください。"})
        expanded.append({"task_type": "topic_pitfall", "prompt": f"{t}の失敗例と回避策を3つ示してください。"})

    return base + expanded
