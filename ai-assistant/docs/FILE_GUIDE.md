# 📖 AI Assistant - ファイル・フォルダ説明ガイド

このドキュメントは、各ファイルが**何をしているのか**、**何のためのものなのか**を説明します。

## 🔧 すぐに確認すべきファイル

### **config.py** - 中央設定ファイル ⭐ 最重要
```python
Purpose: システム全体の設定を一元管理
         - モデル名
         - パス設定
         - 自動進化フラグ
         - ワーカー間隔
         - その他パラメータ

編集時: 全モジュールが影響を受けます
確認: 何かおかしい場合、ここから始めてください
```

### **idle_mode.py** - 放置モード起動スクリプト
```python
Purpose: 放置モードを開始・停止
Usage: python3 idle_mode.py
       python3 idle_mode.py --check (状態確認)
Status: 定期的に check_idle_status.py で監視
```

---

## 🚀 コアシステム（`src/core/`）

### **worker.py** - 学習ワーカー
```
What: 定期実行される自動学習エンジン
Why:  毎回30分毎にURLをインジェスト・学習・パッチ提案
How:  python3 worker.py (手動)
      または idle_mode.py から自動実行

Flow: URL取得 → テキスト抽出 → ベクトル化 → 訓練データ生成 
      → 訓練 → 進化 → パッチ提案 → 検証

Log:  [WORKER] 🚀 Starting... のようなプリフィックス付き
```

### **trainer.py** - 訓練エンジン
```
What: ワーカーが生成した合成データでモデルを微調整
Why:  学習データから最適化済みモデルを生成
How:  trainer.train_loop_once() で1ループ実行

Training: LoRA/QLoRA による効率的な微調整
```

### **evolver.py** - 自動進化・パッチ生成
```
What: 訓練済みスキルから自動的にコードパッチを生成
Why:  新しい機能・改善を自動提案
How:  evolver.run() で進化ループ実行

Output: data/patches/ に提案書を生成
Status: ENABLE_AUTOMATED_EVOLUTION = True で有効
```

### **monitor.py** - ワーカー監視デーモン
```
What: ワーカープロセスの監視・自動再起動
Why:  ワーカーが停止した場合、自動で再起動する
How:  python3 monitor.py (常時実行)

Features: プロセス監視, ハートビート確認, 自動再起動
```

---

## 📊 機能モジュール（`src/modules/`）

### **ingest.py** - データ取得・抽出
```
What: URL からコンテンツを取得・テキスト抽出
Why:  Web ページを AI の学習データに変換
How:  ingest(urls) で実行

Output: data/clean/ にクリーニング済みテキスト保存
```

### **vector_store.py** - 知識ベース・検索エンジン
```
What: テキストをベクトル化して高速検索できる索引を構築
Why:  セマンティック検索により、関連する知識を素早く検索
How:  vs = VectorStore(); vs.query("search term")

Backend: FAISS (GPU対応) または TF-IDF (フォールバック)
```

### **llm_manager.py** - ローカル LLM 推論
```
What: Ollama 経由でローカル LLM と通信
Why:  クラウド不要で、プライバシー保護しながら推論
How:  llm = LLMManager(...); llm.generate(prompt)

Models: llama2 (デフォルト), mistral, neural-chat, codegemma
```

### **reporter.py** - 評価レポート生成
```
What: 訓練進捗・性能を分析してレポート出力
Why:  学習がうまくいっているか定期的に確認
How:  reporter.run_report() で生成

Output: logs/reports_{timestamp}.json
```

---

## 🔍 監視・ダッシュボード（`src/monitoring/`）

### **idle_mode_dashboard.py** - リアルタイムダッシュボード
```
What: 放置モードの活動をリアルタイムで可視化
Why:  AI が今、何をしているかを見たいとき
How:  python3 idle_mode_dashboard.py (3秒毎更新)

表示: ワーカー状態, 学習進捗, パッチ統計, スキル進化
```

### **live_monitor.py** - ログストリーム監視
```
What: ログをリアルタイムでストリーム・検索
Why:  詳細なログからデバッグ情報を確認
How:  python3 live_monitor.py
      python3 live_monitor.py tail 50 (最新50行)
      python3 live_monitor.py follow WORKER (ワーカーのみ)
      python3 live_monitor.py search ERROR (エラー検索)
```

### **view_idle_mode.py** - 統合メニュー
```
What: 全ての監視ツールへのワンストップアクセス
Why:  複数のコマンドを覚える代わりに、メニューから選択
How:  python3 view_idle_mode.py (日本語メニュー)
```

---

## 🎯 完璧化システム（`src/perfection/`）

