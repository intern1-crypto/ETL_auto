"""個人データの集計（来店 + Meetup を結合IDで統合）。

戻り値:
    bq_user : 個人ごとの来店 / Meetup 集計（インド店舗を除外）
"""

import pandas as pd

from .store_mapping import inverse_store_dict


def _aggregate_order(df_order):
    """来店データから個人（結合ID）ごとの来店集計を作成する。"""
    df_order = df_order.copy()

    user_columns_order = [
        "conected_id", "ordered_at", "store_code", "group", "grade",
        "university", "faculty", "DU_id",
    ]

    df_order["ordered_at"] = pd.to_datetime(df_order["ordered_at"])

    # DU（DU_id）のみを残す
    df_du = df_order.drop_duplicates(subset="DU_id")

    df_user_order = (
        df_du[user_columns_order]
        .groupby("conected_id")
        .agg(
            visit=("DU_id", "nunique"),
            first_ordered_at=("ordered_at", "min"),
            last_ordered_at=("ordered_at", "max"),
            store_code=("store_code", "first"),
            grade=("grade", "last"),
            university=("university", "last"),
            faculty=("faculty", "last"),
        )
        .reset_index()
    )

    # 今年度4月以降の来店数
    this_year_april = pd.Timestamp(year=pd.Timestamp.today().year, month=4, day=1)
    df_visit_since_april = (
        df_order[df_order["ordered_at"] >= this_year_april]
        .groupby("conected_id")
        .agg(visit_since_april=("DU_id", "nunique"))
        .reset_index()
    )
    df_user_order = df_user_order.merge(
        df_visit_since_april, on="conected_id", how="left"
    )
    df_user_order["visit_since_april"] = (
        df_user_order["visit_since_april"].fillna(0).astype(int)
    )

    return df_user_order


def _aggregate_meetup(df_meetup):
    """Meetup データから個人（結合ID）ごとの参加集計を作成する。"""
    df_meetup = df_meetup.copy()
    df_meetup["キャンセル"] = df_meetup["キャンセル有無"].notnull()
    df_meetup["イベント開始日時"] = pd.to_datetime(df_meetup["イベント開始日時"])

    user_columns_meetup = [
        "結合ID", "イベント開始日時", "会員ID", "大学", "学部", "学年",
        "参加", "キャンセル", "店舗番号",
    ]

    df_user_meetup = (
        df_meetup[user_columns_meetup]
        .groupby("結合ID")
        .agg(
            attendance=("参加", "sum"),
            cancel=("キャンセル", "sum"),
            first_event_datetime=("イベント開始日時", "min"),
            last_event_datetime=("イベント開始日時", "max"),
            store_code=(
                "店舗番号",
                lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0],
            ),
            university=("大学", "last"),
            faculty=("学部", "last"),
            grade=("学年", "last"),
        )
        .reset_index()
    )
    df_user_meetup.rename(columns={"結合ID": "conected_id"}, inplace=True)

    # 今年度4月以降の参加数
    this_year_april = pd.Timestamp(year=pd.Timestamp.today().year, month=4, day=1)
    df_meetup_since_april = (
        df_meetup[df_meetup["イベント開始日時"] >= this_year_april]
        .groupby("結合ID")
        .agg(attendance_since_april=("参加", "sum"))
        .reset_index()
    )
    df_meetup_since_april.rename(columns={"結合ID": "conected_id"}, inplace=True)

    df_user_meetup = df_user_meetup.merge(
        df_meetup_since_april, on="conected_id", how="left"
    )
    df_user_meetup["attendance_since_april"] = (
        df_user_meetup["attendance_since_april"].fillna(0).astype(int)
    )

    return df_user_meetup


def build(df_order, df_meetup):
    """来店データ(df_order)と Meetup データ(df_meetup)から bq_user を構築する。"""
    df_user_order = _aggregate_order(df_order)
    df_user_meetup = _aggregate_meetup(df_meetup)

    # 結合IDをキーとして結合
    df_user = pd.merge(df_user_order, df_user_meetup, on="conected_id", how="outer")

    # Meetup データの欠損値を来店データから埋める
    df_user["university"] = df_user["university_y"].fillna(df_user["university_x"])
    df_user["faculty"] = df_user["faculty_y"].fillna(df_user["faculty_x"])
    df_user["grade"] = df_user["grade_y"].fillna(df_user["grade_x"])
    df_user["store_code"] = df_user["store_code_y"].fillna(df_user["store_code_x"])
    df_user.drop(
        columns=[
            "university_x", "faculty_x", "grade_x", "store_code_x",
            "university_y", "faculty_y", "grade_y", "store_code_y",
        ],
        inplace=True,
    )

    # 数値の欠損を0にして整数型に
    int_col = ["visit", "attendance", "store_code", "cancel"]
    df_user[int_col] = df_user[int_col].fillna(0).astype(int)

    df_user["store"] = df_user["store_code"].map(inverse_store_dict)

    # インド店舗（store_code >= 500）を除外
    bq_user = df_user[df_user["store_code"] < 500]

    return bq_user
