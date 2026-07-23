"""日次・月次データの集計（来店 + Meetup + 目標値）。

戻り値:
    df_daily   : 日付・店舗ごとの来店 / Meetup 集計（BigQuery 出力用）
    df_monthly : 月・店舗ごとの来店 / Meetup / 目標値 集計（BigQuery 出力用）
"""

import pandas as pd

from .store_mapping import inverse_store_dict


def _aggregate_visits(df_order):
    """来店データを日付・店舗ごとに集計する。"""
    df_daily_visits = df_order.copy()
    df_daily_visits["date"] = df_daily_visits["ordered_at"].dt.date

    # date と store_code ごとに総来店(visit_total)と DU(visit_du) を集計
    df_daily_visits = df_daily_visits.groupby(["date", "store_code"])["connected_id"].agg(
        visit_total="count",  # 行数（全体のカウント）
        visit_du="nunique",  # ユニークな値の個数
    )
    return df_daily_visits.reset_index()


def _aggregate_meetup(df_meetup_bq):
    """Meetup データを日付・店舗ごとに集計する。"""
    df_daily_meetup = df_meetup_bq.copy()
    df_daily_meetup["date"] = df_daily_meetup["start_at"].dt.date

    # キャンセル有無を1,0に
    df_daily_meetup["cancell"] = df_daily_meetup["cancell"].notnull().astype(int)

    # date, store_code 毎に参加・参加予定・キャンセルのそれぞれの合計
    df_daily_meetup = df_daily_meetup.groupby(["date", "store_code"])[
        ["attendance", "planned_attendance", "cancell"]
    ].sum()
    return df_daily_meetup.reset_index()


def _aggregate_visits_monthly(df_order):
    """来店データを月・店舗ごとに集計する（DU: DU_id のユニークカウント）。"""
    df_monthly_visits = df_order.copy()
    df_monthly_visits["month"] = (
        df_monthly_visits["ordered_at"].dt.to_period("M").dt.to_timestamp()
    )

    df_monthly_visits = df_monthly_visits.groupby(["month", "store_code"])[
        "DU_id"
    ].nunique()
    return df_monthly_visits.reset_index(name="DU")


def _aggregate_meetup_monthly(df_meetup_bq):
    """Meetup データを月・店舗ごとに集計する。

    attendance_point / planned_attendance_point は pickup_flag（0, 1, 2）に応じて
    attendance / planned_attendance を (pickup_flag + 1) 倍した値の合計。
    """
    df_monthly_meetup = df_meetup_bq.copy()
    df_monthly_meetup["month"] = (
        df_monthly_meetup["start_at"].dt.to_period("M").dt.to_timestamp()
    )

    df_monthly_meetup["attendance_point"] = df_monthly_meetup["attendance"] * (
        df_monthly_meetup["pickup_flag"] + 1
    )
    df_monthly_meetup["planned_attendance_point"] = df_monthly_meetup[
        "planned_attendance"
    ] * (df_monthly_meetup["pickup_flag"] + 1)

    df_monthly_meetup = df_monthly_meetup.groupby(["month", "store_code"]).agg(
        attendance_count=("attendance", "sum"),
        planned_attendance_count=("planned_attendance", "sum"),
        attendance_point=("attendance_point", "sum"),
        planned_attendance_point=("planned_attendance_point", "sum"),
    )
    return df_monthly_meetup.reset_index()


def _aggregate_mcs_monthly(bq_mcs):
    """MCS データを月・店舗ごとに集計する（viewing: 視聴完了数の合計）。"""
    df_monthly_mcs = bq_mcs.copy()
    df_monthly_mcs["month"] = (
        pd.to_datetime(df_monthly_mcs["date"]).dt.to_period("M").dt.to_timestamp()
    )

    df_monthly_mcs = df_monthly_mcs.groupby(["month", "store_code"])["viewing"].sum()
    return df_monthly_mcs.reset_index()


def _aggregate_shiruru_monthly(bq_srr):
    """SHIRURU データを月・店舗ごとに集計する（shiruru_distribution: 配布件数）。"""
    df_monthly_srr = bq_srr.copy()
    df_monthly_srr["month"] = (
        df_monthly_srr["date"].dt.to_period("M").dt.to_timestamp()
    )

    df_monthly_srr = df_monthly_srr.groupby(["month", "store_code"]).size()
    return df_monthly_srr.reset_index(name="shiruru_distribution")


