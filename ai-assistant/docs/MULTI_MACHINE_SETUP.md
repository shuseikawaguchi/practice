# 複数PCで同じアシスタントを起動する手順（mac / Windows）

目的: **同じURL（http://ai.local:8000/ui）で、接続先だけを切替**できる状態にする。

> 重要: この手順は「URLの固定化」です。**データ共有は別途設定が必要**です。
> - 何もしない場合、データは**各PCのローカルに保存**され、**共有されません**。
> - 共有したい場合は、**共有ストレージ**（NAS/SMB）や**同期**（rsync/クラウド）を利用してください。

---

## 共通の前提
- 同じリポジトリ（ai-assistant）を各PCに配置。
- Python 3.10+ 推奨。
- サーバは **LAN内で http://<PCのIP>:8000/ui** で開く。
- URL固定は **hosts で ai.local を上書き**する。

---

## mac 版（起動）

### 1) 依存関係の準備
```bash
cd /Users/kawaguchishuusei/workspace/training/practice/ai-assistant
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 2) サーバ起動
```bash
cd /Users/kawaguchishuusei/workspace/training/practice/ai-assistant
source venv/bin/activate
python api.py
```

> 既定では `AI_ASSISTANT_API_HOST` を未設定にしている場合、`192.168.1.11` にバインドします。
> 別のIPで起動するPCは、**起動時に環境変数で上書き**してください。

例: 192.168.1.12 のmacで起動する場合
```bash
cd /Users/kawaguchishuusei/workspace/training/practice/ai-assistant
source venv/bin/activate
AI_ASSISTANT_API_HOST=192.168.1.12 AI_ASSISTANT_API_PORT=8000 python api.py
```

---

## Windows 版（起動）

### 1) 依存関係の準備（PowerShell）
```powershell
cd C:\path\to\ai-assistant
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2) サーバ起動（PowerShell）
```powershell
cd C:\path\to\ai-assistant
.\venv\Scripts\Activate.ps1
python api.py
```

> 別IPで起動するPCは環境変数を付けて起動します。

例: 192.168.1.12 のWindowsで起動する場合
```powershell
$env:AI_ASSISTANT_API_HOST="192.168.1.12"
$env:AI_ASSISTANT_API_PORT="8000"
python api.py
```

---

## URL固定（hosts 設定）

### mac
**ai.local を 192.168.1.11 に向ける**
```bash
sudo sh -c 'printf "\n192.168.1.11  ai.local\n" >> /etc/hosts'
```

**192.168.1.12 に切替**
```bash
sudo sed -i '' 's/^192\.168\.1\.11[[:space:]]\+ai\.local$/192.168.1.12  ai.local/' /etc/hosts
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

### Windows（管理者 PowerShell）
**ai.local を 192.168.1.11 に向ける**
```powershell
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "192.168.1.11  ai.local"
```

**192.168.1.12 に切替**
```powershell
(Get-Content C:\Windows\System32\drivers\etc\hosts) -replace '^192\.168\.1\.11\s+ai\.local$','192.168.1.12  ai.local' | Set-Content C:\Windows\System32\drivers\etc\hosts
```

---

## 接続先の切替ルール
- 192.168.1.11（Mac側）が停止/スリープ → 192.168.1.12 に切替
- 192.168.1.11 を使いたい → 192.168.1.11 に戻す

**ブラウザは常に**: http://ai.local:8000/ui

---

## データ共有について（重要）
この運用は **URLを固定しているだけ** なので、**データ共有は別設定**です。

共有の実現方法（例）:
- 共有フォルダ（NAS / SMB / NFS）に `ai-assistant/data` を置き、各PCから同じパスで参照
- rsync / robocopy / クラウド同期で `data/` を定期同期

> 共有しない場合、各PCは別々のデータを持ちます。

---

## 参考URL
- UI: http://ai.local:8000/ui
- API確認: http://ai.local:8000/api/ping
