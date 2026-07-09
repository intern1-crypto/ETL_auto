"""日報データ（Google フォーム）の抽出・加工。

戻り値:
    build_new(...) -> (bq_report_new, df_report_new, form_structure)
"""

import logging

import pandas as pd
from gspread_dataframe import set_with_dataframe

from . import config
from .store_mapping import inverse_store_dict, store_dict
from .utils import add_section_to_items, fix_shift_in_at

logger = logging.getLogger(__name__)

# 全店共通の出力カラム
QUESTIONS_COMMON = [
    "responseId", "timestamp", "store_code", "store", "staff_number",
    "staff_name", "shift-in_at", "customer_count", "target_count",
    "non-announcement", "invitation",
]

RENAME_MAPPING = {
    "対象数": "target_count",
    "スタッフ名（フルネーム）": "staff_name",
    "スタッフナンバー（7桁）": "staff_number",
    "シフトイン日時": "shift-in_at",
    "非接客時間（OP / CL / 貸切 / 席利用シフト）": "non-serving_time",
    "接客時間（日中 / PICSシフト）": "serving_time",
    "接客数": "customer_count",
    "未告知数": "non-announcement",
    "誘致数": "invitation",
}

# 店舗別シート書き出し時の日本語カラム名
DICT_JP = {
    "staff_name": "スタッフ名",
    "staff_number": "スタッフナンバー",
    "shift-in_at": "シフトイン日時",
    "customer_count": "接客数",
    "non-announcement": "未告知数",
    "invitation": "誘致数",
    "store": "店舗",
    "store_code": "店舗番号",
    "target_count": "対象数",
}


