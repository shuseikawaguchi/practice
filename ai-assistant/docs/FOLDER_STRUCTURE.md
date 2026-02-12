# AI Assistant Project Structure Guide

## フォルダ構成

```
ai-assistant/
├── src/                          # ソースコード
│   ├── core/                     # コアシステム（ワーカー・トレーナー・エボルバー・モニター）
│   │   ├── worker.py
│   │   ├── trainer.py
│   │   ├── evolver.py
│   │   └── monitor.py
│   │
│   ├── modules/                  # 機能モジュール（データ・検索・推論）
│   │   ├── ingest.py             # URL インジェスト
│   │   ├── vector_store.py       # ベクトルストア・検索
│   │   ├── llm_manager.py        # LLM 推論
│   │   ├── web_crawler.py        # Web クローリング
│   │   └── reporter.py           # 評価レポート
│   │
│   ├── monitoring/               # 監視・ダッシュボード（可視化）
│   │   ├── idle_mode_dashboard.py
│   │   ├── live_monitor.py
│   │   ├── view_idle_mode.py
│   │   └── show_idle_mode_tools.py
│   │
│   ├── generation/               # 生成系（3D・UI・コード生成）
│   │   ├── code_generator.py     # コード生成
│   │   ├── model_3d_generator.py # 3D モデル生成
│   │   └── ui_generator.py       # UI 生成
│   │
│   ├── perfection/               # 完璧化システム（Phase 1-4）
│   │   ├── multi_teacher_llm.py  # マルチ教師学習
│   │   ├── extended_skills.py    # 拡張スキル管理
│   │   ├── universal_crawler.py  # 知識自動収集
│   │   └── perfection_system.py  # 統合インターフェース
│   │
│   └── utils/                    # ユーティリティ（フィルタ・検証・抽出）
│       ├── config.py             # 中央設定管理
│       ├── patch_validator.py    # パッチ検証
│       ├── sandbox.py            # サンドボックス実行
│       ├── pii_filter.py         # 個人情報フィルタ
│       ├── copyright_filter.py   # 著作権フィルタ
│       ├── extractor.py          # テキスト抽出
│       └── git_utils.py          # Git 操作
│
├── data/                         # データストレージ
│   ├── training/                 # 訓練データセット
│   ├── vector_store/             # ベクトルインデックス
│   ├── patches/                  # パッチ提案
│   ├── crawled/                  # クローリングデータ
│   └── clean/                    # クリーニング済みテキスト
│
├── logs/                         # ログファイル
│   ├── ai_assistant.log          # メインログ
│   └── reports_*.json            # 評価レポート
│
├── docs/                         # ドキュメント
│   ├── ARCHITECTURE.md           # システムアーキテクチャ
│   ├── API.md                    # API リファレンス
│   └── TROUBLESHOOTING.md        # トラブルシューティング
│
├── models/                       # モデルチェックポイント
│   └── trained_*.pt             # PyTorch モデル
│
├── scripts/                      # ユーティリティスクリプト
│   └── setup.sh
│
├── auto_edits/                   # 自動編集・パッチ
│   └── patches/
│
├── backups/                      # バックアップ
│
├── config.py                     # メイン設定ファイル
├── idle_mode.py                  # 放置モード起動スクリプト
├── main.py                       # メインアプリ
├── api.py                        # API サーバー
├── requirements.txt              # Python 依存ライブラリ
├── README.md                     # プロジェクト概要
└── .gitignore                    # Git 除外設定

```

## ファイル分類

### ⚙️ コアシステム（`src/core/`）
- **worker.py** - 定期実行される学習ワーカー（30分毎）
- **trainer.py** - モデル微調整エンジン
- **evolver.py** - 自動進化・パッチ生成
- **monitor.py** - ワーカー監視デーモン

### 📊 機能モジュール（`src/modules/`）
- **ingest.py** - URL からのデータ取得
- **vector_store.py** - ベクトルストア・セマンティック検索
- **llm_manager.py** - ローカル LLM 推論
- **reporter.py** - 性能評価・レポート生成

### 🔍 監視・ダッシュボード（`src/monitoring/`）
- **idle_mode_dashboard.py** - リアルタイムダッシュボード
- **live_monitor.py** - ログストリーム監視
- **view_idle_mode.py** - 統合メニュー

### 🎯 完璧化システム（`src/perfection/`）
- **multi_teacher_llm.py** - マルチ教師学習（Phase 1）
- **extended_skills.py** - 拡張スキル管理（79+ スキル）
- **universal_crawler.py** - 知識自動収集（6 分野）
- **perfection_system.py** - 統合エンジン

### 🛡️ ユーティリティ（`src/utils/`）
- **patch_validator.py** - パッチ検証・提案管理
- **sandbox.py** - 安全な検証サンドボックス
- **pii_filter.py** - 個人情報マスキング
- **config.py** - 中央設定（**最重要**）

## 使用方法

### 放置モード起動
```bash
python3 idle_mode.py
```

### ダッシュボード表示
```bash
python3 view_idle_mode.py
```

### ログ監視
```bash
python3 live_monitor.py follow WORKER
```

### 手動でワーカー実行
```bash
python3 src/core/worker.py
```

### API サーバー起動
```bash
python3 api.py
```

## 開発時のクイックリファレンス

| 機能 | ファイル | 用途 |
|------|---------|------|
| 設定変更 | `config.py` | すべてのパスと設定がここに |
| ログ確認 | `live_monitor.py` | リアルタイムログ表示 |
| パッチ承認 | `patch_validator.py` | 提案一覧・承認/却下 |
| スキル確認 | `extended_skills.py` | 習得スキル・習熟度確認 |
| 性能確認 | `reporter.py` | 訓練進捗・性能評価 |

## エクスプローラー表示を整理するコツ

1. **.gitignore で非表示** - `__pycache__/`, `*.pyc` など自動生成ファイル
2. **フォルダ分類** - 関連ファイルを `src/*/` に整理
3. **ドキュメント** - `docs/` に集約
4. **データ** - `data/` に集約（データは `.gitignore` 除外）

## パフォーマンスチューニング

- **data/** フォルダが大きくなった場合、古い `crawled/` を削除
- **logs/** フォルダは定期的にアーカイブ
- **models/** は定期的にクリーンアップ（古いチェックポイント削除）
