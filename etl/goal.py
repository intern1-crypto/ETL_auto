"""目標値データ（スプレッドシート）の抽出・加工。

戻り値:
    build(...) -> (bq_goal, bq_goal_monthly)
"""

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

GOAL_COLUMN_MAPPING = {
    "店舗名": "store",
    "店舗番号": "store_code",
    "目標月": "target_month",
    "結合キー": "connection_key",
    "結合ナンバー": "connection_number",
    "目標日": "target_day",
    "曜日": "day",
    "総来店目標": "total_goal",
    "DU来店目標": "DU_goal",
    "Meetup参加目標": "Meetup_goal",
    "SHIRURU目標": "SHIRURU_goal",
    "MCS目標": "MCS_goal",
}

MONTHLY_COLUMN_MAPPING = {
    "目標月": "target_month",
    "店舗番号": "store_code",
    "総来店目標_monthly": "kpi_order",
    "DU来店目標_monthly": "kpi_du",
    "Meetup目標_monthly": "kpi_meetup",
    "SHIRURU目標_monthly": "kpi_shiruru",
    "MCS目標_monthly": "kpi_mcs",
}


def _build_daily_goal(ss_goal):
    """日別目標値（worksheet 1・2）を構築する。"""
    df_ss_goal = get_as_dataframe(ss_goal.get_worksheet(1), evaluate_formulas=True)
    df_ss_goal2 = get_as_dataframe(ss_goal.get_worksheet(2), evaluate_formulas=True)

    # 外部結合・重複削除
    df_daily_goal = pd.concat([df_ss_goal, df_ss_goal2], join="outer", ignore_index=True)
    len_before = len(df_daily_goal)
    df_daily_goal.drop_duplicates(inplace=True)
    print(f"{len_before - len(df_daily_goal)}行の重複データが削除されました")

    # 店舗名をもとに店舗番号をマッピング
    df_daily_goal["店舗番号"] = df_daily_goal["店舗名"].map(store_dict)
    if df_daily_goal["店舗名"].count() == df_daily_goal["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(df_daily_goal[df_daily_goal["店舗番号"].isnull()]["店舗名"].unique())

    # 不要カラムを削除
    df_daily_goal.drop(columns=["祝日", "休日"], inplace=True)

    # 日付・年月型に
    df_daily_goal["目標日"] = pd.to_datetime(df_daily_goal["目標日"]).dt.date
    df_daily_goal["目標月"] = pd.to_datetime(df_daily_goal["目標月"], format="%Y/%m")

    # 整数型・小数型に
    df_daily_goal[["店舗番号", "総来店目標"]] = (
        df_daily_goal[["店舗番号", "総来店目標"]].fillna(0).astype(int)
    )
    df_daily_goal[["DU来店目標", "Meetup参加目標", "SHIRURU目標", "MCS目標"]] = df_daily_goal[
        ["DU来店目標", "Meetup参加目標", "SHIRURU目標", "MCS目標"]
    ].astype(float)

    df_daily_goal.rename(columns=GOAL_COLUMN_MAPPING, inplace=True)

    return df_daily_goal


def _build_monthly_goal(ss_goal):
    """月毎目標値（worksheet 0）を構築する。"""
    df_goal = get_as_dataframe(ss_goal.get_worksheet(0), evaluate_formulas=True)

    df_goal = df_goal[
        [
            "目標月", "店舗番号", "store", "総来店目標_monthly", "DU来店目標_monthly",
            "Meetup目標_monthly", "SHIRURU目標_monthly", "MCS目標_monthly",
        ]
    ]

    df_goal["目標月"] = pd.to_datetime(df_goal["目標月"], format="mixed", errors="coerce")
    df_goal["店舗番号"] = df_goal["店舗番号"].fillna(0).astype(int)

    df_goal.rename(columns=MONTHLY_COLUMN_MAPPING, inplace=True)
    df_goal.dropna(subset=["target_month"], inplace=True)

    return df_goal


def build(gc):
    """目標値データを構築して (bq_goal, bq_goal_monthly) を返す。"""
    ss_goal = gc.open_by_url(config.GOAL_SPREADSHEET_URL)
    print(f"{ss_goal.title}を開きました")

    bq_goal = _build_daily_goal(ss_goal)
    bq_goal_monthly = _build_monthly_goal(ss_goal)

    return bq_goal, bq_goal_monthly
