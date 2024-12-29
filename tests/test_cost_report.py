# test
# tests/test_cost_report.py
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# テスト対象コードをインポート
import cost_report  # 例: src/cost_report.py を "cost_report" モジュールとして扱う場合

@pytest.fixture
def mock_ce_client():
    """
    boto3 CE クライアント (self.client) をモックにした MagicMock を返すフィクスチャ。
    """
    return MagicMock()

@pytest.fixture
def explorer(mock_ce_client):
    """
    コスト取得クラスを生成して返すフィクスチャ。
    """
    return cost_report.CostExplorer(mock_ce_client)

@pytest.fixture
def sample_cost_response():
    """
    サンプルの get_cost_and_usage レスポンスを返すフィクスチャ。
    """
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2024-12-01", "End": "2024-12-28"},
                "Total": {cost_report.COST_METRIC: {"Amount": "123.45"}},
                "Groups": [
                    {
                        "Keys": ["Amazon EC2"],
                        "Metrics": {cost_report.COST_METRIC: {"Amount": "100.0"}}
                    },
                    {
                        "Keys": ["Amazon S3"],
                        "Metrics": {cost_report.COST_METRIC: {"Amount": "23.45"}}
                    }
                ]
            }
        ]
    }

def test_get_cost_and_usage_include_credit(explorer, mock_ce_client, sample_cost_response):
    """
    include_credit=True の場合、フィルタなしでAPIを呼び出すかどうかをテスト。
    """
    mock_ce_client.get_cost_and_usage.return_value = sample_cost_response
    period = {"Start": "2024-12-01", "End": "2024-12-28"}

    resp = explorer.get_cost_and_usage(period, include_credit=True)

    assert resp == sample_cost_response["ResultsByTime"][0]
    mock_ce_client.get_cost_and_usage.assert_called_once_with(
        TimePeriod=period,
        Granularity=cost_report.GRANULARITY,
        Metrics=[cost_report.COST_METRIC],
        GroupBy=[]
    )

def test_get_cost_and_usage_exclude_credit(explorer, mock_ce_client, sample_cost_response):
    """
    include_credit=False の場合、Not フィルタが使われるかをテスト。
    """
    mock_ce_client.get_cost_and_usage.return_value = sample_cost_response
    period = {"Start": "2024-12-01", "End": "2024-12-28"}

    resp = explorer.get_cost_and_usage(period, include_credit=False)

    assert resp == sample_cost_response["ResultsByTime"][0]
    expected_filter = {
        "Filter": {
            "Not": {
                "Dimensions": {
                    "Key": cost_report.RECORD_TYPE_DIMENSION,
                    "Values": [cost_report.CREDIT_RECORD_TYPE]
                }
            }
        }
    }
    mock_ce_client.get_cost_and_usage.assert_called_once_with(
        TimePeriod=period,
        Granularity=cost_report.GRANULARITY,
        Metrics=[cost_report.COST_METRIC],
        GroupBy=[],
        **expected_filter
    )

def test_get_total_cost_with_total(explorer):
    """
    get_total_cost のテスト: 'Total' が存在する場合。
    """
    data = {
        "Total": {cost_report.COST_METRIC: {"Amount": "45.67"}},
        "Groups": []
    }
    total = explorer.get_total_cost(data)
    assert total == 45.67

def test_get_total_cost_without_total(explorer):
    """
    get_total_cost のテスト: 'Total' が存在しない場合 (Groups の合計)。
    """
    data = {
        "Groups": [
            {"Metrics": {cost_report.COST_METRIC: {"Amount": "12.3"}}},
            {"Metrics": {cost_report.COST_METRIC: {"Amount": "0.7"}}}
        ]
    }
    total = explorer.get_total_cost(data)
    assert total == 13.0

def test_get_total_cost_with_zero_cost(explorer):
    """
    get_total_cost のテスト: 'Total' が 0 の場合。
    """
    data = {
        "Total": {cost_report.COST_METRIC: {"Amount": "0"}},
        "Groups": []
    }
    total = explorer.get_total_cost(data)
    assert total == 0.0

def test_get_service_costs(explorer):
    """
    get_service_costs のテスト。
    """
    data = {
        "Groups": [
            {
                "Keys": ["Amazon EC2"],
                "Metrics": {cost_report.COST_METRIC: {"Amount": "100.0"}}
            },
            {
                "Keys": ["Amazon S3"],
                "Metrics": {cost_report.COST_METRIC: {"Amount": "23.45"}}
            }
        ]
    }
    services = explorer.get_service_costs(data)
    assert len(services) == 2
    assert services[0]["service_name"] == "Amazon EC2"
    assert services[0]["billing"] == 100.0
    assert services[1]["service_name"] == "Amazon S3"
    assert services[1]["billing"] == 23.45

def test_format_service_costs():
    """
    0.01 USD 未満を除外し、表示用文字列に整形できるか。
    """
    data = [
        {"service_name": "Amazon EC2", "billing": 100.0},
        {"service_name": "Amazon S3", "billing": 0.009},  # 除外対象
    ]
    formatted = cost_report.format_service_costs(data)
    assert len(formatted) == 1
    assert "- Amazon EC2: 100.00 USD" in formatted[0]

