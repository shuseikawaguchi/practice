**日次学習サマリ**

- **目的**: 放置モードで何を学習したかを日ごとに記録し、ダッシュボードで確認できるようにする。
- **出力先**: `data/summaries/YYYY-MM-DD.json`
- **生成方法**:
  - 手動: `python3 scripts/generate_daily_summary.py [YYYY-MM-DD]`（省略時は今日）
  - 自動: cron 等で毎日実行することを推奨（例: 毎日 00:05 に実行）

  自動実行の設定例

  - シンプルな crontab 行（毎日 00:05 に実行）: `crontab -e` に追加

  ```
  5 0 * * * /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/run_generate_summary.sh >> /Users/kawaguchishuusei/Documents/test/ai-assistant/logs/daily_summary.log 2>&1
  ```

  - 直接 python を使う例（仮想環境の python を指定するのが安全）:

  ```
  5 0 * * * PYTHONPATH=/Users/kawaguchishuusei/Documents/test/ai-assistant /Users/kawaguchishuusei/.venv/bin/python /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/generate_daily_summary.py >> /Users/kawaguchishuusei/Documents/test/ai-assistant/logs/daily_summary.log 2>&1
  ```

  - macOS 推奨（cron ではなく launchd を使う場合）: `~/Library/LaunchAgents/com.ai.daily-summary.plist` を作成してロードします（前のメッセージの plist 例を参照）。

  ラッパースクリプト

  プロジェクトに `scripts/run_generate_summary.sh` を追加しました。仮想環境を利用する場合はスクリプト内で `source` してから実行する形にしてください。

  学習したスキル一覧の見方

  - メモリファイル: `data/ai_memory.json`（`Config.MEMORY_FILE`）に `learned_skills` が格納されます。
  - 日次サマリには、その日の学習スキル名を `learned_skills` として最大20件まで保存します（`data/summaries/YYYY-MM-DD.json`）。
  - 確認コマンド（今日のサマリを生成して表示）:

  ```
  PYTHONPATH=/Users/kawaguchishuusei/Documents/test/ai-assistant python3 /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/generate_daily_summary.py
  cat data/summaries/$(date +%F).json
  ```

  - 学習したスキルを日付指定で一覧表示するスクリプトを追加しました:

  ```
  python3 scripts/show_learned_skills.py 2026-02-06
  ```

  スクリプトは `data/ai_memory.json` の `learned_skills` を参照し、`learned_at` / `added_at` / `timestamp` のいずれかのタイムスタンプをサポートします。タイムスタンプが無いエントリは一覧に含められます（ただし日付絞りはできません）。

日次サマリの見方（まとめ）

- **最短で見る（最新サマリ）**:

```
PYTHONPATH=/Users/kawaguchishuusei/Documents/test/ai-assistant python3 /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/view_daily_summary.py
```

- **日付指定で見る**:

```
PYTHONPATH=/Users/kawaguchishuusei/Documents/test/ai-assistant python3 /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/view_daily_summary.py 2026-02-09
```

- **週次でパッと見る（過去7日）**:

```
PYTHONPATH=/Users/kawaguchishuusei/Documents/test/ai-assistant python3 /Users/kawaguchishuusei/Documents/test/ai-assistant/scripts/view_weekly_summary.py
```

- **ダッシュボードで見る**:
  - `idle_mode_dashboard.py` の「日次サマリ（過去7日）」と「詳細サマリ（最新3日）」に表示されます。

- **含まれる情報**:
  - `new_datasets`: その日に追加された合成データセット数
  - `new_examples`: その日に追加された学習例（行数ベース）
  - `new_indexed_documents`: その日にインデックスされたドキュメント数（heuristic）
  - `index_size_mb`: ベクトルインデックスのサイズ（MB）
  - `approved_patches`: その日に承認されたパッチ数（heuristic）

例: `data/summaries/2026-02-06.json`

運用メモ:
- 自動実行する場合は、プロジェクトルートで仮想環境や PATH を正しく設定した上で cron エントリを追加してください。
