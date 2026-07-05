# 君だけの占い

悩みを入力すると、AIが占いとして気持ちを読み解く1ページWeb MVPです。

本サービスの出力は娯楽・自己理解を目的とし、未来や結果を保証しません。医療、法律、投資などの専門的助言でもありません。

## 機能

- 占いジャンル選択（恋愛、復縁、相性、仕事、今日の運勢）
- 悩み、任意のニックネーム、任意の生年月日入力
- 生年月日がある場合の星座・ライフパスナンバーによる個別化
- OpenAI Responses APIによる鑑定文生成
- 無料鑑定は400文字まで、出力は最大500トークン
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
USE_MOCK_AI=false
OPENAI_MODEL_FREE=gpt-5.4-mini
OPENAI_MODEL_PREMIUM=gpt-5.5
MAX_INPUT_CHARS_FREE=400
MAX_OUTPUT_TOKENS_FREE=500
MAX_INPUT_CHARS_PREMIUM=1200
MAX_OUTPUT_TOKENS_PREMIUM=1800
```

`OPENAI_MODEL_PREMIUM`は将来の決済接続用です。現在の生成処理では使用しません。

### OpenAI APIを呼ばずに画面を確認する

開発中にAPI料金を発生させたくない場合は、`.env`を次のように設定します。

```env
USE_MOCK_AI=true
```

固定のモック鑑定文が返り、OpenAI APIクライアントは使用されません。設定変更後はサーバーを再起動してください。

実際の占い品質を確認するときと本番環境では、必ず次の設定を使用します。

```env
USE_MOCK_AI=false
```

`false`または未設定の場合は通常どおりOpenAI APIを呼び出すため、有効な`OPENAI_API_KEY`が必要です。

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
  "birthday": "2000-11-22",
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

`birthday`は任意です。`YYYY-MM-DD`と`YYYY/MM/DD`の両方を受け付け、内部では`YYYY-MM-DD`へ正規化します。未来日、存在しない日付、120歳を超える日付は受け付けません。

## 注意

- APIキーはサーバー側だけで使用し、HTMLやJavaScriptへ渡しません。
- `USE_MOCK_AI=true`は画面・API・エラー表示の開発確認専用です。本番品質の評価には使用しません。
- 悩み本文やAI出力全文はアプリケーションログへ保存しません。
- 生年月日は任意で、入力された場合だけ星座とライフパスナンバーを算出して鑑定に利用します。
- 入力された生年月日と算出した占い要素は鑑定生成のためOpenAI APIへ送信されますが、現時点ではDBやログへ保存しません。
- チャット履歴は保持・送信せず、1回の相談だけをOpenAI APIへ送ります。
- 無料鑑定は、核心、現在の流れ、やりがちな失敗1つ、今日の行動1つに絞ります。
- 入出力上限は環境変数で設定し、API側でも無料入力文字数を検証します。
- 簡易レート制限は単一プロセスのメモリ内実装です。複数プロセス・複数台構成ではRedis等へ置き換えてください。
- 法務ページは仮文面です。正式公開前に事業者情報と運用実態に合わせて確定してください。

## OpenAI使用量ログ

`USE_MOCK_AI=false`でOpenAI APIから応答を受け取ると、開発コンソールへ次の形式で表示します。

```text
model=gpt-5.4-mini input_tokens=1000 output_tokens=300 total_tokens=1300 estimated_cost_usd=0.00210000
```

悩み本文とAI出力全文は表示しません。概算料金はコード内のモデル単価と`response.usage`から計算するため、OpenAIの料金改定後は単価表の更新が必要です。モック利用時はOpenAI APIを呼ばないため使用量ログも出ません。

## 旧CLI

旧CLIコードは参照用に残していますが、製品の入口には使用しません。Web MVPの入口は`src.kimidake_bot.web:app`です。