def build_monthly(
    df_order, df_meetup_bq, bq_goal_monthly=None, bq_mcs=None, bq_srr=None
):
    """来店データ(df_order)と Meetup データ(df_meetup_bq)、

    目標値データ(bq_goal_monthly、任意)・MCS データ(bq_mcs、任意)・
    SHIRURU データ(bq_srr、任意)から月・店舗ごとの df_monthly を構築する。
    """
    df_monthly_visits = _aggregate_visits_monthly(df_order)
    df_monthly_meetup = _aggregate_meetup_monthly(df_meetup_bq)

    df_monthly = pd.merge(
        df_monthly_visits, df_monthly_meetup, on=["month", "store_code"], how="outer"
    )

    goal_columns = ["kpi_du", "kpi_meetup", "kpi_shiruru", "kpi_mcs"]
    if bq_goal_monthly is not None:
        df_goal_monthly = bq_goal_monthly.rename(columns={"target_month": "month"})[
            ["month", "store_code"] + goal_columns
        ]
        df_monthly = pd.merge(
            df_monthly, df_goal_monthly, on=["month", "store_code"], how="outer"
        )

    if bq_mcs is not None:
        df_monthly_mcs = _aggregate_mcs_monthly(bq_mcs)
        df_monthly = pd.merge(
            df_monthly, df_monthly_mcs, on=["month", "store_code"], how="outer"
        )

    if bq_srr is not None:
        df_monthly_srr = _aggregate_shiruru_monthly(bq_srr)
        df_monthly = pd.merge(
            df_monthly, df_monthly_srr, on=["month", "store_code"], how="outer"
        )

    df_monthly.fillna(0, inplace=True)

    # 店舗番号から店舗名を付与し、カラム順を整える
    df_monthly["store"] = df_monthly["store_code"].map(inverse_store_dict)
    columns = [
        "month", "store_code", "store", "DU", "attendance_count",
        "planned_attendance_count", "attendance_point", "planned_attendance_point",
    ]
    if bq_goal_monthly is not None:
        columns += goal_columns
    if bq_mcs is not None:
        columns += ["viewing"]
    if bq_srr is not None:
        columns += ["shiruru_distribution"]
    df_monthly = df_monthly[columns]

    # 店舗番号が有効でないレコードを消す
    df_monthly = df_monthly[
        (df_monthly["store_code"] > 0) & (df_monthly["store_code"] < 500)
    ]

    # 整数型に
    int_columns = [
        "DU", "attendance_count", "planned_attendance_count",
        "attendance_point", "planned_attendance_point",
    ]
    if bq_mcs is not None:
        int_columns += ["viewing"]
    if bq_srr is not None:
        int_columns += ["shiruru_distribution"]
    df_monthly[int_columns] = df_monthly[int_columns].astype(int)

    return df_monthly


def build(df_order, df_meetup_bq):
    """来店データ(df_order)と Meetup データ(df_meetup_bq)から df_daily を構築する。"""
    df_daily_visits = _aggregate_visits(df_order)
    df_daily_meetup = _aggregate_meetup(df_meetup_bq)

    # 外部結合し、欠損値を0で埋める
    df_daily = pd.merge(
        df_daily_visits, df_daily_meetup, on=["date", "store_code"], how="outer"
    )
    df_daily.fillna(0, inplace=True)

    # 店舗番号から店舗名を付与し、カラム順を整える
    df_daily["store"] = df_daily["store_code"].map(inverse_store_dict)
    df_daily = df_daily[
        [
            "date", "store_code", "store", "visit_total", "visit_du",
            "attendance", "planned_attendance", "cancell",
        ]
    ]

    # 店舗番号が有効でないレコードを消す
    df_daily = df_daily[(df_daily["store_code"] > 0) & (df_daily["store_code"] < 500)]

    # 整数型に
    int_columns = [
        "visit_total", "visit_du", "attendance", "planned_attendance", "cancell",
    ]
    df_daily[int_columns] = df_daily[int_columns].astype(int)

    return df_daily
