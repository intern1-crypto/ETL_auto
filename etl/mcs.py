"""MCS データ（スプレッドシート）の抽出・加工。

戻り値:
    bq_mcs : BigQuery 出力用データフレーム
"""

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

COLUMN_MAPPING = {
    "日付": "date",
    "店舗": "store_id",
    "視聴完了数": "comp_viewing",
    "視聴完了数_修正": "comp_viewing_fix",
    "視聴数": "viewing",
    "店舗名": "store",
    "店舗番号": "store_num",
}


def build(gc):
    """MCS データを構築して bq_mcs を返す。"""
    ss_mcs = gc.open_by_url(config.MCS_SPREADSHEET_URL)
    print(f"{ss_mcs.title}を開きました")

    # 数式の結果を取得してデータフレーム化
    df_ss_mcs = get_as_dataframe(ss_mcs.get_worksheet(0), evaluate_formulas=True)

    dfm = df_ss_mcs.copy()

    # 店舗名をもとに店舗番号をマッピング
    dfm["店舗番号"] = dfm["店舗名"].map(store_dict)
    if dfm["店舗名"].count() == dfm["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(dfm[dfm["店舗番号"].isnull()]["店舗名"].unique())

    # 不要カラムを削除
    dfm.drop(columns=["a", "b", "c", "卒業年度"], inplace=True)

    # 日付型に
    dfm["日付"] = pd.to_datetime(dfm["日付"]).dt.date

    # NaN を 0 に変えて int に変換
    dfm["視聴数"] = dfm["視聴数"].fillna(0).astype(int)
    dfm["視聴完了数"] = dfm["視聴完了数"].fillna(0).astype(int)
    dfm["店舗番号"] = dfm["店舗番号"].fillna(0).astype(int)

    dfm.rename(columns=COLUMN_MAPPING, inplace=True)

    return dfm
