# Kimidake Bot

キマダケボット — 数秘術とAIを組み合わせた占い生成ボット

## 概要

このプロジェクトは、OpenAI APIを利用して数秘術に基づいた占いを生成するボットです。ユーザーの生年月日や名前から運勢を計算し、パーソナライズされた占いの結果を提供します。

## 機能

- 数秘術による運勢計算
- AIによる詳細な占い生成
- 入力値の検証
- 設定管理

## セットアップ

### 前提条件

- Python 3.8以上
- OpenAI APIキー

### インストール

1. リポジトリをクローン
```bash
git clone <repository_url>
cd kimidake-bot
```

2. 仮想環境を作成
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

3. 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

4. 環境変数を設定
```bash
cp .env.example .env
# .envファイルを編集してOpenAI APIキーを設定
```

## 使用方法

```bash
python src/kimidake_bot/main.py
```

## プロジェクト構造

```
kimidake-bot/
├── src/
│   └── kimidake_bot/
│       ├── __init__.py
│       ├── config.py           # 設定管理
│       ├── main.py             # エントリーポイント
│       ├── prompts/            # AIプロンプト
│       ├── services/           # 外部サービス連携
│       ├── logic/              # ビジネスロジック
│       └── utils/              # ユーティリティ
├── .env.example                # 環境変数テンプレート
├── requirements.txt            # 依存パッケージ
└── README.md                   # このファイル
```

## ライセンス

MIT License
