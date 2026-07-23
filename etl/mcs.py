"""MCS データ（スプレッドシート）の抽出・加工。

戻り値:
    bq_mcs : BigQuery 出力用データフレーム
"""

import logging

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "日付": "date",
    "視聴完了数": "viewing",
    "店舗名": "store",
    "店舗番号": "store_code",
}


def build(gc):
    """MCS データを構築して bq_mcs を返す。"""
    ss_mcs = gc.open_by_url(config.MCS_SPREADSHEET_URL)

    # 数式の結果を取得してデータフレーム化
    df_mcs = get_as_dataframe(ss_mcs.get_worksheet(0), evaluate_formulas=True)

    # 不要カラムを削除
    df_mcs.drop(columns=["a", "b", "c", "卒業年度", "店舗", "月換算"], inplace=True)

    # 日付型に
    df_mcs["日付"] = pd.to_datetime(df_mcs["日付"]).dt.date

    # NaN を 0 に変えて int に変換
    df_mcs["視聴完了数"] = df_mcs["視聴完了数"].fillna(0).astype(int)
    df_mcs["店舗番号"] = df_mcs["店舗番号"].fillna(0).astype(int)

    df_mcs.rename(columns=COLUMN_MAPPING, inplace=True)

    return df_mcs
