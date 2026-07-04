"""日次データの集計（来店 + Meetup）。

戻り値:
    df_daily : 日付・店舗ごとの来店 / Meetup 集計（BigQuery 出力用）
"""

import pandas as pd

from .store_mapping import inverse_store_dict


def _aggregate_visits(df_order):
    """来店データを日付・店舗ごとに集計する。"""
    df_daily_visits = df_order.copy()
    df_daily_visits["date"] = df_daily_visits["ordered_at"].dt.date

    # date と store_code ごとに総来店(visit_total)と DU(visit_du) を集計
    df_daily_visits = df_daily_visits.groupby(["date", "store_code"])["conected_id"].agg(
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
