# 🔍 放置モード活動監視ガイド

## 概要

放置モードの AI が何をしているか、リアルタイムで監視できるツール群を実装しました。

## ツール一覧

### 1. 🖥️ リアルタイムダッシュボード (`idle_mode_dashboard.py`)

**機能:**
- ワーカー/モニターのプロセス状況
- 学習進捗（合成データセット数、訓練例数）
- 知識ベース統計（インデックス文書数、サイズ）
- 自動パッチ生成統計（提案数、承認数、失敗数）
- スキル進化状況（総スキル数、レベル別集計）
- 最新の活動ログ
- システム稼働時間

**使用方法:**
```bash
# リアルタイムダッシュボードを起動（3秒毎に更新）
python3 idle_mode_dashboard.py

# HTML ダッシュボードを生成（ブラウザで表示）
python3 idle_mode_dashboard.py --html
# 生成されたファイルを確認: /tmp/idle_dashboard.html
```

**出力例:**
```
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║  🚀 AI IDLE MODE DASHBOARD - Real-time Activity Monitor                       ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝

⏱️  Uptime: 2h 15m 30s
📅 Time: 2026-02-06 14:35:22

┌─ PROCESS STATUS ──────────────────────────────────────────────────────────────┐
│ ✅ Worker (PID 12345): Running
│ ✅ Monitor (PID 12346): Running
└──────────────────────────────────────────────────────────────────────────────┘

┌─ LEARNING PROGRESS ───────────────────────────────────────────────────────────┐
│ 📚 Synthetic Datasets: 5 files
│ 📊 Training Examples: 150 examples
│ 📝 Latest Dataset: synthetic_1707205800.jsonl
└──────────────────────────────────────────────────────────────────────────────┘

┌─ KNOWLEDGE BASE ──────────────────────────────────────────────────────────────┐
│ 🗂️  Indexed Documents: 1250 documents
│ 💾 Index Size: 45.20 MB
└──────────────────────────────────────────────────────────────────────────────┘

┌─ AUTO-PATCH GENERATION ───────────────────────────────────────────────────────┐
│ 📋 Total Proposals: 8
│ ⏳ Pending (PROPOSED): 2
│ 🆗 Approved (APPROVED): 5
│ ❌ Failed: 1
└──────────────────────────────────────────────────────────────────────────────┘

┌─ SKILL EVOLUTION ─────────────────────────────────────────────────────────────┐
│ 📚 Total Skills: 79
│ 🏆 Expert: 5 | ⭐ Advanced: 12 | ✨ Intermediate: 25 | 📖 Beginner: 37
└──────────────────────────────────────────────────────────────────────────────┘

┌─ RECENT ACTIVITIES (Last 10) ─────────────────────────────────────────────────┐
│ [2026-02-06 14:35:20] [WORKER] ✅ Cycle completed in 45.3 seconds             │
│ [2026-02-06 14:35:15] [TRAINER] 📊 Training completed: loss=0.245             │
│ [2026-02-06 14:35:10] [WORKER] ✅ Synthetic dataset created                   │
│ ...
└──────────────────────────────────────────────────────────────────────────────┘

💡 Tip: Press Ctrl+C to stop monitoring
⚙️  Settings: ENABLE_AUTOMATED_EVOLUTION = True
```

### 2. 📡 ライブログストリーム (`live_monitor.py`)

**機能:**
- ログファイルをリアルタイムで監視
- 色分けされた出力（INFO: 緑、WARNING: 黄、ERROR: 赤）
- キーワードフィルタリング
- ログ検索機能
- タイムスタンプ付き表示

**使用方法:**
```bash
# 全てのログをリアルタイム表示
python3 live_monitor.py

# 最後の 30 行を表示
python3 live_monitor.py tail 30

# キーワードでフィルタ（ワーカーのログのみ）
python3 live_monitor.py follow WORKER

# ログ検索
python3 live_monitor.py search "ERROR"

# パッチ関連のログをフィルタ
python3 live_monitor.py follow PATCH
```

