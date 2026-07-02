"""Google API 認証（サービスアカウント）。

Colab の `google.colab.auth` / `drive.mount` を廃止し、サービスアカウント
鍵ファイルから各サービスのクライアントを生成する。
"""

import gspread
from google.cloud import bigquery
from google.oauth2 import service_account
from googleapiclient.discovery import build

from . import config

# gspread（スプレッドシート）用スコープ
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# BigQuery 用スコープ
BIGQUERY_SCOPES = ["https://www.googleapis.com/auth/bigquery"]

# Google フォーム（日報）用スコープ：回答とフォーム構造の読み取り
FORMS_SCOPES = [
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/forms.body.readonly",
]


def get_gspread_client():
    """gspread のクライアントを返す。"""
    creds = service_account.Credentials.from_service_account_file(
        str(config.SERVICE_ACCOUNT_FILE), scopes=SHEETS_SCOPES
    )
    return gspread.authorize(creds)


def get_bigquery_client():
    """BigQuery のクライアントを返す。"""
    creds = service_account.Credentials.from_service_account_file(
        str(config.SERVICE_ACCOUNT_FILE), scopes=BIGQUERY_SCOPES
    )
    return bigquery.Client(project=config.BIGQUERY_PROJECT_ID, credentials=creds)


def get_forms_service():
    """Google フォーム API のサービスオブジェクトを返す。"""
    creds = service_account.Credentials.from_service_account_file(
        str(config.FORMS_SERVICE_ACCOUNT_FILE), scopes=FORMS_SCOPES
    )
    return build("forms", "v1", credentials=creds)
