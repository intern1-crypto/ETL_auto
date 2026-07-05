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
    drive_service = auth.get_drive_service()

    writer = bigquery_writer.BigQueryWriter(bq_client)
    t = config.TABLE_NAMES

    # ------------------------------------------------------------------
    # 抽出・加工・BigQuery 書き込み（処理ごと）
    # ------------------------------------------------------------------
    print("=== 参加データ ===")
    df_meetup, bq_meetup = meetup.build(gc, drive_service)
    writer.write(bq_meetup, t["meetup"])

    print("=== 来店データ ===")
    df_order, bq_order = order.build(gc, drive_service)
    writer.write(bq_order, t["order"])

    print("=== イベントデータ ===")
    bq_event = event.build(gc, drive_service)
    # イベントテーブルは元ノートブックでも書き込みを無効化しているため既定ではスキップ
    # writer.write(bq_event, t["event"])

    print("=== 日報データ ===")
    bq_report_new, df_report_new, form_structure_new = report.build_new(forms_service)
    writer.write(bq_report_new, t["report_new"])

    print("=== 日次データ集計 ===")
    df_daily = aggregate.build(df_order, bq_meetup)
    writer.write(df_daily, t["daily"])

    print("=== 個人データ ===")
    bq_user = user.build(df_order, df_meetup)
    writer.write(bq_user, t["user"])

    print("=== MCS ===")
    bq_mcs = mcs.build(gc)
    writer.write(bq_mcs, t["mcs"])

    print("=== SHIRURU ===")
    bq_srr = shiruru.build(gc)
    writer.write(bq_srr, t["shiruru"])

    print("=== 目標値 ===")
    bq_goal, bq_goal_monthly = goal.build(gc)
    writer.write(bq_goal, t["goal"])
    writer.write(bq_goal_monthly, t["goal_monthly"])

    # 店舗別日報シートの書き出し（config で URL を設定した場合のみ）
    if config.STORE_REPORT_SPREADSHEET_URL:
        print("=== 店舗別日報シート書き出し ===")
        report.write_store_report_sheets(
            gc,
            df_report_new,
            form_structure_new,
            bq_report_new,
            config.STORE_REPORT_SPREADSHEET_URL,
            config.STORE_REPORT_START_DATE,
        )

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
