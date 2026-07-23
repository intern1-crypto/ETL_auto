"""ETL パイプラインのエントリーポイント。

各データソースを抽出・加工し、BigQuery のテーブルへ書き込む。

実行:
    python main.py
"""

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from etl import auth, bigquery_writer, config, pipeline, report

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    # ------------------------------------------------------------------
    # 抽出・加工
    # ------------------------------------------------------------------
    bq_tables, extra, errors = pipeline.build_all()

    # ------------------------------------------------------------------
    # BigQuery 書き込み
    # ------------------------------------------------------------------
    bq_client = auth.get_bigquery_client()
    writer = bigquery_writer.BigQueryWriter(bq_client)
    t = config.TABLE_NAMES

    for key in [
        "meetup", "order", "report_new", "daily", "user",
        "mcs", "shiruru", "goal", "goal_monthly", "monthly",
    ]:
        df = bq_tables[key]
        if df is None:
            continue
        try:
            writer.write(df, t[key])
        except Exception as e:
            logging.error("BigQuery 書き込み失敗 [%s]: %s", key, t[key], exc_info=True)
            errors[key] = e
    # イベントテーブルは元ノートブックでも書き込みを無効化しているため既定ではスキップ
    # writer.write(bq_tables["event"], t["event"])

    # 店舗別日報シートの書き出し（config で URL を設定した場合のみ）
    if config.STORE_REPORT_SPREADSHEET_URL and bq_tables["report_new"] is not None:
        try:
            report.write_store_report_sheets(
                extra["gc"],
                extra["df_report_new"],
                extra["form_structure_new"],
                bq_tables["report_new"],
                config.STORE_REPORT_SPREADSHEET_URL,
                config.STORE_REPORT_START_DATE,
            )
        except Exception as e:
            logging.error("店舗別日報シート書き出し失敗", exc_info=True)
            errors["store_report"] = e

    # ------------------------------------------------------------------
    # 完了サマリー
    # ------------------------------------------------------------------
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    succeeded = [k for k in bq_tables if bq_tables[k] is not None and k not in errors]
    print(f"完了: {now.strftime('%Y-%m-%d %H:%M:%S JST')}")
    print(f"成功: {succeeded}")

    # ------------------------------------------------------------------
    # エラーまとめ・終了コード
    # ------------------------------------------------------------------
    if errors:
        print(f"失敗: {list(errors.keys())}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
