"""参加データ（Meetup 参加者）の抽出・加工。

戻り値:
    df_meetup : 個人データ集計（user モジュール）でも使う加工済み全カラム版（日本語カラム名）
    bq_meetup : BigQuery 出力用（英語カラム名）
"""

import logging

import pandas as pd
from gspread_dataframe import get_as_dataframe

from . import config
from .store_mapping import store_dict

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "予約ID": "reservation_id",
    "イベント開始日時": "start_at",
    "イベント終了日時": "end_at",
    "MeetupID": "event_id",
    "結合ID": "connected_id",
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
    "注力可否": "pickup_flag",
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

    df_ss_meetup = get_as_dataframe(ss_meetup.get_worksheet(0))
    df_ss_meetup_del = get_as_dataframe(ss_meetup.worksheet("カウント対象外Meetup"))

    # カウント対象外の予約IDを削除
    df_ss_meetup = df_ss_meetup[
        ~df_ss_meetup["予約ID"].isin(df_ss_meetup_del["MeetupID"])
    ]

    # 日時を変換（yyyy-MM-dd HH:mm:ss 形式）
    df_ss_meetup["イベント日"] = pd.to_datetime(
        df_ss_meetup["イベント日"], format="mixed"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    # CSV データとスプレッドシートデータを外部結合し、重複削除
    df_meetup_raw = pd.concat([df_meetup_raw, df_ss_meetup], join="outer", ignore_index=True)
    df_meetup_raw.drop_duplicates(inplace=True)

    return df_meetup_raw


def _process(df_meetup_raw):
    """参加データを加工して df_meetup（全カラム）を作成する。"""
    df_meetup = df_meetup_raw.copy()

    # イベント時間から開始時刻を抽出し、開始・終了日時カラムを作成
    df_meetup["開始時刻"] = df_meetup["イベント時間"].str.extract(r"(\d{2}:\d{2}:\d{2})")
    df_meetup["イベント開始日時"] = pd.to_datetime(
        df_meetup["イベント日"].astype(str) + " " + df_meetup["開始時刻"],
        format="mixed",
    )
    df_meetup["イベント終了日時"] = df_meetup["イベント開始日時"] + pd.Timedelta(hours=1)
    df_meetup.drop(columns=["開始時刻", "イベント時間"], inplace=True)
    df_meetup["イベント日"] = pd.to_datetime(df_meetup["イベント日"]).dt.date

    # 店舗名をもとに店舗番号をマッピング
    df_meetup["店舗番号"] = df_meetup["店舗名"].map(store_dict)
    if df_meetup["店舗名"].count() != df_meetup["店舗番号"].count():
        unmapped = df_meetup[df_meetup["店舗番号"].isnull()]["店舗名"].unique()
        logger.warning("meetup: 店舗マッピングに漏れあり: %s", unmapped)

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


def _load_bukatsu_master(gc):
    """部活ID をキーとした部活マスタ（部活ID タブ）を取得する。"""
    ss_meetup = gc.open_by_url(config.MEETUP_SPREADSHEET_URL)
    df_bukatsu = get_as_dataframe(ss_meetup.worksheet("部活ID"), evaluate_formulas=True)
    df_bukatsu = df_bukatsu.dropna(subset=["bukatsu_id"])

    # 部活ID は数値で管理されているため、bukatsu_id（文字列）と同じキー形式に揃える
    df_bukatsu["bukatsu_id"] = df_bukatsu["bukatsu_id"].astype(int).astype(str)
    df_bukatsu = df_bukatsu.drop_duplicates(subset="bukatsu_id", keep="last")
    return df_bukatsu.set_index("bukatsu_id")


def _to_bq(df_meetup, gc):
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

    # 部活ID：数値IDと部活名などの自由記述が混在するため文字列に統一
    bq_meetup["bukatsu_id"] = bq_meetup["bukatsu_id"].astype("string")

    # 部活ID -> 部活名・目標参加人数（対応表にないIDは NaN のまま）
    bukatsu_master = _load_bukatsu_master(gc)
    bq_meetup["bukatsu"] = bq_meetup["bukatsu_id"].map(bukatsu_master["bukatsu"])
    bq_meetup["goal_attendance"] = bq_meetup["bukatsu_id"].map(
        bukatsu_master["goal_attendance"]
    )

    # 注力可否：「注力している」なら1, else 0
    bq_meetup["pickup_flag"] = (bq_meetup["pickup_flag"] == "注力している").astype(int)

    return bq_meetup


def build(gc, drive_service):
    """参加データを構築して (df_meetup, bq_meetup) を返す。"""
    df_meetup_raw = _extract(gc, drive_service)
    df_meetup = _process(df_meetup_raw)
    bq_meetup = _to_bq(df_meetup, gc)
    return df_meetup, bq_meetup
