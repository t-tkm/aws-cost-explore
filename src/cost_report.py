# src/cost_report.py
import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import Tuple, List, Dict, Any, Optional

import boto3
import botocore.exceptions
import requests

# --------------------------------------------------------------------
# 定数定義
# --------------------------------------------------------------------
REGION_NAME = "us-east-1"
GRANULARITY = "MONTHLY"
COST_METRIC = "AmortizedCost"
SERVICE_GROUP_DIMENSION = "SERVICE"
RECORD_TYPE_DIMENSION = "RECORD_TYPE"
CREDIT_RECORD_TYPE = "Credit"

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.disabled = True


# --------------------------------------------------------------------
# 実行時に環境変数を取得する関数
# --------------------------------------------------------------------
def get_config() -> dict:
    """
    環境変数を実行時に取得して返す

    Returns:
        dict: USE_TEAMS_POST, TEAMS_WEBHOOK_URL をキーに含む辞書
    """
    return {
        "USE_TEAMS_POST": os.environ.get("USE_TEAMS_POST", "no").lower() == "yes",
        "TEAMS_WEBHOOK_URL": os.environ.get("TEAMS_WEBHOOK_URL"),
    }


# --------------------------------------------------------------------
# クラス・関数定義
# --------------------------------------------------------------------
class CostExplorer:
    """
    AWS Cost Explorer API を用いてコスト情報を取得するクラス。
    """

    def __init__(self, client: boto3.client) -> None:
        self.client = client

    def get_cost_and_usage(
        self,
        period: Dict[str, str],
        include_credit: bool,
        group_by_dimension: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        指定期間のコストと使用状況を取得する。
        """
        try:
            filter_params: Dict[str, Any] = {}
            if not include_credit:
                filter_params = {
                    "Filter": {
                        "Not": {
                            "Dimensions": {
                                "Key": RECORD_TYPE_DIMENSION,
                                "Values": [CREDIT_RECORD_TYPE]
                            }
                        }
                    }
                }

            group_by = []
            if group_by_dimension:
                group_by = [{"Type": "DIMENSION", "Key": group_by_dimension}]

            response = self.client.get_cost_and_usage(
                TimePeriod=period,
                Granularity=GRANULARITY,
                Metrics=[COST_METRIC],
                GroupBy=group_by,
                **filter_params
            )
            return response["ResultsByTime"][0]

        except botocore.exceptions.ClientError as e:
            logger.error(f"Failed to fetch cost and usage data: {e}")
            raise RuntimeError(f"Error calling AWS Cost Explorer API: {e}") from e

    def get_total_cost(self, cost_and_usage_data: Dict[str, Any]) -> float:
        """
        コストと使用状況のデータから合計費用を取得する。
        """
        try:
            if not cost_and_usage_data.get("Total"):
                total_cost = sum(
                    max(0, float(group["Metrics"][COST_METRIC]["Amount"]))
                    for group in cost_and_usage_data.get("Groups", [])
                )
                logger.info(f"Calculated total cost from Groups: {total_cost:.2f} USD")
                return total_cost

            return float(cost_and_usage_data["Total"][COST_METRIC]["Amount"])

        except KeyError as e:
            logger.error(f"Metric '{COST_METRIC}' is missing: {cost_and_usage_data}")
            return 0.0

    def get_service_costs(self, cost_and_usage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        コストと使用状況のデータからサービスごとの費用を取得する。
        """
        service_groups = cost_and_usage_data.get("Groups", [])
        result = []
        for item in service_groups:
            billing_amount = float(item["Metrics"][COST_METRIC]["Amount"])
            result.append({
                "service_name": item["Keys"][0],
                "billing": billing_amount
            })
        return result


def get_client() -> boto3.client:
    """
    boto3 Cost Explorer クライアントを返す。
    """
    return boto3.client("ce", region_name=REGION_NAME)


def get_date_range() -> Tuple[str, str]:
    """
    集計期間を取得する。
    """
    start_date = date.today().replace(day=1).isoformat()
    end_date = date.today().isoformat()
    return start_date, end_date


def format_service_costs(service_billings: List[Dict[str, Any]]) -> List[str]:
    """
    サービスごとの費用を表示用に整形する。
    """
    formatted_services = []
    for item in service_billings:
        billing = item["billing"]
        if billing >= 0.01:
            formatted_services.append(f"- {item['service_name']}: {billing:.2f} USD")
        else:
            logger.debug(f"Excluded negligible cost: {item['service_name']} ({billing:.5f})")
    return formatted_services


def handle_cost_report(
    explorer: CostExplorer,
    period: Dict[str, str],
    include_credit: bool,
    start_day: str,
    end_day: str
) -> Tuple[str, List[str]]:
    """
    費用レポート（クレジット適用前/後）の取得と整形を行う。
    """
    cost_and_usage = explorer.get_cost_and_usage(
        period,
        include_credit=include_credit,
        group_by_dimension=SERVICE_GROUP_DIMENSION
    )
    total_cost = explorer.get_total_cost(cost_and_usage)
    services_cost = explorer.get_service_costs(cost_and_usage)
    formatted_services = format_service_costs(services_cost)

    credit_text = "後" if include_credit else "前"
    title = f"{start_day}～{end_day}のクレジット適用{credit_text}費用は、{total_cost:.2f} USD です。"
    return title, formatted_services


def print_report(title: str, services_cost: List[str]) -> None:
    """
    レポートを標準出力に表示する。
    """
    print("------------------------------------------------------")
    print(title)
    if services_cost:
        print("\n".join(services_cost))
    else:
        print("サービスごとの費用データはありません。")
    print("------------------------------------------------------\n")

def post_to_teams(title: str, services_cost: List[str]) -> None:
    """
    Teams WebhookにAdaptive Card形式でメッセージを送信する。
    """
    teams_webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not teams_webhook_url:
        raise ValueError("TEAMS_WEBHOOK_URL is環境変数で設定されていません。")

    # サービスごとの費用データを1行ずつ整形
    services_text = "\n".join(services_cost) if services_cost else "サービスごとの費用データはありません。"

    # Adaptive Card形式のメッセージを作成
    message = {
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"### {title}\n\n{services_text}",
                            "wrap": True,
                            "markdown": True
                        }
                    ]
                }
            }
        ]
    }

    # Teams WebhookにPOSTリクエストを送信
    try:
        response = requests.post(
            url=teams_webhook_url,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        logger.info("Teamsへの通知に成功しました。")
    except requests.exceptions.RequestException as e:
        logger.error(f"Teams Webhookへの通知に失敗しました: {e}")
        raise RuntimeError("Teams通知に失敗しました。") from e



def main() -> None:
    """
    メイン関数。
    """
    config = get_config()
    use_teams_post = config["USE_TEAMS_POST"]
    teams_webhook_url = config["TEAMS_WEBHOOK_URL"]

    # USE_TEAMS_POST が True なら TEAMS_WEBHOOK_URL が必要
    if use_teams_post and not teams_webhook_url:
        raise ValueError("TEAMS_WEBHOOK_URL is not set in the environment variables.")

    # boto3 CostExplorer クライアントをモック化できるよう必ず get_client() 経由にする
    client = get_client()
    explorer = CostExplorer(client)

    start_date, end_date = get_date_range()
    period = {"Start": start_date, "End": end_date}
    start_day_str = datetime.strptime(start_date, "%Y-%m-%d").strftime("%m/%d")
    end_day_str = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%m/%d")

    # --- クレジット適用後 ---
    title_after, services_after = handle_cost_report(
        explorer, period, include_credit=True, start_day=start_day_str, end_day=end_day_str
    )
    print_report(title_after, services_after)
    if use_teams_post:
        post_to_teams(title_after, services_after)

    # --- クレジット適用前 ---
    title_before, services_before = handle_cost_report(
        explorer, period, include_credit=False, start_day=start_day_str, end_day=end_day_str
    )
    print_report(title_before, services_before)
    if use_teams_post:
        post_to_teams(title_before, services_before)


if __name__ == "__main__":
    main()