**フィルタリング例:**
```
# ワーカーのログを監視
$ python3 live_monitor.py follow WORKER

📡 Connected to /Users/kawaguchishuusei/Documents/test/ai-assistant/logs/ai_assistant.log
🔍 Filter: WORKER
⏱️  Started: 2026-02-06 14:32:15
────────────────────────────────────────────────────────────────────────────────────────────────

[2026-02-06 14:32:15] [WORKER] 🚀 Worker daemon starting...
[2026-02-06 14:32:15] [WORKER] 📝 PID written to data/worker.pid
[2026-02-06 14:32:16] [WORKER] ═══════════════════════════════════════════════════════
[2026-02-06 14:32:16] [WORKER] Starting cycle - 5 URLs to process
[2026-02-06 14:32:16] [WORKER] ▶️  Ingesting URLs from watchlist
[2026-02-06 14:32:25] [WORKER] ✅ Ingest completed
[2026-02-06 14:32:25] [WORKER] ▶️  Loading vector store
[2026-02-06 14:32:27] [WORKER] ✅ Vector store loaded
[2026-02-06 14:32:27] [WORKER] ▶️  Creating synthetic training dataset
```

### 3. 🎨 統合ビューアー (`view_idle_mode.py`)

すべてのツールへのワンストップアクセス。

**使用方法:**
```bash
python3 view_idle_mode.py
```

**メニュー:**
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  📊 IDLE MODE ACTIVITY VIEWER                                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

オプション:

  1️⃣  リアルタイムダッシュボード (3秒毎に更新)
  2️⃣  ライブログストリーム (全てのログをリアルタイム表示)
  3️⃣  最新ログ表示 (最後の30行)
  4️⃣  ワーカーのログのみ (フィルタ済み)
  5️⃣  トレーナーのログのみ (フィルタ済み)
  6️⃣  パッチのログのみ (フィルタ済み)
  7️⃣  ログ検索 (キーワード検索)
  8️⃣  HTML ダッシュボード (ブラウザで表示)
  0️⃣  終了

選択: 
```

## ワーカーログの改良

ワーカー (`worker.py`) のログ出力を詳細にしました。各フェーズに絵文字と ▶️ / ✅ / ❌ アイコンを付けています。

**ログ例:**
```
[2026-02-06 14:32:16] [WORKER] 🚀 Worker daemon starting...
[2026-02-06 14:32:16] [WORKER] 📝 PID written to data/worker.pid
[2026-02-06 14:32:16] [WORKER] ═══════════════════════════════════════════════════════
[2026-02-06 14:32:16] [WORKER] Starting cycle - 5 URLs to process
[2026-02-06 14:32:16] [WORKER] ▶️  Ingesting URLs from watchlist
[2026-02-06 14:32:25] [WORKER] ✅ Ingest completed
[2026-02-06 14:32:25] [WORKER] ▶️  Loading vector store
[2026-02-06 14:32:27] [WORKER] ✅ Vector store loaded
[2026-02-06 14:32:27] [WORKER] ▶️  Creating synthetic training dataset
[2026-02-06 14:32:35] [WORKER] 📊 Synthetic dataset written: data/training/synthetic_1707205800.jsonl (3 examples)
[2026-02-06 14:32:35] [WORKER] ✅ Synthetic dataset created
[2026-02-06 14:32:35] [WORKER] ▶️  Triggering trainer
[2026-02-06 14:32:45] [WORKER] ✅ Training completed
[2026-02-06 14:32:45] [WORKER] ▶️  Running evolution
[2026-02-06 14:32:50] [WORKER] ✅ Evolution completed
[2026-02-06 14:32:50] [WORKER] ▶️  Attempting auto-patch generation
[2026-02-06 14:32:51] [WORKER] 📋 2 proposed patches awaiting approval
[2026-02-06 14:32:51] [WORKER]   - src/handler.py: Add new feature X
[2026-02-06 14:32:51] [WORKER] ✅ Patch generation completed
[2026-02-06 14:32:51] [WORKER] 🏁 Cycle completed in 35.2 seconds
[2026-02-06 14:32:51] [WORKER] 💤 Sleeping for 1800 seconds until next cycle
```

### ログレベルと記号

| 記号 | 意味 | 例 |
|-----|-----|-----|
| 🚀 | 起動/開始 | Worker daemon starting |
| ▶️  | 処理開始 | ▶️  Ingesting URLs |
| ✅ | 処理成功 | ✅ Ingest completed |
| ❌ | 処理失敗 | ❌ Ingest failed |
| ⚠️  | 警告 | ⚠️  Trainer not available |
| ℹ️  | 情報 | ℹ️  No existing vector store |
| 🏁 | 完了 | 🏁 Cycle completed |
| 💤 | スリープ | 💤 Sleeping |
| 📋 | リスト/集計 | 📋 2 proposed patches |
| 📊 | データ/統計 | 📊 Synthetic dataset written |
| 🔨 | 構築 | 🔨 Building vector store |
| 🛑 | 停止 | 🛑 Worker stopped |

## クイックスタート

### 最もシンプルな方法（推奨）

```bash
# 統合ビューアーを起動
cd /Users/kawaguchishuusei/Documents/test/ai-assistant
python3 view_idle_mode.py
```

その後、メニューから選択します：
- **1番** - ダッシュボード（統計情報）を見たい
- **2番** - ライブログをリアルタイムで見たい
- **4番** - ワーカーの動作だけ見たい

### スクリプトから直接実行

```bash
# ダッシュボード
python3 idle_mode_dashboard.py

