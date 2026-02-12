# 放置モード & 自己学習・自動進化 運用ガイド

## 概要

このシステムは、**放置モード（Idle Mode）** で自動的に：
1. Webからデータを取得・学習
2. Llama 2 教師モデルで知識を蒸留
3. パッチ候補を自動生成・提案
4. 承認されたパッチを自動的に統合

を実行する**自己改善 AI システム**です。

---

## 1. 放置モードの開始

### 1.1 CLI から開始
```bash
cd /Users/kawaguchishuusei/Documents/test/ai-assistant
python3 main.py
```

対話型モードで以下のコマンドを入力：
```
放置モードをオンにしてください
```
または
```
/idle-on
```

### 1.2 Python から開始
```python
from idle_mode import IdleMode

im = IdleMode()
result = im.start_idle()
print(result)
# 出力例: {'status': 'started', 'pids': {'worker': 61931, 'monitor': 61932}}
```

### 1.3 確認
```bash
python3 check_idle_status.py
```

期待される出力：
```
✅ 放置モード: オン
✅ 自己学習: 実行中
✅ 自動進化: 有効（ENABLE_AUTOMATED_EVOLUTION = True）
✅ 学習データ: N ファイル
```

---

## 2. 放置モードの監視

### 2.1 状態確認
```bash
python3 check_idle_status.py
```

確認される項目：
- **放置モード状態**: オン/オフ
- **バックグラウンドプロセス**: Worker/Monitor が実行中か
- **学習データ**: Synthetic データの生成状況
- **パッチ提案**: 自動生成パッチの状態
- **自動進化設定**: 有効/無効

### 2.2 ログ確認

**Worker ログ**:
```bash
tail -f logs/ai_assistant.log
```

**パッチ生成履歴**:
```bash
ls -lh data/patches/
```

**学習データ**:
```bash
ls -lh data/training/synthetic_*.jsonl
```

---

## 3. 自動パッチ管理

### 3.1 提案パッチの確認
```
/patch-list
```

出力例：
```
📋 パッチ提案一覧
⏳ 20260206_172245
   タイトル: Add feature X
   ステータス: PROPOSED
   ファイル: module_x.py, utils_x.py

🆗 20260206_172200
   タイトル: Bug fix Y
   ステータス: APPROVED
   ファイル: bugfix.py
```

**ステータスの説明**:
- `⏳ PROPOSED`: 検証完了、自動マージ待ち
- `🆗 APPROVED`: マージ済み
- `❌ FAILED`: 検証失敗（手動確認必要）

### 3.2 パッチを手動で確認
```bash
cd data/patches/<patch_id>
cat proposal.json          # メタデータ
cat validation.json        # 検証結果
cat files/*               # 生成ファイル
```

### 3.3 パッチを手動で承認・拒否

**承認する**（自動進化が有効な場合、次のサイクルで自動マージ）:
```
/patch-approve <patch_id>
```

**拒否する**（パッチファイルを手動削除）:
```bash
rm -rf data/patches/<patch_id>
```

---

## 4. 自動進化の制御

### 4.1 自動進化をオン（推奨設定）
```python
# config.py を編集
ENABLE_AUTOMATED_EVOLUTION = True
```

効果：
- ✅ 提案パッチが自動的にマージ
- ✅ Git ブランチ (`auto/edit/*`) に自動コミット
- ✅ 継続的なモデル改善

### 4.2 自動進化をオフ（慎重モード）
```python
# config.py を編集
ENABLE_AUTOMATED_EVOLUTION = False
```

効果：
- ⚠️ パッチは PROPOSED 状態で待機
- ⚠️ 手動で `/patch-approve` する必要あり
- ✅ より慎重な運用（推奨：初期段階）

### 4.3 設定を確認
```bash
python3 -c "from config import Config; print(f'自動進化: {Config.ENABLE_AUTOMATED_EVOLUTION}')"
```

---

## 5. 放置モードの停止

### 5.1 CLI から停止
```
放置モードを停止してください
```
または
```
/idle-off
```

### 5.2 Python から停止
```python
from idle_mode import IdleMode

im = IdleMode()
result = im.stop_idle()
print(result)
```

### 5.3 強制停止（緊急時）
```bash
# STOP フラグを作成
touch data/STOP

# または
python3 -c "from config import Config; Config.STOP_FILE.touch()"
```

---

## 6. バックアップ・ロールバック

### 6.1 バックアップの確認
```bash
ls -lh backups/
```

バックアップは自動的に以下のタイミングで作成：
- 30分ごと（Monitor が定期実行）
- パッチ適用前

### 6.2 ロールバック（手動マージの場合）
```bash
# Git ブランチを確認
git branch -a | grep auto/edit

# ロールバック
git reset --hard <commit_before_patch>
git branch -D auto/edit/<patch_id>
```

### 6.3 Synthetic データのリセット
```bash
# すべての学習データを削除（初期化）
rm -rf data/training/synthetic_*.jsonl
```

---

## 7. トラブルシューティング

### 7.1 Worker が停止している
```bash
# 状態確認
python3 check_idle_status.py

# Worker プロセスを確認
ps aux | grep worker.py

# 再起動
python3 main.py
/idle-on
```

