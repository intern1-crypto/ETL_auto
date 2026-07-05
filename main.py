"""ETL パイプラインのエントリーポイント。

各データソースを抽出・加工し、BigQuery のテーブルへ書き込む。

実行:
    python main.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from etl import auth, bigquery_writer, config, pipeline, report


def main():
    # ------------------------------------------------------------------
    # 抽出・加工
    # ------------------------------------------------------------------
    bq_tables, extra = pipeline.build_all()

    # ------------------------------------------------------------------
    # BigQuery 書き込み
    # ------------------------------------------------------------------
    bq_client = auth.get_bigquery_client()
    writer = bigquery_writer.BigQueryWriter(bq_client)
    t = config.TABLE_NAMES

    for key in [
        "meetup", "order", "report_new", "daily", "user",
        "mcs", "shiruru", "goal", "goal_monthly",
    ]:
        writer.write(bq_tables[key], t[key])
    # イベントテーブルは元ノートブックでも書き込みを無効化しているため既定ではスキップ
    # writer.write(bq_tables["event"], t["event"])

    # 店舗別日報シートの書き出し（config で URL を設定した場合のみ）
    if config.STORE_REPORT_SPREADSHEET_URL:
        print("=== 店舗別日報シート書き出し ===")
        report.write_store_report_sheets(
            extra["gc"],
            extra["df_report_new"],
            extra["form_structure_new"],
            bq_tables["report_new"],
            config.STORE_REPORT_SPREADSHEET_URL,
            config.STORE_REPORT_START_DATE,
        )

    # ------------------------------------------------------------------
    # サマリー
    # ------------------------------------------------------------------
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    print(f"最終更新日時: {now}")

    bq_meetup = bq_tables["meetup"]
    bq_order = bq_tables["order"]
    bq_mcs = bq_tables["mcs"]

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
