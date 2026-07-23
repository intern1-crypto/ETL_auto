"""SHIRURU データ（スプレッドシート）の抽出・加工。

戻り値:
    bq_srr : BigQuery 出力用データフレーム
"""

import logging

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "会員ID": "guest_num",
    "企業名": "company",
    "店舗番号": "store_code",
    "店舗名": "store",
    "大学": "university",
    "学部": "faculty",
    "学年": "grade",
    "性別": "gender",
    "日時": "date",
    "文理区分": "bunri",
}


def build(gc):
    """SHIRURU データを構築して bq_srr を返す。"""
    ss_srr = gc.open_by_url(config.SHIRURU_SPREADSHEET_URL)

    # 数式の結果を取得してデータフレーム化
    df_srr = get_as_dataframe(ss_srr.get_worksheet(0), evaluate_formulas=True)

    # アクション形態が「パンフレットがほしい」の行のみを残す
    df_srr = df_srr[df_srr["アクション形態"] == "パンフレットがほしい"].copy()

    # 店舗名をもとに店舗番号をマッピング
    df_srr["店舗番号"] = df_srr["店舗名"].map(store_dict)
    if df_srr["店舗名"].count() != df_srr["店舗番号"].count():
        unmapped = df_srr[df_srr["店舗番号"].isnull()]["店舗名"].unique()
        logger.warning("shiruru: 店舗マッピングに漏れあり: %s", unmapped)

    # 必要なカラムのみ残す
    df_srr = df_srr[list(COLUMN_MAPPING.keys())]

    # 日時型に
    df_srr["日時"] = pd.to_datetime(df_srr["日時"], errors="coerce")

    # NaN を 0 に変えて int に変換
    df_srr["会員ID"] = df_srr["会員ID"].fillna(0).astype(int)
    df_srr["店舗番号"] = df_srr["店舗番号"].fillna(0).astype(int)

    df_srr.rename(columns=COLUMN_MAPPING, inplace=True)

    return df_srr
