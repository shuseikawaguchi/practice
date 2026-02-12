# 🤖 自作AI Assistant - 自己改善型スマートAI

**概要**: 自分で学習し、機能を拡張し、自動で成長するAIアシスタントシステムです。

**目的**: 完璧な AI を構築 - 何を聞いても正しい答えが返ってくる、あらゆる業務・ゲーム作成が可能なシステム

**ステータス**: 🟢 **稼働中** | 放置モード有効 | 自動進化有効

---

## 📁 プロジェクト構造

このプロジェクトは、メンテナンス性を高めるため、以下の構造に整理されています：

```
src/
├── core/           # コアシステム（ワーカー・トレーナー・エボルバー・モニター）
├── modules/        # 機能モジュール（インジェスト・検索・推論・レポート）
├── monitoring/     # 監視・ダッシュボード（可視化ツール）
├── generation/     # 生成系（コード・3D・UI生成）
├── perfection/     # 完璧化システム（マルチ教師・スキル・クローラー）
└── utils/          # ユーティリティ（検証・フィルタ・設定）
```

**詳細は `docs/FOLDER_STRUCTURE.md` を参照してください**

---

## 🎯 主な機能

### 第一段階（実装済み）

✅ **自然な日本語会話**
- 複雑な日本語のニュアンス理解
- コンテキスト認識型の応答

✅ **コード生成**
- Python コード自動生成
- JavaScript コード自動生成
- HTML コード自動生成
- コード修正・説明機能

✅ **UI・Web制作**
- HTMLとCSSでのUI自動生成
- レスポンシブデザイン対応
- ランディングページ生成

✅ **3Dモデル生成**
- Three.jsを使用した3Dシーン生成
- アニメーション付きモデル
- インタラクティブな3D環境

✅ **自己改善メカニズム**
- スキル学習とトラッキング
- 使用度と精度の記録
- メモリシステムによる記憶

## 🚀 セットアップ

### 前提条件
- Python 3.9以上
- Ollama（ローカルLLM実行用）

### 1. Ollama のインストール

```bash
# macOSの場合
brew install ollama

# または https://ollama.ai からダウンロード
```

### 2. Llama 2 モデルのダウンロード

```bash
# Ollamaを起動
ollama serve

# 別のターミナルで
ollama pull llama2
```

### 3. Python 環境セットアップ

```bash
# プロジェクトディレクトリに移動
cd ai-assistant

# 仮想環境作成（推奨）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows

# 依存パッケージインストール
pip install -r requirements.txt
```

## 📖 使い方

### インタラクティブチャットモード

```bash
python main.py
```

すると以下のように対話開始：
```
🤖 AI Assistant - Interactive Mode
==================================================
コマンド:
  /help        - ヘルプ表示
  /code        - コード生成モード
  /ui          - UI生成モード
  /3d          - 3Dモデル生成モード
  /status      - ステータス表示
  /clear       - 会話履歴クリア
  /exit        - 終了
==================================================

あなた: こんにちは
```

### コマンド使用例

#### 💻 コード生成
```
あなた: /code
言語を選択してください (python): python
生成してほしいコードの説明: フィボナッチ数列を計算する関数
```

#### 🎨 UI生成
```
あなた: /ui
UIの説明: ダークテーマのタスク管理アプリケーションのUI
```

#### 🎪 3Dモデル生成
```
あなた: /3d
3Dモデルの説明: 回転する立方体にライティング付き
```

#### 📊 ステータス確認
```
あなた: /status
```

## 📁 プロジェクト構造

```
ai-assistant/
├── main.py                    # メインプログラム
├── config.py                  # 設定ファイル
├── llm_manager.py             # Llama 2管理
├── skill_manager.py           # スキル管理・学習
├── code_generator.py          # コード生成機能
├── ui_generator.py            # UI生成機能
├── model_3d_generator.py      # 3Dモデル生成機能
├── requirements.txt           # 依存パッケージ
├── README.md                  # このファイル
│
├── data/                      # データディレクトリ
│   ├── ai_memory.json         # 学習履歴・スキル情報
│   └── interactions.jsonl     # ユーザー対話ログ
│
├── models/                    # モデルディレクトリ
│   └── student_model.pt       # 小型学習モデル（将来実装）
│
└── logs/                      # ログディレクトリ
    └── ai_assistant.log       # 実行ログ
```

## 🧠 自己改善メカニズム

### スキル学習システム

AIは以下の方法で継続的に学習・改善します：

1. **ユーザーフィードバック**
   - ユーザーが応答の質を評価
   - その評価に基づいてモデルを微調整

2. **使用度トラッキング**
   - 各スキルの使用回数を記録
   - 頻繁に使用されるスキルの精度向上を優先

3. **メモリシステム**
   - 過去の対話から学習
   - 学習内容をJSONファイルに保存
   - 次回起動時に学習内容を復元

### スキル成長の進行状況

```
初期状態:
- コード生成: 0% 精度
- UI生成: 0% 精度
- 3Dモデル生成: 0% 精度
- 日本語理解: 0% 精度

使用と学習後:
- コード生成: ↗ 75% 精度
- UI生成: ↗ 68% 精度
- 3Dモデル生成: ↗ 82% 精度
- 日本語理解: ↗ 90% 精度
```

## 🔧 詳細設定

`config.py` で調整可能な設定：

```python
# モデル設定
TEACHER_MODEL = "llama2"        # 教師モデル
STUDENT_MODEL_NAME = "student_ai"

# 学習設定
LEARNING_RATE = 5e-5
BATCH_SIZE = 4
EPOCHS = 3

# Ollama設定
OLLAMA_BASE_URL = "http://localhost:11434"
API_PORT = 8000
```

## 📊 ログとデバッグ

ログファイル: `logs/ai_assistant.log`

詳細なログを確認：
```bash
tail -f logs/ai_assistant.log
```

## 🐛 トラブルシューティング

### "Ollamaに接続できません"
```bash
# Ollamaを起動
ollama serve
```

### "llama2モデルが見つかりません"
```bash
# モデルをダウンロード
ollama pull llama2
```

### メモリ不足エラー
```python
# config.py で設定を減らす
BATCH_SIZE = 2  # 4から減らす
```

## 🚧 次のフェーズ

### フェーズ2: 高度な学習機構
- [ ] ファインチューニング実装
- [ ] 強化学習システム
- [ ] 自動品質評価

### フェーズ3: スキル拡張
- [ ] データベース管理スキル
- [ ] API連携スキル
- [ ] 画像生成スキル
- [ ] 音声合成スキル

### フェーズ4: Web UI
- [ ] リアルタイムチャット
- [ ] 生成されたコードのプレビュー
- [ ] 3Dモデルビューアー
- [ ] スキル進捗ダッシュボード

## 📚 参考資料

- [Ollama](https://ollama.ai) - ローカルLLM実行
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/)
- [Three.js Documentation](https://threejs.org/docs/)
- [FastAPI](https://fastapi.tiangolo.com/)

## 📝 ライセンス

MIT License

## 🤝 貢献

改善提案やバグ報告を歓迎します！

---

**作成日**: 2026年2月6日
**バージョン**: 1.0 (フェーズ1)
