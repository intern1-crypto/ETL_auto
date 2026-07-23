"""全データソースの抽出・加工をまとめて行う。

main.py（BigQuery への書き込み）と、確認用スクリプト（ローカル保存）の
両方から共通で利用する。

各データソースは独立して try/except で囲み、一部が失敗しても他の処理は続行する。
失敗したデータソースの値は None になる。
"""

import logging

from . import aggregate, auth, event, goal, mcs, meetup, order, report, shiruru, user

logger = logging.getLogger(__name__)


def build_all():
    """全データソースを抽出・加工し、(bq_tables, extra, errors) を返す。

    bq_tables : {テーブル名: DataFrame | None} の辞書（失敗したものは None）
    extra     : 店舗別日報シート書き出しで使う補助データ
    errors    : {テーブル名: Exception} の辞書（失敗したもののみ）
    """
    gc = auth.get_gspread_client()
    forms_service = auth.get_forms_service()
    drive_service = auth.get_drive_service()

    errors = {}

    try:
        df_meetup, bq_meetup = meetup.build(gc, drive_service)
    except Exception as e:
        logger.error("参加データ (meetup) の抽出に失敗", exc_info=True)
        errors["meetup"] = e
        df_meetup, bq_meetup = None, None

    try:
        df_order, bq_order = order.build(gc, drive_service)
    except Exception as e:
        logger.error("来店データ (order) の抽出に失敗", exc_info=True)
        errors["order"] = e
        df_order, bq_order = None, None

    try:
        bq_event = event.build(gc, drive_service)
    except Exception as e:
        logger.error("イベントデータ (event) の抽出に失敗", exc_info=True)
        errors["event"] = e
        bq_event = None

    try:
        bq_report_new, df_report_new, form_structure_new = report.build_new(forms_service)
    except Exception as e:
        logger.error("日報データ (report_new) の抽出に失敗", exc_info=True)
        errors["report_new"] = e
        bq_report_new, df_report_new, form_structure_new = None, None, None

    # daily・user は meetup と order に依存
    if df_order is not None and bq_meetup is not None:
        try:
            df_daily = aggregate.build(df_order, bq_meetup)
        except Exception as e:
            logger.error("日次データ集計 (daily) の処理に失敗", exc_info=True)
            errors["daily"] = e
            df_daily = None
    else:
        logger.warning("日次データ集計 (daily): 依存データ（order/meetup）の取得失敗のためスキップ")
        df_daily = None

    try:
        bq_goal, bq_goal_monthly = goal.build(gc)
    except Exception as e:
        logger.error("目標値 (goal) の抽出に失敗", exc_info=True)
        errors["goal"] = e
        bq_goal, bq_goal_monthly = None, None

    try:
        bq_mcs = mcs.build(gc)
    except Exception as e:
        logger.error("MCS の抽出に失敗", exc_info=True)
        errors["mcs"] = e
        bq_mcs = None

    try:
        bq_srr = shiruru.build(gc)
    except Exception as e:
        logger.error("SHIRURU の抽出に失敗", exc_info=True)
        errors["shiruru"] = e
        bq_srr = None

    # monthly は meetup と order に依存（目標値・MCS・SHIRURUは取得できていれば結合、失敗していれば省略）
    if df_order is not None and bq_meetup is not None:
        try:
            df_monthly = aggregate.build_monthly(
                df_order, bq_meetup, bq_goal_monthly, bq_mcs, bq_srr
            )
        except Exception as e:
            logger.error("月次データ集計 (monthly) の処理に失敗", exc_info=True)
            errors["monthly"] = e
            df_monthly = None
    else:
        logger.warning("月次データ集計 (monthly): 依存データ（order/meetup）の取得失敗のためスキップ")
        df_monthly = None

    if df_order is not None and df_meetup is not None:
        try:
            bq_user = user.build(df_order, df_meetup)
        except Exception as e:
            logger.error("個人データ (user) の処理に失敗", exc_info=True)
            errors["user"] = e
            bq_user = None
    else:
        logger.warning("個人データ (user): 依存データ（order/meetup）の取得失敗のためスキップ")
        bq_user = None

    bq_tables = {
        "meetup": bq_meetup,
        "order": bq_order,
        "event": bq_event,
        "report_new": bq_report_new,
        "daily": df_daily,
        "monthly": df_monthly,
        "user": bq_user,
        "mcs": bq_mcs,
        "shiruru": bq_srr,
        "goal": bq_goal,
        "goal_monthly": bq_goal_monthly,
    }
    extra = {
        "gc": gc,
        "df_report_new": df_report_new,
        "form_structure_new": form_structure_new,
    }
    return bq_tables, extra, errors
