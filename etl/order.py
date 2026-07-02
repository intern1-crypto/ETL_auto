"""来店データ（オーダー）の抽出・加工。

戻り値:
    df4       : 集計・個人データでも使う加工済みデータ（英語カラム名）
    bq_order  : BigQuery 出力用（インド店舗を除外）
"""

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict
from .utils import read_csv_folder

NEW_COLUMNS = [
    "conected_id", "order_id", "store", "group", "university", "grade",
    "Graduation_year", "faculty", "type", "ordered_at", "drink", "store_code",
    "DU_id",
]


def _extract(gc):
    """CSV とスプレッドシートから来店データを抽出・結合する。"""
    folder = config.DATA_DIR / config.ORDER_CSV_SUBDIR
    # utf-8 を優先し、失敗したファイルは cp932 で読み込む
    df3 = read_csv_folder(folder, encodings=("utf-8", "cp932"))

    # スプレッドシートを開く
    ss_order = gc.open_by_url(config.ORDER_SPREADSHEET_URL)
    print(f"{ss_order.title}を開きました")

    df_ss_order = get_as_dataframe(ss_order.get_worksheet(0))

    # yyyy-MM-dd HH:mm:ss 形式に変換
    df_ss_order["登録日"] = pd.to_datetime(
        df_ss_order["登録日"], format="mixed"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    # CSV データとスプレッドシートデータの結合
    df3 = pd.concat([df3, df_ss_order], join="outer", ignore_index=True)

    # 重複データ削除
    len_before = len(df3)
    df3.drop_duplicates(subset=["結合ID", "オーダーID", "登録日"], inplace=True)
    print(f"{len_before - len(df3)}行の重複データが削除されました")

    return df3


def _process(df3):
    """来店データを加工して df4 を作成する。"""
    df4 = df3[
        [
            "結合ID", "オーダーID", "店舗名", "グループ", "大学/キャンパス", "学年",
            "卒年", "学部・学科", "タイプ", "登録日", "ドリンク",
        ]
    ].copy()

    # 重複データ削除
    len_before = len(df4)
    df4.drop_duplicates(inplace=True)
    print(f"{len_before - len(df4)}行の重複データが削除されました")

    # カラム名変更・型変換
    df4 = df4.rename(columns={"登録日": "オーダー日時"})
    df4["オーダー日時"] = pd.to_datetime(
        df4["オーダー日時"], format="mixed", dayfirst=False
    )

    # 店舗名をもとに店舗番号をマッピング
    df4["店舗番号"] = df4["店舗名"].map(store_dict)
    if df4["店舗名"].count() == df4["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(df4[df4["店舗番号"].isnull()]["店舗名"].unique())

    df4["オーダーID"] = pd.to_numeric(df4["オーダーID"]).astype(int)

    df4["DU_id"] = (
        df4["オーダー日時"].dt.date.astype(str)
        + "_"
        + df4["結合ID"]
        + "_"
        + df4["店舗番号"].astype(str)
    )

    # カラム名を英語に
    df4.columns = NEW_COLUMNS

    # 来店回数のカラム追加
    df4["visit_count"] = df4.groupby("conected_id").cumcount() + 1

    # カラムの順番を入れ替え
    df4 = df4[
        [
            "order_id", "ordered_at", "store_code", "store", "conected_id",
            "visit_count", "group", "grade", "Graduation_year", "university",
            "faculty", "type", "DU_id", "drink",
        ]
    ]

    # 大学名整形
    df4["university"] = df4["university"].str.replace(" /", "", regex=False)
    df4["university"] = df4["university"].str.replace("大学 ", "大学", regex=False)
    df4["university"] = df4["university"].str.replace("その他 ", "その他", regex=False)

    return df4


def build(gc):
    """来店データを構築して (df4, bq_order) を返す。"""
    df3 = _extract(gc)
    df4 = _process(df3)

    # BigQuery 出力用：インド店舗（store_code >= 500）を除外
    bq_order = df4[df4["store_code"] < 500]

    return df4, bq_order
