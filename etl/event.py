"""イベントデータ（Meetup 開催企業）の抽出・加工。

戻り値:
    bq_event : BigQuery 出力用データフレーム
"""

import logging

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .utils import read_csv_folder_from_drive

logger = logging.getLogger(__name__)

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


def _extract(gc, drive_service):
    """Google Drive とスプレッドシートからイベントデータを抽出・結合する。"""
    df_event_raw = read_csv_folder_from_drive(
        drive_service, config.EVENT_CSV_FOLDER_ID, encodings=("cp932",)
    )

    df_event_raw["予約日"] = pd.to_datetime(df_event_raw["予約日"], format="mixed").dt.date
    df_event_raw["作成日"] = pd.to_datetime(df_event_raw["作成日"], format="mixed")
    df_event_raw["キャンセル日"] = pd.to_datetime(df_event_raw["キャンセル日"], format="mixed")

    # スプレッドシートを開く
    ss_event = gc.open_by_url(config.EVENT_SPREADSHEET_URL)
    df_ss_event = get_as_dataframe(ss_event.get_worksheet(0))

    df_ss_event["予約日"] = pd.to_datetime(df_ss_event["予約日"], format="mixed").dt.date
    df_ss_event["作成日"] = pd.to_datetime(df_ss_event["作成日"], format="mixed")
    df_ss_event["キャンセル日"] = pd.to_datetime(df_ss_event["キャンセル日"], format="mixed")

    # 予約IDが欠損しているレコードを削除
    df_ss_event = df_ss_event.dropna(subset=["予約ID"])

    # CSV データとスプレッドシートデータの結合・重複削除
    df_event_raw = pd.concat([df_event_raw, df_ss_event], join="outer", ignore_index=True)
    df_event_raw = df_event_raw.drop_duplicates()

    return df_event_raw


def _process(df_event_raw):
    """イベントデータを加工して bq_event を作成する。"""
    bq_event = df_event_raw.copy()

    # 開始時間が欠損している行は開始日時を特定できないため除外
    bq_event = bq_event[bq_event["開始時間"].notna()]

    # 開始日時を作成
    bq_event["開始日時"] = pd.to_datetime(
        bq_event["予約日"].astype(str) + " " + bq_event["開始時間"]
    )

    # 終了日時を作成（終了時間が欠損している場合は開始日時の1時間後とする）
    end_at_str = bq_event["予約日"].astype(str) + " " + bq_event["終了時間"].fillna("")
    bq_event["終了日時"] = pd.to_datetime(end_at_str, errors="coerce")
    bq_event["終了日時"] = bq_event["終了日時"].fillna(
        bq_event["開始日時"] + pd.Timedelta(hours=1)
    )

    bq_event.drop(columns=["開始時間", "終了時間", "予約日"], inplace=True)

    # 整数型に
    bq_event = bq_event.astype(
        {"予約ID": int, "企業様人数": int, "学生参加枠": int, "学生参加人数": int}
    )

    # カラムを絞る
    bq_event = bq_event[
        [
            "予約ID", "お客様企業名", "店舗名", "開催状態", "予約形態", "企業様人数",
            "学生参加枠", "対象卒年(Meetup)", "タイプ(Meetup)", "学生予約人数",
            "学生参加人数", "作成日", "キャンセル日", "注力可否", "開始日時", "終了日時",
        ]
    ]

    bq_event = bq_event.replace(
        {
            "タイプ(Meetup)": {
                "オンラインMeetup (自宅から参加)": "オンライン",
                "Meetup (店舗開催)": "対面",
            }
        }
    )

    bq_event.rename(columns={"予約ID": "イベントID"}, inplace=True)
    bq_event = bq_event.rename(columns=COLUMN_MAPPING)

    return bq_event


def build(gc, drive_service):
    """イベントデータを構築して bq_event を返す。"""
    df_event_raw = _extract(gc, drive_service)
    bq_event = _process(df_event_raw)
    return bq_event
