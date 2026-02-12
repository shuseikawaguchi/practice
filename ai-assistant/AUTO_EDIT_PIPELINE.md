# Auto-Edit Pipeline - 実装完了

## 概要
自動修正（Auto-Edit）パイプラインが完全に実装され、テストされました。このシステムは以下の安全な自動化フローを実現します：

```
提案生成 → 検証（Sandbox） → パッチ化 → マニュアル承認 → （将来）自動適用
```

## 実装されたコンポーネント

### 1. **Sandbox (sandbox.py)**
- Python ファイルの構文チェック
- インポート検証
- Flake8 リンティング（オプション）
- テストスイート実行（pytest）
- すべての検証をパッチ適用前に実行

**キー関数:**
- `validate_patch(files: dict)` - パッチ内のすべてのファイルを検証
- `save_validation_report(validation, report_path)` - 検証レポートを保存

### 2. **Patch Validator (patch_validator.py)**
提案パッチのライフサイクル管理：

**PatchProposal クラス:**
- `validate()` - Sandbox 検証を実行
- `create_git_branch()` - Git ブランチを作成し、ファイルをコミット
- `propose()` - パッチを `data/patches/` に記録

**PatchValidator クラス:**
- `create_and_validate()` - ワンストップパッチ生成・検証
- `list_proposals()` - 提案一覧（ステータスでフィルタ可能）
- `approve_proposal()` - パッチを承認（マニュアルゲート）

**パッチの状態遷移:**
```
DRAFT → VALIDATED → PROPOSED → APPROVED → （将来）MERGED
        ↓
       FAILED (検証失敗時も PROPOSED 状態で保存可能)
```

### 3. **Git Utils (git_utils.py)**
- `create_branch_and_commit()` - ファイルをブランチにコミット
- Git リポジトリがない場合、`auto_edits/` ディレクトリに直接保存
- パッチファイルを `git format-patch` で生成

### 4. **Worker 統合 (worker.py)**
- `_attempt_auto_patch_generation()` メソッドを追加
- 提案待ちのパッチをチェック
- （将来）ENABLE_AUTOMATED_EVOLUTION が True の場合、自動マージ

### 5. **CLI 統合 (main.py)**
パッチ管理コマンド：
```
/patch-list              - 提案パッチ一覧表示
/patch-approve <id>      - パッチ ID を承認
```

## ファイル構造

```
ai-assistant/
├── sandbox.py              # サンドボックステスト実行環境
├── patch_validator.py      # パッチ検証・提案管理
├── git_utils.py           # Git 統合ユーティリティ
├── worker.py              # (更新) auto-patch 生成を統合
├── main.py                # (更新) パッチ管理 CLI コマンド
├── config.py              # (更新) PROJECT_ROOT, AUTO_EDIT_* 定義
├── test_integration.py    # 統合テストスクリプト
└── data/
    └── patches/           # パッチ提案が保存される
        └── {timestamp}/
            ├── proposal.json      # メタデータ
            ├── validation.json    # 検証レポート
            └── files/             # 生成ファイル
```

## 使用方法

### 1. **提案パッチを作成・検証**
```python
from patch_validator import PatchValidator

proposal = PatchValidator.create_and_validate(
    title='New feature implementation',
    description='Auto-generated feature based on training',
    files={
        'new_module.py': '...',
        'utils/helper.py': '...'
    },
    auto_propose=True
)
```

### 2. **提案パッチを一覧表示**
```bash
# CLI コマンド
/patch-list
```

**出力例:**
```
📋 パッチ提案一覧
======================================================================
⏳ 20260206_172245
   タイトル: Add test feature
   ステータス: PROPOSED
   ファイル: test_feature.py

🆗 20260206_172200
   タイトル: Bug fix
   ステータス: APPROVED
   ファイル: bugfix.py
```

### 3. **パッチを手動で承認**
```bash
# CLI コマンド
/patch-approve 20260206_172245
```

## 安全性メカニズム

### 1. **多段階検証**
- Syntax: Python コンパイルチェック
- Imports: 依存関係検証
- Linting: コード品質チェック
- Tests: ユニットテスト実行

### 2. **マニュアルゲート**
- すべての PROPOSED パッチは人間のレビューを待つ
- APPROVED されたパッチのみ次段階へ進む
- `ENABLE_AUTOMATED_EVOLUTION = False` により自動適用を停止

### 3. **Git ブランチ隔離**
- ブランチ: `auto/edit/{timestamp}`
- すべての変更は分離されたブランチで記録
- Main ブランチへのマージは明示的に承認後のみ

### 4. **完全な監査ログ**
- すべてのパッチは `data/patches/` に保存
- 検証レポート・メタデータ・変更内容を記録
- ロールバック可能

## テスト結果

統合テスト (test_integration.py) の結果：
```
✅ Sandbox テスト: OK
   - Validation OK: True
   - Files validated: 1

✅ Patch Validator テスト: OK
   - Total proposals: 1
   - Latest: Add test feature [APPROVED]

✅ Worker 統合テスト: OK
   - Worker initialized: OK
   - Patch validator available: OK

✅ Main CLI テスト: OK
   - AIAssistant import: OK
   - PatchValidator import: OK
```

## 次の段階（実装予定）

1. **自動マージ機能**
   - `ENABLE_AUTOMATED_EVOLUTION = True` の場合、APPROVED パッチを自動的に main ブランチにマージ
   - Git 統合を完全に実装

2. **パッチ生成の自動化**
   - Trainer/Evolver から自動的にパッチ候補を生成
   - コード生成モジュールを統合

3. **高度な検証**
   - カスタム テストケース実行
   - 性能ベンチマーク
   - セキュリティ スキャン

4. **デプロイメント統合**
   - CI/CD パイプラインとの統合
   - 段階的なロールアウト（カナリア展開）

## 設定オプション

[config.py](config.py) で以下を設定可能：

```python
# Auto-edit 設定
AUTO_EDIT_DIR = BASE_DIR / "auto_edits"           # パッチ保存先
AUTO_EDIT_BRANCH_PREFIX = "auto/edit"             # Git ブランチプレフィックス
AUTO_EDIT_COMMIT_MESSAGE_TEMPLATE = "..."         # コミットメッセージ

# 自動進化（デフォルト: False）
ENABLE_AUTOMATED_EVOLUTION = False                # 自動マージを有効化

# Worker
WORKER_INTERVAL_SECONDS = 60 * 30                 # 30分間隔
STOP_FILE = DATA_DIR / "STOP"                     # 停止フラグ
```

## 実行中のシステム

現在、バックグラウンドで以下が実行中：
- Worker (PID: 61931) - データ取得・ラベリング・合成
- Monitor (PID: 61932) - プロセス監視・バックアップ
- （オプション）Evolver - 試験的なモデル訓練

放置モードを停止するには：
```bash
# CLI コマンド
/idle-off

# または Python
from idle_mode import IdleMode
IdleMode().stop_idle()
```

---

**最後に更新:** 2026年2月6日  
**ステータス:** ✅ 実装完了・テスト済み・本番準備完了
