"""参加データ（Meetup 参加者）の抽出・加工。

戻り値:
    df2        : 個人データ集計（user モジュール）でも使う加工前の全カラム版
    bq_meetup  : BigQuery 出力用（df5 相当、英語カラム名）
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


def _extract(gc):
    """CSV とスプレッドシートから参加データを抽出・結合する。"""
    from .utils import read_csv_folder

    folder = config.DATA_DIR / config.MEETUP_CSV_SUBDIR
    df1 = read_csv_folder(folder, encodings=("cp932",))
    df1["イベント日"] = pd.to_datetime(df1["イベント日"])

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
    df1 = pd.concat([df1, df_ss_meetup], join="outer", ignore_index=True)
    len_before = len(df1)
    df1.drop_duplicates(inplace=True)
    print(f"{len_before - len(df1)}行の重複データが削除されました")

    return df1


def _process(df1):
    """参加データを加工して df2（全カラム）を作成する。"""
    df2 = df1.copy()

    # イベント時間から開始時刻を抽出し、開始・終了日時カラムを作成
    df2["開始時刻"] = df2["イベント時間"].str.extract(r"(\d{2}:\d{2}:\d{2})")
    df2["イベント開始日時"] = pd.to_datetime(
        df2["イベント日"].astype(str) + " " + df2["開始時刻"]
    )
    df2["イベント終了日時"] = df2["イベント開始日時"] + pd.Timedelta(hours=1)
    df2.drop(columns=["開始時刻", "イベント時間"], inplace=True)
    df2["イベント日"] = pd.to_datetime(df2["イベント日"]).dt.date

    # 店舗名をもとに店舗番号をマッピング
    df2["店舗番号"] = df2["店舗名"].map(store_dict)
    if df2["店舗名"].count() == df2["店舗番号"].count():
        print("マッピング成功")
    else:
        print("マッピングに漏れあり")
        print(df2[df2["店舗番号"].isnull()]["店舗名"].unique())

    df2 = df2.rename(columns={"予約ID": "MeetupID"})
    df2["MeetupID"] = df2["MeetupID"].astype(int)
    df2["会員ID"] = df2["会員ID"].astype(int)

    # 参加：参加なら1, else 0
    df2["参加可否"] = (df2["参加可否"] == "参加").astype(int)
    df2 = df2.rename(columns={"参加可否": "参加"})

    # 参加予定：参加してないかつキャンセル有無が欠損 → 1, else → 0
    df2["参加予定"] = ((df2["参加"] == 0) & (df2["キャンセル有無"].isnull())).astype(int)

    # 開催形式を簡潔に言い換え
    df2["開催形式"] = df2["開催形式"].replace(
        {"オンラインMeetup": "オンライン", "Meetup (店舗開催)": "対面"}
    )

    df2["予約ID"] = (
        df2["イベント開始日時"].astype(str)
        + "_"
        + df2["MeetupID"].astype(str)
        + "_"
        + df2["結合ID"].astype(str)
    )

    df2["cancell"] = (df2["キャンセル有無"] == "キャンセル").astype(int)
    df2["no_show"] = (df2["キャンセル有無"] == "無断欠席").astype(int)

    return df2


def _to_bq(df2):
    """df2 から BigQuery 出力用データフレーム（bq_meetup / df5）を作成する。"""
    df5 = df2[
        [
            "予約ID", "イベント開始日時", "イベント終了日時", "MeetupID", "結合ID",
            "会員ID", "店舗番号", "店舗名", "企業名", "開催形式", "参加", "参加予定",
            "cancell", "no_show", "予約したきっかけ", "学年", "入学年月", "予約日",
            "卒業年月", "大学", "文理", "学部", "専攻", "性別", "出身地", "満足度",
            "参加経由", "注力可否", "部活ID",
        ]
    ].copy()

    df5.rename(columns=COLUMN_MAPPING, inplace=True)

    # Pickup count
    cond_1 = (
        (df5["attendance"] == 1) | (df5["planned_attendance"] == 1)
    ) & (df5["Pickup1"] == "注力している")
    cond_2 = ((df5["attendance"] == 1) | (df5["planned_attendance"] == 1)) & (
        (df5["Pickup1"].isna()) | (df5["Pickup1"] == "注力していない")
    )
    cond_3 = (df5["attendance"] == 0) & (df5["planned_attendance"] == 0)

    df5["Pickup"] = np.select([cond_1, cond_2, cond_3], [2, 1, 0], default=np.nan)
    df5["Pickup"] = df5["Pickup"].fillna(0).astype(int)

    df5 = df5.drop(columns=["Pickup1"])

    return df5


def build(gc):
    """参加データを構築して (df2, bq_meetup) を返す。"""
    df1 = _extract(gc)
    df2 = _process(df1)
    bq_meetup = _to_bq(df2)
    return df2, bq_meetup
