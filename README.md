# 小学生向け日本のニュースBot

小学生や保護者向けに、最新の日本の国内ニュースを簡単な言葉で毎日自動投稿するNote Botです。

## 概要

このアプリケーションは、OpenAI Agents SDKを使用して以下の機能を提供します：

1. 最新の日本のニュースを自動収集
2. 小学校低学年（1〜3年生）でも理解できる言葉に変換
3. note.comに自動投稿

## 特徴

- **小学生向け**：難しい言葉や概念を簡単に説明
- **教育的**：複雑なトピックも理解しやすく解説
- **信頼性**：信頼できるニュースソースのみを使用
- **安全**：子ども向けに不適切なコンテンツをフィルタリング
- **自動化**：毎日決まった時間に自動で投稿

## システム要件

- Python 3.8以上
- インターネット接続
- noteアカウント
- OpenAI API Key
- News API Key

## インストール

1. リポジトリをクローン：

```bash
git clone https://github.com/yourusername/elementary-news-bot.git
cd elementary-news-bot
```

2. 必要なパッケージをインストール：

```bash
pip install -r requirements.txt
```

3. 設定ファイルを作成：

```bash
cp config.template.json config.json
```

4. `config.json`を編集して必要な情報を入力：
   - OpenAI API Key
   - News API Key
   - noteのログイン情報
   - 投稿時間

## 使い方

### 今すぐ実行

```bash
python main.py --now
```

### スケジューラーとして実行

```bash
python main.py
```

デフォルトでは、`config.json`で指定した時間（デフォルト：08:00）に毎日記事を投稿します。

## プロジェクト構造

```
elementary-news-bot/
├── main.py                 # メインアプリケーション
├── config.template.json    # 設定テンプレート
├── config.json             # 実際の設定ファイル（gitignore対象）
├── requirements.txt        # 必要なパッケージ
├── app.log                 # アプリケーションログ
├── models/
│   └── article.py          # 記事モデル
└── services/
    └── note_poster_service.py  # note投稿サービス
```

## 設定オプション

- `openai_api_key`: OpenAI APIキー
- `news_api_key`: News APIキー
- `note_email`: noteアカウントのメールアドレス
- `note_password`: noteアカウントのパスワード
- `post_time`: 投稿時間（例：`08:00`）
- `model`: 使用するOpenAIモデル（デフォルト：`gpt-4o`）
- `log_level`: ログレベル（`INFO`, `DEBUG`, `ERROR`など）

## 環境変数

設定ファイルの代わりに環境変数も使用できます：

- `OPENAI_API_KEY`
- `NEWS_API_KEY`
- `NOTE_EMAIL`
- `NOTE_PASSWORD`
- `POST_TIME`
- `OPENAI_MODEL`

## 注意事項

- このアプリケーションは教育目的のニュース配信を目的としています
- 適切なコンテンツフィルタリングを行っていますが、常に保護者の監視が推奨されます
- API使用量に注意してください（OpenAI APIとNews APIの両方に使用制限があります）

## ライセンス

MIT

## 連絡先

質問や提案がありましたら、Issueを作成するか以下にお問い合わせください：
your.email@example.com