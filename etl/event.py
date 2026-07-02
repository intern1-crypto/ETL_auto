"""イベントデータ（Meetup 開催企業）の抽出・加工。

戻り値:
    bq_event : BigQuery 出力用データフレーム
"""

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .utils import read_csv_folder

COLUMN_MAPPING = {
    "イベントID": "event_id",
    "お客様企業名": "company",
    "店舗名": "store",
    "開催状態": "status",
    "予約形態": "event_type",
    "企業様人数": "company_attendance",
    "学生参加枠": "student_attendance_max",
    "対象卒年(Meetup)": "target",
    "タイプ(Meetup)": "meetup_type",
    "学生予約人数": "student_reserved",
    "学生参加人数": "student_attendance",
    "作成日": "created_at",
    "キャンセル日": "canceled_at",
    "注力可否": "pickup",
    "開始日時": "start_at",
    "終了日時": "end_at",
}


def _extract(gc):
    """CSV とスプレッドシートからイベントデータを抽出・結合する。"""
    folder = config.DATA_DIR / config.EVENT_CSV_SUBDIR
    df6 = read_csv_folder(folder, encodings=("cp932",))

    df6["予約日"] = pd.to_datetime(df6["予約日"], format="mixed").dt.date
    df6["作成日"] = pd.to_datetime(df6["作成日"], format="mixed")
    df6["キャンセル日"] = pd.to_datetime(df6["キャンセル日"], format="mixed")

    # スプレッドシートを開く
    ss_event = gc.open_by_url(config.EVENT_SPREADSHEET_URL)
    print(f"{ss_event.title}を開きました")

    df_ss_event = get_as_dataframe(ss_event.get_worksheet(0))

    df_ss_event["予約日"] = pd.to_datetime(df_ss_event["予約日"], format="mixed").dt.date
    df_ss_event["作成日"] = pd.to_datetime(df_ss_event["作成日"], format="mixed")
    df_ss_event["キャンセル日"] = pd.to_datetime(df_ss_event["キャンセル日"], format="mixed")

    # 予約IDが欠損しているレコードを削除
    len_before = len(df_ss_event)
    df_ss_event = df_ss_event.dropna(subset=["予約ID"])
    print(f"{len_before - len(df_ss_event)}行のデータが削除されました")

    # CSV データとスプレッドシートデータの結合・重複削除
    df6 = pd.concat([df6, df_ss_event], join="outer", ignore_index=True)
    df6 = df6.drop_duplicates()

    return df6


def _process(df6):
    """イベントデータを加工する。"""
    df7 = df6.copy()

    # 開始日時と終了日時を作成
    df7["開始日時"] = pd.to_datetime(df7["予約日"].astype(str) + " " + df7["開始時間"])
    df7["終了日時"] = pd.to_datetime(df7["予約日"].astype(str) + " " + df7["終了時間"])
    df7.drop(columns=["開始時間", "終了時間", "予約日"], inplace=True)

    # 整数型に
    df7 = df7.astype(
        {"予約ID": int, "企業様人数": int, "学生参加枠": int, "学生参加人数": int}
    )

    # カラムを絞る
    df7 = df7[
        [
            "予約ID", "お客様企業名", "店舗名", "開催状態", "予約形態", "企業様人数",
            "学生参加枠", "対象卒年(Meetup)", "タイプ(Meetup)", "学生予約人数",
            "学生参加人数", "作成日", "キャンセル日", "注力可否", "開始日時", "終了日時",
        ]
    ]

    df7 = df7.replace(
        {
            "タイプ(Meetup)": {
                "オンラインMeetup (自宅から参加)": "オンライン",
                "Meetup (店舗開催)": "対面",
            }
        }
    )

    df7.rename(columns={"予約ID": "イベントID"}, inplace=True)
    df7 = df7.rename(columns=COLUMN_MAPPING)

    return df7


def build(gc):
    """イベントデータを構築して bq_event を返す。"""
    df6 = _extract(gc)
    bq_event = _process(df6)
    return bq_event