# ライブログ
python3 live_monitor.py

# ワーカーのみフィルタ
python3 live_monitor.py follow WORKER

# パッチのみフィルタ
python3 live_monitor.py follow PATCH

# 検索
python3 live_monitor.py search "ERROR"
```

## 色分けされたログ

ライブモニターは自動的に色分けします：

- 🟢 INFO（緑） - 正常な処理
- 🟡 WARNING（黄） - 警告
- 🔴 ERROR（赤） - エラー
- 🟣 CRITICAL（紫） - 重大エラー
- ⚪ DEBUG（暗い） - デバッグ情報

## ダッシュボード指標の説明

### PROCESS STATUS
- ✅ Running / ❌ Stopped - プロセスが動作しているかどうか
- PID - プロセスID

### LEARNING PROGRESS
- Synthetic Datasets - 作成された訓練用データセット数
- Training Examples - 訓練に使用された総例数
- Latest Dataset - 最後に生成されたデータセットファイル

### KNOWLEDGE BASE
- Indexed Documents - ベクトルストアに保存された文書数
- Index Size - インデックスファイルのサイズ（MB）

### AUTO-PATCH GENERATION
- Total Proposals - 提案されたパッチの総数
- Pending (PROPOSED) - 承認待ちのパッチ
- Approved (APPROVED) - 承認済みのパッチ
- Failed - 検証失敗したパッチ

### SKILL EVOLUTION
- Total Skills - システムが学習した総スキル数
- Expert / Advanced / Intermediate / Beginner - 習熟度別分類

## トラブルシューティング

### ログファイルが見つからない

```bash
# ログファイルの確認
ls -la logs/
cat logs/ai_assistant.log | tail -20
```

### プロセスが動作していない

```bash
# ワーカープロセスの確認
ps aux | grep worker
cat data/worker.pid

# 手動でワーカーを起動
python3 worker.py
```

### ダッシュボードが表示されない

```bash
# ディレクトリが存在するか確認
ls -la data/training/
ls -la data/vector_store/
ls -la data/patches/
```

## 定期的なチェック

毎日朝にダッシュボードをチェックすることをお勧めします：

```bash
# 毎朝確認用スクリプト
python3 idle_mode_dashboard.py | head -50
```

学習が進んでいるか、パッチが生成されているか、エラーが発生していないかを確認できます。

## まとめ

| 用途 | コマンド |
|-----|--------|
| 全体統計を見たい | `python3 idle_mode_dashboard.py` |
| ログをリアルタイムで見たい | `python3 live_monitor.py` |
| ワーカーだけ見たい | `python3 live_monitor.py follow WORKER` |
| エラーだけ見たい | `python3 live_monitor.py follow ERROR` |
| 検索したい | `python3 live_monitor.py search "keyword"` |
| HTML で見たい | `python3 idle_mode_dashboard.py --html` |
| 統合メニュー | `python3 view_idle_mode.py` |

これで放置モードの活動が完全に可視化されます！🎉
