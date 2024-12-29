# aws-cost-explore

## Dockerを使用したビルドと起動

### Dockerイメージのビルド
1. プロジェクトのルートディレクトリに移動します。
   ```bash
   cd aws-cost-explore
   ```
2. Dockerイメージをビルドします。
   ```bash
   docker compose build
   ```

### Dockerコンテナの起動
1. Dockerコンテナを起動します。
   ```bash
   docker compose up 

   # コンテナ名など余計なメタ情報をログに出力しない場合はこちらを使用
   docker compose up --no-log-prefix
   ```

### Dockerコンテナの停止
1. Dockerコンテナを停止します。
   ```bash
   docker compose down
   ```