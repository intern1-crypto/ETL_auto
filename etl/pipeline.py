"""全データソースの抽出・加工をまとめて行う。

main.py（BigQuery への書き込み）と、確認用スクリプト（ローカル保存）の
両方から共通で利用する。
"""

from . import aggregate, auth, event, goal, mcs, meetup, order, report, shiruru, user


def build_all():
    """全データソースを抽出・加工し、(bq_tables, extra) を返す。

    bq_tables : {テーブル名: DataFrame} の辞書（config.TABLE_NAMES のキーに対応）
    extra     : 店舗別日報シート書き出しで使う補助データ（gc, df_report_new, form_structure_new）
    """
    gc = auth.get_gspread_client()
    forms_service = auth.get_forms_service()
    drive_service = auth.get_drive_service()

    print("=== 参加データ ===")
    df_meetup, bq_meetup = meetup.build(gc, drive_service)

    print("=== 来店データ ===")
    df_order, bq_order = order.build(gc, drive_service)

    print("=== イベントデータ ===")
    bq_event = event.build(gc, drive_service)

    print("=== 日報データ ===")
    bq_report_new, df_report_new, form_structure_new = report.build_new(forms_service)

    print("=== 日次データ集計 ===")
    df_daily = aggregate.build(df_order, bq_meetup)

    print("=== 個人データ ===")
    bq_user = user.build(df_order, df_meetup)

    print("=== MCS ===")
    bq_mcs = mcs.build(gc)

    print("=== SHIRURU ===")
    bq_srr = shiruru.build(gc)

    print("=== 目標値 ===")
    bq_goal, bq_goal_monthly = goal.build(gc)

    bq_tables = {
        "meetup": bq_meetup,
        "order": bq_order,
        "event": bq_event,
        "report_new": bq_report_new,
        "daily": df_daily,
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
    return bq_tables, extra