### 7.2 Synthetic データが生成されない
```bash
# Watchlist を確認
cat data/watchlist.txt

# URL を追加
echo "https://example.com" >> data/watchlist.txt

# Worker の次サイクルを待つか、手動トリガー
python3 -c "from worker import Worker; Worker().run_once()"
```

### 7.3 パッチの検証に失敗
```bash
# 検証レポートを確認
cat data/patches/<patch_id>/validation.json

# 問題のあるファイルを確認
cat data/patches/<patch_id>/files/*
```

### 7.4 Git ブランチが競合している
```bash
# git status で確認
git status

# 競合を解決（自動マージを一時停止）
ENABLE_AUTOMATED_EVOLUTION = False  # config.py で設定
git merge --abort
git reset --hard HEAD
```

---

## 8. パフォーマンス・チューニング

### 8.1 Worker の実行間隔を変更
```python
# config.py
WORKER_INTERVAL_SECONDS = 60 * 30  # 30分（デフォルト）
WORKER_INTERVAL_SECONDS = 60 * 5   # 5分（高速）
WORKER_INTERVAL_SECONDS = 60 * 60  # 1時間（低速）
```

### 8.2 進化の試験数を調整
```python
# config.py
EVOLUTION_MAX_TRIALS = 4  # デフォルト: 4回の試験
EVOLUTION_VALIDATION_SIZE = 20  # デフォルト: 20件の検証
```

### 8.3 メモリ使用量を削減
```python
# config.py
BATCH_SIZE = 4  # デフォルト: 4 → 2 に減らす
EPOCHS = 3     # デフォルト: 3 → 1 に減らす
```

---

## 9. セキュリティ注意事項

### 9.1 PII（個人情報）の保護
```bash
# PII フィルタが自動的に動作：
# - 電話番号、メールアドレス、住所などを検出・削除
# - 郵便番号パターン（日本）を対応
```

### 9.2 著作権の保護
```bash
# Copyright フィルタが自動的に動作：
# - ライセンス表記、著作権表示を検出
# - 保護された内容の学習を制限
```

### 9.3 Web スクレイピングの安全性
```bash
# robots.txt を尊重（自動）
# レート制限（自動）: 1リクエスト/秒
# User-Agent を設定（自動）
```

### 9.4 コード除外パターン
```python
# config.py
EXCLUDE_PATTERNS = ["*.py", "*.md", "scripts/*"]
# Watchlist から .py, .md ファイルの自動スクレイピングを除外
```

---

## 10. 運用チェックリスト

### 日次チェック
- [ ] 放置モードが実行中か確認: `python3 check_idle_status.py`
- [ ] エラーログを確認: `tail logs/ai_assistant.log`
- [ ] パッチ提案を確認: `/patch-list`

### 週次チェック
- [ ] Synthetic データの増加を確認: `ls data/training/`
- [ ] バックアップの状態を確認: `ls backups/`
- [ ] ディスク容量を確認: `du -sh .`

### 月次チェック
- [ ] パフォーマンスレポートを確認: `cat logs/reports/`
- [ ] モデルの精度を確認: BLEU/ROUGE スコア
- [ ] Git ブランチをクリーンアップ: `git branch -d auto/edit/*`

---

## 11. よくある質問（FAQ）

### Q: 自動進化をオンにしても安全ですか？
**A**: はい。以下の安全機構があります：
- すべてのパッチはサンドボックスで検証
- Git ブランチで隔離・ロールバック可能
- PII・著作権フィルタで違法なコンテンツを排除
- 定期的なバックアップで復旧可能

### Q: いつパッチが提案されますか？
**A**: Worker が実行するたびに（デフォルト30分ごと）：
1. Watchlist の URL からデータ取得
2. ベクトル化・検索
3. Llama 2 教師で合成データ生成
4. Trainer で軽量学習
5. Evolver で改善案を試験
6. PatchValidator でパッチ化・検証
7. 自動進化が有効なら自動マージ

### Q: 学習の進捗を確認するには？
**A**: 以下の方法で確認：
```bash
# Synthetic データ数
ls data/training/synthetic_*.jsonl | wc -l

# 最新のデータ
cat data/training/synthetic_$(ls -t data/training/synthetic_*.jsonl | head -1 | xargs -I {} basename {}) | head

# 評価レポート
tail logs/reports/report_*.json
```

### Q: Web クローラーがどの URL にアクセスしているか確認するには？
**A**:
```bash
# Watchlist を確認
cat data/watchlist.txt

# 取得済みの URL を確認
ls data/clean/  # または data/raw/
```

---

## 12. リソースと参考資料

- **Main CLI**: `python3 main.py`
- **Auto-Edit パイプライン**: [AUTO_EDIT_PIPELINE.md](AUTO_EDIT_PIPELINE.md)
- **設定**: [config.py](config.py)
- **ログディレクトリ**: `logs/`
- **バックアップ**: `backups/`
- **学習データ**: `data/training/`
- **パッチ提案**: `data/patches/`

---

**最終更新**: 2026年2月6日  
**バージョン**: 1.0