def _fetch_responses(service, form_id):
    """フォームの回答を全件取得する（1回のリクエストで最大5000件）。"""
    responses = []
    page_token = None
    while True:
        response = (
            service.forms()
            .responses()
            .list(formId=form_id, pageSize=5000, pageToken=page_token)
            .execute()
        )
        responses.extend(response.get("responses", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return responses


def _responses_to_df(responses):
    """回答を質問IDをカラムとした DataFrame に変換する。"""
    data = []
    for res in responses:
        row = {
            "responseId": res["responseId"],
            "timestamp": res["createTime"],
        }
        for question_id, answer in res.get("answers", {}).items():
            row[question_id] = (
                answer.get("textAnswers", {}).get("answers", [{}])[0].get("value", "")
            )
        data.append(row)
    return pd.DataFrame(data)


def _get_form_structure(service, form_id):
    """フォームの構造を取得し、各質問に section（店舗番号）を付与する。"""
    form = service.forms().get(formId=form_id).execute()
    return add_section_to_items(form.get("items", []))


def _common_question_mapping(form_structure):
    """全店共通セクション（section == 0）の質問ID -> 質問内容マップを作成する。"""
    mapping = {}
    for item in form_structure:
        if item.get("section", {}) != 0:
            continue
        question_id = (
            item.get("questionItem", {}).get("question", {}).get("questionId", "No ID")
        )
        mapping[question_id] = item.get("title", {})
    return mapping


def _common_datetime_and_ints(df_report):
    """timestamp・数値カラム・shift-in_at・スタッフ名などの共通加工を行う。"""
    df_report["timestamp"] = pd.to_datetime(df_report["timestamp"], format="mixed")
    # 標準時から日本時間に
    df_report["timestamp"] = df_report["timestamp"].dt.tz_convert("Asia/Tokyo")

    # 一旦浮動小数点型にしてから整数型に
    cols = ["staff_number", "target_count", "customer_count", "non-announcement"]
    df_report[cols] = df_report[cols].astype(float).astype(int)

    # 数字でないものは0に
    df_report["invitation"] = (
        df_report["invitation"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # shift-in_at は途中まで年がないため timestamp から補完
    df_report["shift-in_at"] = df_report.apply(
        lambda row: fix_shift_in_at(row["shift-in_at"], row["timestamp"]), axis=1
    )

    # シフトイン日時とスタッフナンバーが重複している「先のデータ」を削除
    original_len = len(df_report)
    df_report = df_report[
        ~df_report.duplicated(subset=["shift-in_at", "staff_number"], keep="last")
    ]

    # タイムゾーン情報を落として naive datetime に
    df_report["timestamp"] = pd.to_datetime(
        df_report["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    df_report["shift-in_at"] = pd.to_datetime(
        df_report["shift-in_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    # シフトイン日時がフォーム送信日時より後（入力ミス）の行を除外
    df_report = df_report[df_report["shift-in_at"] <= df_report["timestamp"]]

    # スタッフ名から半角・全角スペースを除く
    df_report["staff_name"] = df_report["staff_name"].str.replace(
        r"[ 　]+", "", regex=True
    )

    return df_report


def build_new(service):
    """新フォームの日報を構築して (bq_report_new, df_report_new, form_structure) を返す。"""
    responses = _fetch_responses(service, config.REPORT_FORM_ID_NEW)
    df_report_raw = _responses_to_df(responses)

    form_structure = _get_form_structure(service, config.REPORT_FORM_ID_NEW)
    question_mapping_common = _common_question_mapping(form_structure)
    df_report_raw.rename(columns=question_mapping_common, inplace=True)

    df_report_new = df_report_raw.copy()

    # 新フォームは標準の store_dict でマッピング
    df_report_new["store_code"] = df_report_new["店舗名（シフトインした店舗）"].map(
        store_dict
    )
    if (
        df_report_new["店舗名（シフトインした店舗）"].count()
        != df_report_new["store_code"].count()
    ):
        unmapped = df_report_new[df_report_new["store_code"].isnull()][
            "店舗名（シフトインした店舗）"
        ].unique()
        logger.warning("report: 店舗マッピングに漏れあり: %s", unmapped)

    # timestamp をもとに昇順に並べる
    df_report_new.sort_values(by="timestamp", ascending=True, inplace=True)
    df_report_new.reset_index(drop=True, inplace=True)

    # 新フォームは店舗名カラムを 'store' にリネームして保持
    rename_new = dict(RENAME_MAPPING)
    rename_new["店舗名（シフトインした店舗）"] = "store"
    df_report_new.rename(columns=rename_new, inplace=True)

    df_report_new = _common_datetime_and_ints(df_report_new)

    bq_report_new = df_report_new[QUESTIONS_COMMON].copy()

    return bq_report_new, df_report_new, form_structure


def write_store_report_sheets(
    gc, df_report, form_structure, bq_report, spreadsheet_url, start_date
):
    """店舗ごとの日報を対象スプレッドシートの店舗番号シートへ書き出す（任意機能）。"""
    import gspread

    spreadsheet = gc.open_by_url(spreadsheet_url)
    start_date = pd.to_datetime(start_date)

    # 質問ID -> 質問内容マップ（全店分）
    question_mapping = {}
    for item in form_structure:
        question_id = (
            item.get("questionItem", {}).get("question", {}).get("questionId", "No ID")
        )
        question_mapping[question_id] = item.get("title", {})

    stores = sorted(bq_report["store_code"].unique().tolist())

    for store_code in stores:
        questions_store = []
        for item in form_structure:
            if item.get("section", {}) == store_code:
                question_id = (
                    item.get("questionItem", {})
                    .get("question", {})
                    .get("questionId", "No ID")
                )
                if question_id in df_report.columns:
                    questions_store.append(question_id)

        df_store = df_report[QUESTIONS_COMMON + questions_store]
        df_store = df_store[df_store["store_code"] == store_code]
        df_store = df_store[df_store["timestamp"] > start_date]

        df_store.rename(columns=question_mapping, inplace=True)
        df_store.rename(columns=DICT_JP, inplace=True)

        try:
            worksheet = spreadsheet.worksheet(str(store_code))
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=str(store_code), rows="5000", cols="30"
            )
        set_with_dataframe(worksheet, df_store)
