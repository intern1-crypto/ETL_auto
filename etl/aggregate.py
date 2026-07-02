"""日次データの集計（来店 + Meetup）。

戻り値:
    df_daily : 日付・店舗ごとの来店 / Meetup 集計（BigQuery 出力用）
"""

import pandas as pd

from .store_mapping import inverse_store_dict


def _aggregate_visits(df4):
    """来店データを日付・店舗ごとに集計する。"""
    df_visiter = df4.copy()
    df_visiter["date"] = df_visiter["ordered_at"].dt.date

    # date と store_code ごとに総来店(visit_total)と DU(visit_du) を集計
    df_visiter = df_visiter.groupby(["date", "store_code"])["conected_id"].agg(
        visit_total="count",  # 行数（全体のカウント）
        visit_du="nunique",  # ユニークな値の個数
    )
    return df_visiter.reset_index()


def _aggregate_meetup(df5):
    """Meetup データを日付・店舗ごとに集計する。"""
    df8 = df5.copy()
    df8["date"] = df8["start_at"].dt.date

    # キャンセル有無を1,0に
    df8["cancell"] = df8["cancell"].notnull().astype(int)

    # date, store_code 毎に参加・参加予定・キャンセルのそれぞれの合計
    df8 = df8.groupby(["date", "store_code"])[
        ["attendance", "planned_attendance", "cancell"]
    ].sum()
    return df8.reset_index()


def build(df4, df5):
    """来店データ(df4)と Meetup データ(df5)から df_daily を構築する。"""
    df_visiter = _aggregate_visits(df4)
    df8 = _aggregate_meetup(df5)

    # 外部結合し、欠損値を0で埋める
    df_daily = pd.merge(df_visiter, df8, on=["date", "store_code"], how="outer")
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
