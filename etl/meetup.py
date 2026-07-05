"""参加データ（Meetup 参加者）の抽出・加工。

戻り値:
    df_meetup : 個人データ集計（user モジュール）でも使う加工済み全カラム版（日本語カラム名）
    bq_meetup : BigQuery 出力用（英語カラム名）
"""

import numpy as np
import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

COLUMN_MAPPING = {
    "予約ID": "reservation_id",
    "イベント開始日時": "start_at",
    "イベント終了日時": "end_at",
    "MeetupID": "event_id",
    "結合ID": "conected_id",
    "会員ID": "member_id",
    "店舗番号": "store_code",
    "店舗名": "store",
    "企業名": "company",
    "開催形式": "meetup_type",
    "参加": "attendance",
    "参加予定": "planned_attendance",
    "予約したきっかけ": "reservation_reason",
    "学年": "grade",
    "入学年月": "enrollment_year_month",
    "予約日": "reservation_day",
    "卒業年月": "graduation_year_month",
    "大学": "university",
    "文理": "bunri",
    "学部": "faculty",
    "専攻": "major",
    "性別": "gender",
    "出身地": "hometown",
    "満足度": "satisfaction",
    "参加経由": "reservation_way",
    "注力可否": "Pickup1",
    "部活ID": "bukatsu_id",
}


def _extract(gc, drive_service):
    """Google Drive とスプレッドシートから参加データを抽出・結合する。"""
    from .utils import read_csv_folder_from_drive

    df_meetup_raw = read_csv_folder_from_drive(
        drive_service, config.MEETUP_CSV_FOLDER_ID, encodings=("cp932",)
    )
    df_meetup_raw["イベント日"] = pd.to_datetime(df_meetup_raw["イベント日"])

    # スプレッドシートを開く
    ss_meetup = gc.open_by_url(config.MEETUP_SPREADSHEET_URL)
    print(f"{ss_meetup.title}を開きました")

    df_ss_meetup = get_as_dataframe(ss_meetup.get_worksheet(0))
    df_ss_meetup_del = get_as_dataframe(ss_meetup.worksheet("カウント対象外Meetup"))

    # カウント対象外の予約IDを削除
    len_before = len(df_ss_meetup)
    df_ss_meetup = df_ss_meetup[
        ~df_ss_meetup["予約ID"].isin(df_ss_meetup_del["MeetupID"])
    ]
    print(f"{len_before - len(df_ss_meetup)}行の重複データが削除されました")

    # 日時を変換（yyyy-MM-dd HH:mm:ss 形式）
    df_ss_meetup["イベント日"] = pd.to_datetime(
        df_ss_meetup["イベント日"], format="mixed"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    # CSV データとスプレッドシートデータを外部結合し、重複削除
    df_meetup_raw = pd.concat([df_meetup_raw, df_ss_meetup], join="outer", ignore_index=True)
    len_before = len(df_meetup_raw)
    df_meetup_raw.drop_duplicates(inplace=True)
    print(f"{len_before - len(df_meetup_raw)}行の重複データが削除されました")

    return df_meetup_raw


def _process(df_meetup_raw):
    """参加データを加工して df_meetup（全カラム）を作成する。"""
    df_meetup = df_meetup_raw.copy()

    # イベント時間から開始時刻を抽出し、開始・終了日時カラムを作成
    df_meetup["開始時刻"] = df_meetup["イベント時間"].str.extract(r"(\d{2}:\d{2}:\d{2})")
    df_meetup["イベント開始日時"] = pd.to_datetime(
        df_meetup["イベント日"].astype(str) + " " + df_meetup["開始時刻"]
    )
    df_meetup["イベント終了日時"] = df_meetup["イベント開始日時"] + pd.Timedelta(hours=1)
    df_meetup.drop(columns=["開始時刻", "イベント時間"], inplace=True)
    df_meetup["イベント日"] = pd.to_datetime(df_meetup["イベント日"]).dt.date

    # 店舗名をもとに店舗番号をマッピング
    df_meetup["店舗番号"] = df_meetup["店舗名"].map(store_dict)
    if df_meetup["店舗名"].count() == df_meetup["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(df_meetup[df_meetup["店舗番号"].isnull()]["店舗名"].unique())

    df_meetup = df_meetup.rename(columns={"予約ID": "MeetupID"})
    df_meetup["MeetupID"] = df_meetup["MeetupID"].astype(int)
    df_meetup["会員ID"] = df_meetup["会員ID"].astype(int)

    # 参加：参加なら1, else 0
    df_meetup["参加可否"] = (df_meetup["参加可否"] == "参加").astype(int)
    df_meetup = df_meetup.rename(columns={"参加可否": "参加"})

    # 参加予定：参加してないかつキャンセル有無が欠損 → 1, else → 0
    df_meetup["参加予定"] = (
        (df_meetup["参加"] == 0) & (df_meetup["キャンセル有無"].isnull())
    ).astype(int)

    # 開催形式を簡潔に言い換え
    df_meetup["開催形式"] = df_meetup["開催形式"].replace(
        {"オンラインMeetup": "オンライン", "Meetup (店舗開催)": "対面"}
    )

    df_meetup["予約ID"] = (
        df_meetup["イベント開始日時"].astype(str)
        + "_"
        + df_meetup["MeetupID"].astype(str)
        + "_"
        + df_meetup["結合ID"].astype(str)
    )

    df_meetup["cancell"] = (df_meetup["キャンセル有無"] == "キャンセル").astype(int)
    df_meetup["no_show"] = (df_meetup["キャンセル有無"] == "無断欠席").astype(int)

    return df_meetup


def _to_bq(df_meetup):
    """df_meetup から BigQuery 出力用データフレーム（bq_meetup）を作成する。"""
    bq_meetup = df_meetup[
        [
            "予約ID", "イベント開始日時", "イベント終了日時", "MeetupID", "結合ID",
            "会員ID", "店舗番号", "店舗名", "企業名", "開催形式", "参加", "参加予定",
            "cancell", "no_show", "予約したきっかけ", "学年", "入学年月", "予約日",
            "卒業年月", "大学", "文理", "学部", "専攻", "性別", "出身地", "満足度",
            "参加経由", "注力可否", "部活ID",
        ]
    ].copy()

    bq_meetup.rename(columns=COLUMN_MAPPING, inplace=True)

    # Pickup count
    cond_1 = (
        (bq_meetup["attendance"] == 1) | (bq_meetup["planned_attendance"] == 1)
    ) & (bq_meetup["Pickup1"] == "注力している")
    cond_2 = ((bq_meetup["attendance"] == 1) | (bq_meetup["planned_attendance"] == 1)) & (
        (bq_meetup["Pickup1"].isna()) | (bq_meetup["Pickup1"] == "注力していない")
    )
    cond_3 = (bq_meetup["attendance"] == 0) & (bq_meetup["planned_attendance"] == 0)

    bq_meetup["Pickup"] = np.select([cond_1, cond_2, cond_3], [2, 1, 0], default=np.nan)
    bq_meetup["Pickup"] = bq_meetup["Pickup"].fillna(0).astype(int)

    bq_meetup = bq_meetup.drop(columns=["Pickup1"])

    return bq_meetup


def build(gc, drive_service):
    """参加データを構築して (df_meetup, bq_meetup) を返す。"""
    df_meetup_raw = _extract(gc, drive_service)
    df_meetup = _process(df_meetup_raw)
    bq_meetup = _to_bq(df_meetup)
    return df_meetup, bq_meetup
