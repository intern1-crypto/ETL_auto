"""各モジュールで共有するヘルパー関数。"""

import io
import json
import re

import pandas as pd


def read_csv_folder_from_drive(drive_service, folder_id, encodings=("cp932",)):
    """Google Drive の指定フォルダ内の全 CSV を読み込み、縦結合したデータフレームを返す。

    encodings に複数指定した場合、ファイルごとに先頭から順に試し、
    最初に成功したエンコーディングで読み込む。
    サービスアカウントに対象フォルダの閲覧権限を共有しておくこと。
    """
    files = []
    page_token = None
    while True:
        response = (
            drive_service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    csv_files = [f for f in files if f["name"].lower().endswith(".csv")]

    df_list = []
    for file in csv_files:
        content = drive_service.files().get_media(fileId=file["id"]).execute()
        last_error = None
        for enc in encodings:
            try:
                df_list.append(pd.read_csv(io.BytesIO(content), encoding=enc))
                last_error = None
                break
            except UnicodeDecodeError as e:
                last_error = e
        if last_error is not None:
            raise last_error
    return pd.concat(df_list, ignore_index=True)


def add_section_to_items(items):
    """フォームの items に、ページ区切り（店舗番号）を section として付与する。

    ページ区切りアイテムのタイトルに含まれる数字をセクション番号とみなし、
    それ以降の質問アイテムに section を設定する。
    """
    current_section = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        # ページ区切りの判定と更新
        if "pageBreakItem" in item:
            title = item.get("title", "")
            match = re.search(r"(\d+)", title)
            current_section = int(match.group(1)) if match else 0

        # 質問アイテムへの section 追加
        elif "questionItem" in item:
            item["section"] = current_section

    return items


def fix_shift_in_at(shift, timestamp):
    """シフトイン日時の年欠損を timestamp から補完して datetime に変換する。"""
    try:
        # すでに年がある場合（YYYY-MM-DD HH:MM）
        if len(shift.split()) == 2 and shift.count("-") == 2:
            return pd.to_datetime(shift, format="%Y-%m-%d %H:%M", errors="coerce")

        # 年がない場合（MM-DD HH:MM）→ timestamp から年を補完し、秒を"00"にする
        year = timestamp.year
        shift_fixed = f"{year}-{shift}:00"
        return pd.to_datetime(shift_fixed, format="%Y-%m-%d %H:%M:%S", errors="coerce")

    except Exception as e:
        print(f"エラー: {e} (shift={shift}, timestamp={timestamp})")
        return None


def schema_maker(df):
    """DataFrame の全カラムの name と type を BigQuery スキーマ形式の JSON で返す。"""
    type_dict = {
        "object": "STRING",
        "int64": "INTEGER",
        "float64": "FLOAT",
        "datetime64[ns]": "DATETIME",
        "bool": "BOOLEAN",
    }
    columns_info = [
        {"name": col, "type": type_dict.get(str(dtype), "STRING")}
        for col, dtype in df.dtypes.items()
    ]
    return json.dumps(columns_info, indent=4)