### **multi_teacher_llm.py** - マルチ教師学習
```
What: 4つの異なる LLM モデルから並行学習
Why:  複数の視点から学習し、より良い応答を生成
How:  mtllm.query(prompt, task='code')

Teachers: llama2 (汎用), mistral (高速), neural-chat (会話), codegemma (コード)
```

### **extended_skills.py** - スキル管理システム
```
What: AI が習得した 79+ スキルを管理・追跡
Why:  どのスキルがどの習熟度かを把握
How:  skills = ExtendedSkills(); skills.load()

Categories: Game Dev, Web Dev, Enterprise, DevOps, Data Science, Security
Levels: Beginner → Intermediate → Advanced → Expert
```

### **universal_crawler.py** - 知識自動収集
```
What: 6つの分野から継続的に知識を自動収集
Why:  最新の情報を常に学習
How:  crawler.crawl_specialty('game_dev')

Specialties: game_dev, web_dev, devops, data_science, enterprise, security
Sources: 各分野30+以上の公式ドキュメント・チュートリアル
```

### **perfection_system.py** - 統合エンジン
```
What: マルチ教師・スキル・クローラーを統合
Why:  完璧な AI を実現するための統一インターフェース
How:  perf = PerfectionSystem()
      perf.generate_with_all_systems(prompt)
      perf.show_system_status()
```

---

## 🛡️ ユーティリティ（`src/utils/`）

### **patch_validator.py** - パッチ検証エンジン
```
What: AI 生成パッチを検証・提案・承認
Why:  危険なコードが本番に適用されるのを防止
How:  PatchValidator.validate_patch(code)
      PatchValidator.list_proposals()

Checks: 構文, インポート, リント, サンドボックス実行
```

### **sandbox.py** - 検証サンドボックス
```
What: パッチをテスト用の隔離環境で実行
Why:  本番環境に適用する前に安全に検証
How:  sandbox.run_checks(patch_code)

Tests: 構文チェック, インポート, リント, ユニットテスト
```

### **pii_filter.py** - 個人情報マスキング
```
What: メール・電話番号・クレジットカード番号を検出・マスキング
Why:  個人情報をインジェストしないようにする
How:  sanitize(text) で実行

Detection: Email, Phone, Credit Card, IP Address
```

---

## 📂 データディレクトリ（`data/`）

```
data/
├── training/           訓練用データセット (synthetic_*.jsonl)
├── vector_store/       ベクトルインデックス (FAISS/TF-IDF)
├── patches/           パッチ提案 (自動進化結果)
├── crawled/           収集された生データ (容量注意)
├── clean/             クリーニング済みテキスト
└── extended_skills.json     スキル進化データ
```

---

## 📝 ログファイル（`logs/`）

```
logs/
├── ai_assistant.log       メインログ (日々更新)
└── reports_*.json         評価レポート (自動生成)
```

**最新ログ確認:**
```bash
tail -50 logs/ai_assistant.log
python3 live_monitor.py tail 50
```

---

## 🎮 動作確認チェックリスト

各機能が正常に動作しているか確認：

```bash
# 1. ワーカーが稼働中か確認
ps aux | grep worker

# 2. ダッシュボード表示
python3 idle_mode_dashboard.py

# 3. ログ確認
python3 live_monitor.py tail 30

# 4. ワーカーのみ確認
python3 live_monitor.py follow WORKER

# 5. パッチが提案されているか確認
python3 live_monitor.py follow PATCH

# 6. エラーが無いか確認
python3 live_monitor.py search ERROR

# 7. スキル進化を確認
cat data/extended_skills.json | python3 -m json.tool | head -50
```

---

## ⚡ クイックリファレンス

| 確認したい事 | コマンド |
|----------|---------|
| ダッシュボード | `python3 idle_mode_dashboard.py` |
| ワーカーのログ | `python3 live_monitor.py follow WORKER` |
| エラー | `python3 live_monitor.py search ERROR` |
| パッチ | `python3 live_monitor.py follow PATCH` |
| 最新ログ | `python3 live_monitor.py tail 50` |
| 統合メニュー | `python3 view_idle_mode.py` |
| 設定確認 | `cat config.py` |

---

## 🔧 トラブルシューティング

### ワーカーが起動しない
1. `config.py` で `ENABLE_AUTOMATED_EVOLUTION = True` を確認
2. `python3 worker.py` を手動実行
3. `logs/ai_assistant.log` でエラー確認

### ログが表示されない
1. `logs/` ディレクトリが存在するか確認
2. `touch logs/ai_assistant.log` で作成
3. `python3 live_monitor.py` で表示

### パッチが提案されない
1. `data/patches/` ディレクトリが存在するか確認
2. `ENABLE_AUTOMATED_EVOLUTION = True` を確認
3. ワーカーログで `[EVOLVER]` メッセージ確認

---

このガイドで、システム全体が理解しやすくなるはずです！
