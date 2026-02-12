# 🚀 クイックスタートガイド

## 5分で始める自作AI

### ステップ1: Ollama のセットアップ（初回のみ）

```bash
# macOS
brew install ollama

# その後、Ollamaを起動
ollama serve
```

> 別のターミナルタブで、Llama 2をダウンロード:
```bash
ollama pull llama2
```

### ステップ2: Python 環境セットアップ（初回のみ）

```bash
# プロジェクトディレクトリに移動
cd ai-assistant

# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate  # macOS/Linux

# 依存パッケージをインストール
pip install -r requirements.txt
```

### ステップ3: AIアシスタントを起動

```bash
python main.py
```

すると、インタラクティブチャットが起動します：

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

あなた: 
```

## 💡 使用例

### 例1: コード生成

```
あなた: /code
言語を選択してください (python): python
生成してほしいコードの説明: 1から100までの素数を計算する関数を作ってください
```

### 例2: UI生成

```
あなた: /ui
UIの説明: 青と白のカラースキームで、ダークテーマのチャットアプリケーションUI
```

### 例3: 3Dモデル生成

```
あなた: /3d
3Dモデルの説明: 上下に跳ねるボールのアニメーション（ライティング付き）
```

### 例4: 通常の会話

```
あなた: 日本語でのニュアンスについて教えてください
```

## 📊 ステータス確認

```
あなた: /status
```

AIの現在のスキル精度や学習状況が表示されます：

```
📊 AI Assistant Status
==================================================
LLM利用可能: ✅ はい

習得スキル数: 3/5
平均精度: 0%

スキル詳細:
  ❌ code_generation: 0% (使用回数: 0)
  ❌ ui_generation: 0% (使用回数: 0)
  ❌ model_3d_generation: 0% (使用回数: 0)
  ❌ japanese_understanding: 0% (使用回数: 0)
  ❌ text_generation: 0% (使用回数: 0)
==================================================
```

使用するたびに精度が向上します。

## 🐛 よくある問題と解決法

### 問題1: "Ollamaに接続できません"

**原因**: Ollamaが起動していない

**解決法**:
```bash
# 別のターミナルで実行
ollama serve
```

### 問題2: "llama2 モデルが見つかりません"

**原因**: Llama 2がダウンロードされていない

**解決法**:
```bash
ollama pull llama2
```

### 問題3: 応答が遅い

**原因**: GPUがない、またはCPUが遅い

**対策**:
- 初回は時間がかかります（数十秒～数分）
- より小さいモデルを使用: `ollama pull orca-mini`
- `config.py` で `MAX_LENGTH` を減らす

### 問題4: メモリ不足

**解決法**:
```python
# config.py の BATCH_SIZE を減らす
BATCH_SIZE = 2  # 4から変更
```

## 📁 生成されたファイル

### data/ ディレクトリ
- `ai_memory.json` - AIの学習履歴とスキル情報
- `interactions.jsonl` - ユーザーとの対話ログ

### logs/ ディレクトリ
- `ai_assistant.log` - 詳細なログ

### models/ ディレクトリ
- `student_model.pt` - 小型学習モデル（将来）

## 🔄 システムの流れ

```
1. ユーザー入力
        ↓
2. Llama 2で処理
        ↓
3. AI応答を生成
        ↓
4. 応答を表示
        ↓
5. スキル精度を更新
        ↓
6. メモリに記録
        ↓
7. 次の対話へ
```

## 🌟 次のステップ

実装後は以下を試してみてください：

1. **複数の質問を連続で実行**
   - AIの学習能力を確認
   - スキル精度の向上を観察

2. **異なるタイプのコード生成**
   - Python、JavaScript、HTMLを交互に実行
   - AI がどのように適応するかを見る

3. **ログを確認**
   ```bash
   tail -f logs/ai_assistant.log
   ```

4. **メモリを確認**
   ```bash
   cat data/ai_memory.json
   ```

## 📞 サポート

問題が発生した場合：
1. `logs/ai_assistant.log` を確認
2. Ollamaが起動しているか確認
3. Pythonバージョンが3.9以上か確認

## 🎓 学習資料

- [Llama 2 について](https://github.com/meta-llama/llama)
- [Ollama ドキュメント](https://ollama.ai)
- [Three.js チュートリアル](https://threejs.org/manual/#en/fundamentals)

---

楽しいAI開発を！ 🚀
