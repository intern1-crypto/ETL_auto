"""SHIRURU データ（スプレッドシート）の抽出・加工。

戻り値:
    bq_srr : BigQuery 出力用データフレーム
"""

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

COLUMN_MAPPING = {
    "会員ID": "guest_num",
    "企業名": "company",
    "店舗": "store_id",
    "大学": "university",
    "学部": "faculty",
    "学年": "grade",
    "性別": "gender",
    "日時": "date",
    "文理区分": "bunri",
    "修正_日時": "date_fix",
    "店舗番号": "store_num",
    "店舗名": "store",
    "配布判定": "handing",
    "配布単価": "cost",
}


def build(gc):
    """SHIRURU データを構築して bq_srr を返す。"""
    ss_srr = gc.open_by_url(config.SHIRURU_SPREADSHEET_URL)
    print(f"{ss_srr.title}を開きました")

    # 数式の結果を取得してデータフレーム化
    df_srr = get_as_dataframe(ss_srr.get_worksheet(0), evaluate_formulas=True)

    # 店舗名をもとに店舗番号をマッピング
    df_srr["店舗番号"] = df_srr["店舗名"].map(store_dict)
    if df_srr["店舗名"].count() == df_srr["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(df_srr[df_srr["店舗番号"].isnull()]["店舗名"].unique())

    # 不要カラムを削除
    df_srr.drop(
        columns=["Unnamed: 21", "SCREEN条件", "KOKUSAI条件", "アクション形態", "卒業年月"],
        inplace=True,
    )

    # 日時型に
    df_srr["日時"] = pd.to_datetime(df_srr["日時"], errors="coerce")
    df_srr["修正_日時"] = pd.to_datetime(df_srr["修正_日時"]).dt.date

    # NaN を 0 に変えて int に変換
    df_srr["会員ID"] = df_srr["会員ID"].fillna(0).astype(int)
    df_srr["配布判定"] = df_srr["配布判定"].fillna(0).astype(int)
    df_srr["店舗番号"] = df_srr["店舗番号"].fillna(0).astype(int)

    df_srr.rename(columns=COLUMN_MAPPING, inplace=True)

    return df_srr
