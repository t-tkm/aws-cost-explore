# aws-cost-explore

このリポジトリは、AWS の Cost Explorer を利用して**指定期間の費用・使用状況を取得し、レポートを生成**する Python スクリプトです。  
標準出力および Microsoft Teams Webhook への通知にも対応しています。

---

## 目次

- [概要](#概要)
- [機能一覧](#機能一覧)
- [必要なもの (Prerequisites)](#必要なもの-prerequisites)
- [セットアップ (Installation)](#セットアップ-installation)
- [使い方 (Usage)](#使い方-usage)
  - [環境変数の設定](#環境変数の設定)
  - [実行例](#実行例)
- [ローカル開発 (Local Development)](#ローカル開発-local-development)
  - [テストの実行 (pytest)](#テストの実行-pytest)
- [FAQ](#faq)
- [ライセンス](#ライセンス)

---

## 概要

本スクリプトは以下のようなフローを想定しています:

1. **AWS Cost Explorer** から今月分のコストを取得  
2. クレジット適用前と適用後の費用を計算  
3. サービスごとの費用内訳を整形  
4. **標準出力** と、必要に応じて **Microsoft Teams** (Webhook) へレポート送信  

これにより、AWSコストを手軽に可視化・共有し、不要なコストの早期発見や管理に役立てることができます。

---

## 機能一覧

- **CostExplorer クラス**  
  - `get_cost_and_usage()`: 指定期間のコストと使用状況を取得  
  - `get_total_cost()`: レスポンスから合計費用を算出  
  - `get_service_costs()`: サービスごとの費用をリスト化  

- **ラッパ関数**  
  - `handle_cost_report()`: 取得データを整形して、クレジット適用前/後のタイトルやサービス一覧を作成  

- **表示・投稿処理**  
  - `print_report()`: コマンドライン上でのレポート表示  
  - `post_to_teams()`: Teams Webhook へレポート送信  

- **メイン実行**  
  - `main()`: 上記機能を順番に呼び出し、環境変数の確認・コスト取得・表示・Teams投稿を一括実行

---

## 必要なもの (Prerequisites)

- Python 3.8 以上 (推奨)
- AWS CLI または boto3 用の AWS 認証情報が設定されていること  
  - 例: `~/.aws/credentials` にアクセスキーやシークレットキーを記載
- （オプション）Microsoft Teams Webhook URL  
  - Teams への通知を行う場合に必要

---

## セットアップ (Installation)

1. **リポジトリのクローン**

   ```bash
   git clone https://github.com/<your-org>/<this-repo>.git
   cd this-repo
   ```

2. **仮想環境の作成 & 有効化**

   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS / Linux
   # Windows の場合: venv\Scripts\activate
   ```

3. **依存パッケージをインストール**

   ```bash
   pip install -r requirements.txt
   ```
   - `boto3`, `requests`, `pytest` などがインストールされます。

---

## 使い方 (Usage)

### 環境変数の設定

- **USE_TEAMS_POST**  
  - `"yes"` の場合は Teams Webhook への投稿を行う。  
  - `"no"` の場合は投稿しない（デフォルト）。
- **TEAMS_WEBHOOK_URL**  
  - Teams 投稿を行う場合の Webhook URL。  
  - `USE_TEAMS_POST="yes"` かつこれが未設定の場合は `ValueError` が発生。

#### 例: `.env` ファイル
```bash
USE_TEAMS_POST=yes
TEAMS_WEBHOOK_URL=https://dummy.webhook.microsoft.com/<your-webhook-url>
```

### 実行例

```bash
# Teams へ投稿しない（デフォルト）場合
python src/cost_report.py

# Teams へ投稿する場合
export USE_TEAMS_POST=yes
export TEAMS_WEBHOOK_URL="https://dummy.webhook.microsoft.com/xxxx"
python src/cost_report.py
```

実行後は、標準出力に以下のようなレポートが表示されます。  
`USE_TEAMS_POST=yes` なら同一内容が Teams にも投稿されます。

```
------------------------------------------------------
02/01～02/08のクレジット適用後費用は、100.00 USD です。
- Amazon EC2: 80.00 USD
- Amazon S3: 20.00 USD
------------------------------------------------------

------------------------------------------------------
02/01～02/08のクレジット適用前費用は、120.00 USD です。
- Amazon EC2: 100.00 USD
- Amazon S3: 20.00 USD
------------------------------------------------------
```

---

## ローカル開発 (Local Development)

1. **リポジトリをクローン** (済みの場合は不要)
   ```bash
   git clone https://github.com/<your-org>/<this-repo>.git
   cd this-repo
   ```

2. **仮想環境の作成とパッケージのインストール**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS / Linux
   pip install -r requirements.txt
   ```

3. **スクリプトの編集**
   - 主要なロジックは `src/cost_report.py` に含まれています。  
   - 認証情報などは `~/.aws/credentials` や環境変数など、boto3 が認識できる形で設定してください。

4. **テストの実行 (pytest)**

   ```bash
   pytest
   ```
   - `tests/` ディレクトリ以下にある各テストが実行されます。
   - すべて成功すると以下のように出力:
     ```
     ============================= test session starts ==============================
     platform darwin -- Python 3.10.12, pytest-8.3.4, pluggy-1.5.0
     collected 11 items

     tests/test_cost_report.py ...........                                   [100%]

     ============================== 11 passed in 2.28s ==============================
     ```

---

## FAQ

### Q1. `NoCredentialsError: Unable to locate credentials` が出る
A. `boto3` が AWS 認証情報を見つけられない場合に発生します。  
   - `aws configure` で `~/.aws/credentials` に設定する  
   - または `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` を環境変数に設定する  
   などの方法で認証情報を設定してください。

### Q2. Teams に投稿しようとすると `ValueError` が出る
A. `USE_TEAMS_POST="yes"` の際は、`TEAMS_WEBHOOK_URL` を必ず設定してください。  
   例:
   ```bash
   export USE_TEAMS_POST=yes
   export TEAMS_WEBHOOK_URL="https://dummy.webhook.microsoft.com/xxxx"
   python src/cost_report.py
   ```

### Q3. CI環境で実行したい
A. GitHub Actions などの CI であれば、AWS 認証情報と Teams Webhook URL (任意) を含む環境変数を設定し、同様の手順で `pytest` を実行することが可能です。

---

## ライセンス

このプロジェクトは [MIT License](./LICENSE) のもとで公開されています。  
詳細は [LICENSE](./LICENSE) ファイルを参照してください。