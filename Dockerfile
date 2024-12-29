FROM python:3.11-slim as base

# 作業ディレクトリを設定
WORKDIR /app

# ホスト側のrequirements.txtを先にコピー
# 依存パッケージのインストールをキャッシュさせるためにコードコピーより先に実行する
COPY requirements.txt .

# 必要ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー (src, testsを含む)
COPY src/ ./src
COPY tests/ ./tests

# pytestを実行するステージ
FROM base as test
# PYTHONPATHにsrcを追加
ENV PYTHONPATH="/app/src"
WORKDIR /app
# pytest実行
RUN pytest --maxfail=1 --disable-warnings -v tests

# 本番環境用ステージ (マルチステージビルド)
# FROM base as prod

# テストが失敗したら本番環境用ステージに移行しない
FROM test as prod 
WORKDIR /app

# 実行コマンドを定義 (例: メインアプリを実行)
CMD ["python", "src/cost_report.py"]