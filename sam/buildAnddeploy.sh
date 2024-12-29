#!/bin/sh
set -eu

# .env ファイルの読み込み
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
else
    echo "Error: ../.env file not found."
    exit 1
fi

# 必要な環境変数の確認
: "${S3_BUCKET:?S3_BUCKET is not set in .env}"
: "${TEAMS_WEBHOOK_URL:?TEAMS_WEBHOOK_URL is not set in .env}"
: "${USE_TEAMS_POST:?USE_TEAMS_POST is not set in .env}"

# エラーハンドリング
trap 'echo "An error occurred. Exiting..."' ERR

echo "Start sam build command."
sam build
echo "SAM build completed successfully."

echo "Start sam package command."
sam package \
    --output-template-file packaged.yaml \
    --s3-bucket $S3_BUCKET
echo "SAM package completed successfully."

echo "Start sam deploy command."
sam deploy \
    --template-file packaged.yaml \
    --stack-name NotifyBillingToTeams \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides TeamsWebhookUrl=$TEAMS_WEBHOOK_URL UseTeamsPost=$USE_TEAMS_POST
echo "SAM deploy completed successfully."