def test_handle_cost_report(explorer, mock_ce_client):
    """
    handle_cost_report のテスト。
    """
    mock_ce_client.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "Total": {cost_report.COST_METRIC: {"Amount": "50.0"}},
                "Groups": [
                    {
                        "Keys": ["Amazon EC2"],
                        "Metrics": {cost_report.COST_METRIC: {"Amount": "30.0"}}
                    },
                    {
                        "Keys": ["Amazon S3"],
                        "Metrics": {cost_report.COST_METRIC: {"Amount": "20.0"}}
                    }
                ]
            }
        ]
    }
    period = {"Start": "2024-12-01", "End": "2024-12-28"}

    title, service_list = cost_report.handle_cost_report(
        explorer,
        period,
        include_credit=True,
        start_day="12/01",
        end_day="12/27"
    )

    assert "クレジット適用後費用は、50.00 USD" in title
    assert len(service_list) == 2
    assert "- Amazon EC2: 30.00 USD" in service_list[0]
    assert "- Amazon S3: 20.00 USD" in service_list[1]

# @patch('cost_report.requests.post')
# def test_post_to_teams(mock_post):
#     """
#     post_to_teams のテスト。
#     """
#     # 環境変数をモック
#     with patch.dict(os.environ, {"TEAMS_WEBHOOK_URL": "https://dummy.webhook.microsoft.com/xxxx"}, clear=True):
#         # ダミーのレスポンス
#         mock_response = MagicMock()
#         mock_response.raise_for_status = MagicMock()
#         mock_post.return_value = mock_response

#         title = "Test Title"
#         services = ["- Amazon EC2: 30.00 USD", "- Amazon S3: 20.00 USD"]
#         cost_report.post_to_teams(title, services)

#         # requests.post が正しく呼ばれたかを検証
#         mock_post.assert_called_once()
#         # mock_post() のように呼び出す
#         args, kwargs = mock_post.call_args
#         assert args[0] == "https://dummy.webhook.microsoft.com/xxxx"

#         payload = json.loads(kwargs["data"])
#         assert payload["attachments"][0]["content"]["body"][0]["text"] == f"### {title}\n\n" + "\n".join(services)

def test_post_to_teams_no_url():
    """
    TEAMS_WEBHOOK_URL が設定されていない場合、ValueError を投げるか。
    """
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc:
            cost_report.post_to_teams("Any Title", ["- cost1", "- cost2"])
        assert "TEAMS_WEBHOOK_URL is環境変数で設定されていません。" in str(exc.value)

@pytest.mark.parametrize(
    "use_teams, webhook_url, expect_error, expect_post_calls",
    [
        # 1) Teams投稿あり (クレジット後/前で2回 post_to_teams が呼ばれる想定)
        (True, "https://dummy.webhook.microsoft.com/xxxx", False, 2),
        # 2) Teams投稿ON かつ webhook URL なし => ValueError
        (True, None, True, 0),
        # 3) Teams投稿OFF => post_to_teamsは一切呼ばれない (0回)
        (False, None, False, 0),
    ],
)
def test_main(use_teams, webhook_url, expect_error, expect_post_calls):
    """
    main() 関数での一連のフローをテスト。
    - USE_TEAMS_POST, TEAMS_WEBHOOK_URL の有無による分岐
    - boto3呼び出しとTeams投稿回数
    """
    env_dict = {}
    env_dict["USE_TEAMS_POST"] = "yes" if use_teams else "no"
    if webhook_url is not None:
        env_dict["TEAMS_WEBHOOK_URL"] = webhook_url

    with patch.dict(os.environ, env_dict, clear=True):
        # boto3 クライアント生成をモック => CostExplorer の呼び出しが実際に AWS に行かないように
        with patch.object(cost_report, "get_client") as mock_get_client:
            mock_ce_client = MagicMock()
            mock_get_client.return_value = mock_ce_client

            # 返り値をセット (クレジット前後ともコスト計算できるダミー)
            mock_ce_client.get_cost_and_usage.return_value = {
                "ResultsByTime": [
                    {
                        "Total": {cost_report.COST_METRIC: {"Amount": "100.0"}},
                        "Groups": []
                    }
                ]
            }

            # post_to_teams, print_report もモック
            with patch.object(cost_report, "post_to_teams") as mock_post:
                with patch.object(cost_report, "print_report") as mock_print:
                    if expect_error:
                        # webhook_url が未設定で USE_TEAMS_POST=True => ValueError
                        with pytest.raises(ValueError) as e:
                            cost_report.main()
                        assert "TEAMS_WEBHOOK_URL is not set" in str(e.value)
                    else:
                        cost_report.main()
                        # post_to_teams の呼び出し回数を検証
                        assert mock_post.call_count == expect_post_calls

                        # print_report は クレジット後/前 で 2 回 呼ばれる想定
                        assert mock_print.call_count == 2