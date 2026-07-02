"""ETL パイプラインのエントリーポイント。

各データソースを抽出・加工し、BigQuery のテーブルへ書き込む。

実行:
    python main.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from etl import (
    aggregate,
    auth,
    bigquery_writer,
    config,
    event,
    goal,
    mcs,
    meetup,
    order,
    report,
    shiruru,
    user,
)


def main():
    # ------------------------------------------------------------------
    # 認証（サービスアカウント）
    # ------------------------------------------------------------------
    gc = auth.get_gspread_client()
    forms_service = auth.get_forms_service()
    bq_client = auth.get_bigquery_client()

    # ------------------------------------------------------------------
    # 抽出・加工
    # ------------------------------------------------------------------
    print("=== 参加データ ===")
    df2, bq_meetup = meetup.build(gc)

    print("=== 来店データ ===")
    df4, bq_order = order.build(gc)

    print("=== イベントデータ ===")
    bq_event = event.build(gc)

    print("=== 日報データ（旧フォーム） ===")
    bq_report, df9_old, form_structure_old = report.build_old(forms_service)

    print("=== 日報データ（新フォーム） ===")
    bq_report2 = report.build_new(forms_service)

    print("=== 日次データ集計 ===")
    df_daily = aggregate.build(df4, bq_meetup)

    print("=== 個人データ ===")
    bq_user = user.build(df4, df2)

    print("=== MCS ===")
    bq_mcs = mcs.build(gc)

    print("=== SHIRURU ===")
    bq_srr = shiruru.build(gc)

    print("=== 目標値 ===")
    bq_goal, bq_goal_monthly = goal.build(gc)

    # 店舗別日報シートの書き出し（config で URL を設定した場合のみ）
    if config.STORE_REPORT_SPREADSHEET_URL:
        print("=== 店舗別日報シート書き出し ===")
        report.write_store_report_sheets(
            gc,
            df9_old,
            form_structure_old,
            bq_report,
            config.STORE_REPORT_SPREADSHEET_URL,
            config.STORE_REPORT_START_DATE,
        )

    # ------------------------------------------------------------------
    # BigQuery へ書き込み
    # ------------------------------------------------------------------
    print("=== BigQuery 書き込み ===")
    writer = bigquery_writer.BigQueryWriter(bq_client)
    t = config.TABLE_NAMES
    writer.write(bq_order, t["order"])
    writer.write(bq_meetup, t["meetup"])
    # イベントテーブルは元ノートブックでも書き込みを無効化しているため既定ではスキップ
    # writer.write(bq_event, t["event"])
    writer.write(bq_report, t["report"])
    writer.write(bq_report2, t["report_new"])
    writer.write(df_daily, t["daily"])
    writer.write(bq_user, t["user"])
    writer.write(bq_goal, t["goal"])
    writer.write(bq_goal_monthly, t["goal_monthly"])
    writer.write(bq_mcs, t["mcs"])
    writer.write(bq_srr, t["shiruru"])

    # ------------------------------------------------------------------
    # サマリー
    # ------------------------------------------------------------------
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    print(f"最終更新日時: {now}")

    last_online = bq_meetup[
        (bq_meetup["attendance"] == 1) & (bq_meetup["meetup_type"] == "オンライン")
    ]["start_at"].max()
    last_taimen = bq_meetup[
        (bq_meetup["attendance"] == 1) & (bq_meetup["meetup_type"] == "対面")
    ]["start_at"].max()
    last_order = bq_order["ordered_at"].max()
    last_mcs = bq_mcs[bq_mcs["viewing"] > 0]["date"].max()

    print("各項目最終日時")
    print(f"オンライン参加: {last_online}")
    print(f"対面参加: {last_taimen}")
    print(f"注文: {last_order}")
    print(f"MCS: {last_mcs}")


if __name__ == "__main__":
    main()
