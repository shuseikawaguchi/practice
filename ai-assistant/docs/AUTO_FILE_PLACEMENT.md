# 自動ファイル配置（Auto File Placement）

概要
---
このドキュメントは、AIやシステムが自動生成するファイルを機能別フォルダへ自動的に配置するための仕組みを説明します。

設計
---
- `Config.AUTO_FILE_MAP` によってコンポーネント名と保存先ディレクトリを定義します。
- `src/utils/file_manager.py` が実際の書き込み処理を担います。ディレクトリが存在しない場合は自動で作成します。
- 既存ファイルがある場合はバックアップを作成して退避します。

使い方
---
```python
from src.utils.file_manager import write_component_file

content = {"foo": "bar"}
# patches コンポーネントに proposal.json を保存
path = write_component_file('patches', 'proposal.json', content)
```

シャム（shim）について
---
- 既存のトップレベル実行ファイルを `src/` 以下に整理した場合、互換性維持のために「shim」をプロジェクトルートに作成できます。
- `FileManager.create_shim()` は簡単なshimファイルを生成します。shim は `src` 以下のモジュールをインポートしてエントリポイントを呼びます。

注意点
---
- 自動でフォルダを作成するため、Config.AUTO_FILE_MAP に新しいコンポーネント名を追加してください。
- import パス（例: `src.core.worker`）に合わせてモジュールを移動するか、shim を作成してください。

