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
ENABLE_PREMIUM_PREVIEW=false
OPENAI_MODEL_FREE=gpt-5.4-mini
OPENAI_MODEL_PREMIUM=gpt-5.5
MAX_INPUT_CHARS_FREE=400
MAX_OUTPUT_TOKENS_FREE=500
MAX_INPUT_CHARS_PREMIUM=1200
MAX_OUTPUT_TOKENS_PREMIUM=1800
```

`OPENAI_MODEL_PREMIUM`は、`ENABLE_PREMIUM_PREVIEW=true`の開発用プレミアム鑑定で使用します。

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

### `POST /api/premium-fortune`

決済接続前にプレミアム鑑定の品質を確認する開発用APIです。`ENABLE_PREMIUM_PREVIEW=false`では`403`を返します。

```json
{
  "nickname": "あおい",
  "birthdate": "2000/11/22",
  "category": "work",
  "concern": "副業を始めましたが、なかなか収益が出なくて諦めそうです。",
  "free_result": "無料鑑定結果"
}
```

```json
{
  "result": "プレミアム鑑定結果",
  "error": null,
  "estimated_cost_usd": "0.02500000",
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 600,
    "total_tokens": 1800
  }
}
```

`estimated_cost_usd`は説明用の例です。実際の値はAPIレスポンスのusageとコード内のモデル単価から計算されます。

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

## プレミアム鑑定プレビュー

目的はStripe接続前に、プレミアム鑑定が500円以上の価値に見えるかと、1回あたりのAPIコストをローカルで確認することです。Stripe決済、購入権限、ユーザーDB、ログインは接続していません。

`.env`を次のように変更し、サーバーを再起動します。

```env
ENABLE_PREMIUM_PREVIEW=true
USE_MOCK_AI=false
```

無料鑑定を実行して結果下のCTAを押すと、同じ画面にプレミアム鑑定が表示されます。無料鑑定と同じ入力および無料結果を引き継ぎますが、ブラウザやサーバーのDB・ログには保存しません。無料結果は最大2000文字までをプロンプトへ渡します。

実APIを使うためOpenAI API料金が発生します。画面下部と開発コンソールで`input_tokens`、`output_tokens`、`total_tokens`、`estimated_cost_usd`を確認してください。出力品質の確認では`USE_MOCK_AI=false`を使用します。画面だけ確認する場合は`USE_MOCK_AI=true`でも固定のプレミアム鑑定を表示できます。

プレミアム鑑定は次を深掘りします。

- 相談全体と内側の葛藤
- 生年月日がある場合の自然な個別傾向
- 現在の流れと見えている分岐
- 避けたい動きとその理由
- 反応に応じて変えられる具体的な次の一手
- 今日〜2週間程度に見るべき判断材料
- 依存を促さず、自分で進むための最後の一言

手動確認では、恋愛・復縁・仕事の各ジャンルで、生年月日`2000/11/22`と実際の相談文を入力します。特に「無料鑑定の繰り返しになっていないか」「分岐の見分け方があるか」「近い期間の観察点が具体的か」「未来や相手の本音を断定していないか」を確認してください。

本番環境では必ず次の設定に戻してください。`false`では画面のCTAは従来どおり準備中ページへ移動し、プレミアムAPIは`403`で拒否されます。

```env
ENABLE_PREMIUM_PREVIEW=false
```

### OpenAI BadRequestの開発診断

`ENABLE_PREMIUM_PREVIEW=true`でOpenAI APIが`BadRequestError`を返した場合、開発コンソールへ次の形式で表示します。

```text
openai_bad_request status_code=400 error_code=unsupported_parameter rejected_parameter=temperature error_message=Unsupported parameter: temperature
```

記録するのはstatus code、OpenAIのerror code、拒否されたパラメータ、エラーメッセージだけです。APIキー、悩み本文、生年月日、無料・プレミアム鑑定本文は記録せず、エラーメッセージ内に含まれた場合も伏せ字にします。エラーレスポンス全体やリクエスト本文はログへ出しません。

## 旧CLI

旧CLIコードは参照用に残していますが、製品の入口には使用しません。Web MVPの入口は`src.kimidake_bot.web:app`です。

## 匿名CTAイベント計測

無料鑑定の表示に対してプレミアム鑑定CTAが何回押されたかを、CTAクリック率（`cta_click / result_view * 100`）として確認できます。鑑定生成とは独立しており、ブラウザは計測完了を待ちません。

`.env`の設定は次のとおりです。

```env
ANALYTICS_ENABLED=true
ANALYTICS_STORAGE=sqlite
```

`ANALYTICS_ENABLED=false`にするとイベントを保存しません。現在対応する保存方式は`sqlite`のみで、保存先は`data/analytics.sqlite3`です。

計測イベントは次の2種類です。

- `result_view`: 無料鑑定結果が画面に表示された時
- `cta_click`: プレミアム鑑定CTAが押された時

保存する項目はイベント名、ジャンル、生年月日の入力有無、サーバー側の記録時刻、ブラウザセッション単位の匿名ランダムID、User-Agentの短いSHA-256ハッシュです。悩み本文、AI鑑定結果、生年月日、ニックネーム、生のUser-Agent、生のIPアドレス、メールアドレス、OpenAI APIキーは保存しません。

ブラウザでは`sessionStorage`へ匿名IDを保持し、まず`navigator.sendBeacon`で送信します。利用できない場合だけ`fetch`の`keepalive`へフォールバックします。送信失敗は画面に表示せず、CTAの遷移や鑑定生成を止めません。

集計はリポジトリ直下で次のコマンドを実行します。

```powershell
python -m src.kimidake_bot.analytics_report
```

全体およびジャンル別の`result_view`件数、`cta_click`件数、CTAクリック率が表示されます。本番デプロイでは、`data/analytics.sqlite3`の保存先が永続ディスクか確認してください。コンテナの一時ファイル領域へ置くと、再起動や再デプロイで計測データが消えます。また、複数インスタンス構成へ移行する場合は共有DBまたは外部分析基盤への移行が必要です。
