"""指定期間のデータ反映状況を確認する。

BigQuery の現在のデータをもとに、開始年月〜終了年月の期間について以下を確認する。

  来店   : 期間内の最終オーダー日時が、終了年月の翌月以降なら OK
  Meetup : 期間内の「参加予定」の最初の開始日時が、終了年月の翌月以降
           または期間内に「参加予定」のデータが存在しなければ OK
  MCS    : 期間内の最終日付が、終了年月の翌月以降なら OK

いずれも OK でなければ、判定に使った実際の日時を表示する。

実行:
    python scripts/check_period_status.py
    （実行すると開始年月・終了年月の入力を求められる）
"""

import re
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from etl import auth, config  # noqa: E402（sys.path 設定後に import する必要があるため）

YYYYMM_RE = re.compile(r"^\d{6}$")


def _parse_yyyymm(value):
    if not YYYYMM_RE.match(value):
        raise ValueError(f"yyyymm 形式で指定してください: {value}")
    year, month = int(value[:4]), int(value[4:])
    if not 1 <= month <= 12:
        raise ValueError(f"月の値が不正です: {value}")
    return year, month


def _input_yyyymm(prompt):
    while True:
        value = input(prompt).strip()
        try:
            return _parse_yyyymm(value)
        except ValueError as e:
            print(e)


def _month_start(year, month):
    return date(year, month, 1)


def _next_month_start(year, month):
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _fetch_status(client, start_date, threshold):
    project = config.BIGQUERY_PROJECT_ID
    dataset = config.BIGQUERY_DATASET
    t = config.TABLE_NAMES
    start_str = start_date.strftime("%Y-%m-%d 00:00:00")
    threshold_str = threshold.strftime("%Y-%m-%d 00:00:00")

    def _scalar(sql):
        rows = list(client.query(sql).result())
        return rows[0]["value"] if rows else None

    last_order_at = _scalar(f"""
        SELECT MAX(ordered_at) AS value
        FROM `{project}.{dataset}.{t['order']}`
        WHERE ordered_at >= '{start_str}'
    """)

    first_planned_at = _scalar(f"""
        SELECT MIN(start_at) AS value
        FROM `{project}.{dataset}.{t['meetup']}`
        WHERE planned_attendance = 1 AND start_at >= '{start_str}'
    """)

    planned_breakdown = list(client.query(f"""
        SELECT
            store_code,
            COUNT(*) AS count,
            SUM(pickup_flag + 1) AS points
        FROM `{project}.{dataset}.{t['meetup']}`
        WHERE planned_attendance = 1
          AND start_at >= '{start_str}'
          AND start_at < '{threshold_str}'
        GROUP BY store_code
        ORDER BY store_code
    """).result())

    last_mcs_date = _scalar(f"""
        SELECT MAX(date) AS value
        FROM `{project}.{dataset}.{t['mcs']}`
        WHERE date >= '{start_date.isoformat()}'
    """)

    return last_order_at, first_planned_at, planned_breakdown, last_mcs_date


def main():
    updated = input("データを更新しましたか(y/n)：").strip().lower()
    if updated != "y":
        print("main.py を実行してください")
        return

    print("=== 表彰の指標確定確認 ===")
    start_yyyymm = _input_yyyymm("表彰開始年月を yyyymm 形式で入力してください（例: 202605）: ")
    end_yyyymm = _input_yyyymm("表彰終了年月を yyyymm 形式で入力してください（例: 202607）: ")

    start_date = _month_start(*start_yyyymm)
    threshold = _next_month_start(*end_yyyymm)  # 終了年月の翌月1日（＝終了年月の最終日の翌日）

    print("\n# 確認方法")
    print("来店: ✅ または最終オーダー日時が期間内の最終営業日ならOK")
    print("MCS: ✅ または最終視聴日が期間内の最終営業日ならOK")
    print("Meetup: ✅ ならOK")

    client = auth.get_bigquery_client()
    last_order_at, first_planned_at, planned_breakdown, last_mcs_date = _fetch_status(
        client, start_date, threshold
    )

    print(f"\n# 期間データ: {start_yyyymm[0]}-{start_yyyymm[1]:02d} 〜 "
          f"{end_yyyymm[0]}-{end_yyyymm[1]:02d} ")

    if last_order_at is not None and last_order_at.date() >= threshold:
        print("来店: ✅")
    else:
        print(f"来店: {last_order_at}（最終オーダー日時）")

    if last_mcs_date is not None and last_mcs_date >= threshold:
        print("MCS: ✅")
    else:
        print(f"MCS: {last_mcs_date}（最終視聴日）")

    if first_planned_at is None or first_planned_at.date() >= threshold:
        print("Meetup: ✅")
    else:
        total_count = sum(row["count"] for row in planned_breakdown)
        total_points = sum(row["points"] for row in planned_breakdown)
        print(f"Meetup: 未確定件数: {total_count}件 / {total_points}pt")
        print("店舗番号  件数  ポイント")
        for row in planned_breakdown:
            print(
                f"{int(row['store_code']):>8}{row['count']:>6}{row['points']:>8}"
            )


if __name__ == "__main__":
    main()
