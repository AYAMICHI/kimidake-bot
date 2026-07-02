# 君だけの占い

悩みを入力すると、AIが占いとして気持ちを読み解く1ページWeb MVPです。

本サービスの出力は娯楽・自己理解を目的とし、未来や結果を保証しません。医療、法律、投資などの専門的助言でもありません。

## 機能

- 占いジャンル選択（恋愛、復縁、相性、仕事、今日の運勢）
- 任意のニックネームと悩み入力
- OpenAI Responses APIによる鑑定文生成
- 入力長制限、危険相談の簡易検出
- IP単位の簡易レート制限（1分間に3回）
- プレミアム鑑定の仮導線
- 利用規約等の仮ページ

初回MVPでは、ログイン、DB、LINE連携、Stripe決済、継続チャットは実装していません。

## 必要環境

- Python 3.12推奨
- OpenAI APIキー

## セットアップ

PowerShellでリポジトリ直下から実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`を編集します。

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_FREE=gpt-4.1-mini
OPENAI_MODEL_PREMIUM=gpt-5.2
```

`OPENAI_MODEL_PREMIUM`は将来の決済接続用です。現在の生成処理では使用しません。

## 起動

```powershell
uvicorn src.kimidake_bot.web:app --reload
```

ブラウザで <http://127.0.0.1:8000> を開きます。

## API

### `POST /api/fortune`

リクエスト例：

```json
{
  "nickname": "あおい",
  "category": "love",
  "concern": "相手の気持ちが分からず、どう向き合えばよいか悩んでいます。"
}
```

レスポンス例：

```json
{
  "result": "鑑定結果",
  "error": null
}
```

カテゴリ値は`love`、`reconciliation`、`compatibility`、`work`、`today`のいずれかです。

## 注意

- APIキーはサーバー側だけで使用し、HTMLやJavaScriptへ渡しません。
- 悩み本文やAI出力全文はアプリケーションログへ保存しません。
- 簡易レート制限は単一プロセスのメモリ内実装です。複数プロセス・複数台構成ではRedis等へ置き換えてください。
- 法務ページは仮文面です。正式公開前に事業者情報と運用実態に合わせて確定してください。

## 旧CLI

旧CLIコードは参照用に残していますが、製品の入口には使用しません。Web MVPの入口は`src.kimidake_bot.web:app`です。
