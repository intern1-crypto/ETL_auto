"""プロジェクト全体の設定値をまとめるモジュール。

Colab の Google Drive マウントや colab.auth を廃止し、サービスアカウント
（API）ベースで動かすための各種パス・ID・URL をここで一元管理する。
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# ディレクトリ
# ---------------------------------------------------------------------------
# このリポジトリのルート（etl/ の一つ上）
BASE_DIR = Path(__file__).resolve().parent.parent

# サービスアカウントの JSON（秘密鍵）などを置くディレクトリ
CREDENTIALS_DIR = BASE_DIR / "credentials"

# ---------------------------------------------------------------------------
# 認証（サービスアカウント）
# ---------------------------------------------------------------------------
# Sheets / Drive / BigQuery / Google フォームをすべて 1 つのサービスアカウント
# （daily-report）に集約する運用。
# ※ credentials ディレクトリに鍵を配置し、このサービスアカウントのメールアドレスへ
#   対象スプレッドシート・BigQuery データセット・Google フォームの権限を付与しておくこと。
SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "gcp-secret-key.json"

# Google フォーム（日報）読み取り用の鍵。上と同じサービスアカウントを使用する。
FORMS_SERVICE_ACCOUNT_FILE = SERVICE_ACCOUNT_FILE

# ---------------------------------------------------------------------------
# Google Drive の CSV フォルダ ID
# ※サービスアカウントのメールアドレスに対象フォルダの閲覧権限を共有しておくこと
# ---------------------------------------------------------------------------
MEETUP_CSV_FOLDER_ID = "1-Q5KPssbgikwFamYPKmwfAp0quYVPZCb"
ORDER_CSV_FOLDER_ID = "1-i9ZHIoiSB8e6cWqhZnVMoSOLslE21q-"
EVENT_CSV_FOLDER_ID = "1LM7rjfi5DMJNdL9VMKY79Y4wWumZYjzi"

# ---------------------------------------------------------------------------
# スプレッドシート URL
# ---------------------------------------------------------------------------
MEETUP_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1B33R0VydVlKLH7UrDwyAWZEwEksFrhgDSpGZbMktDKQ/edit?gid=0#gid=0"
ORDER_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1584pXhsuZfu-hmx9N1p9_JQ3V33uy-VFGdHkbfWxCxU/edit?gid=2012077172#gid=2012077172"
EVENT_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bNd_oqfDEIvVysQSVGMdgWOxY39hSRZLgUBkVsRjysQ/edit?gid=0#gid=0"
MCS_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/11jDJSgYZlVJgMQ5HQy94SuKdWQcv4R5PuMjI0B-dSI4/edit?gid=0#gid=0"
SHIRURU_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1IfieJcqJPft1dFfsGGO3n2buPxL_TE07O-ZZyy4hqLI/edit?gid=0#gid=0"
GOAL_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1P0cnzgYwEe1wYYeTuhi0qiv7c81q8cCy4T4JfnJ3f-Q/edit?gid=769489446#gid=769489446"

# ---------------------------------------------------------------------------
# Google フォーム ID（日報）
# ---------------------------------------------------------------------------
REPORT_FORM_ID_NEW = "1-g9wDUw5OJeUTbaMfoFk-XeP56HMQaIGSJ95XVZ6z98"

# ---------------------------------------------------------------------------
# 店舗別日報シート書き出し（任意機能）
# ---------------------------------------------------------------------------
# 店舗ごとの日報を書き出すスプレッドシート URL。None の場合はスキップする。
STORE_REPORT_SPREADSHEET_URL = None
# 書き出し対象の開始日時（この日時より後の timestamp のみ出力）。文字列 or None。
STORE_REPORT_START_DATE = None

# ---------------------------------------------------------------------------
# BigQuery
# ---------------------------------------------------------------------------
BIGQUERY_PROJECT_ID = "fair-solution-453613-e2"
BIGQUERY_DATASET = "202506"

# BigQuery のテーブル名（bq_* データフレームと対応）
TABLE_NAMES = {
    "order": "来店",
    "meetup": "Meetup参加",
    "event": "イベント",
    "report_new": "日報_new",
    "daily": "日次データ",
    "monthly": "月次データ",
    "user": "ユーザー",
    "goal": "目標値",
    "goal_monthly": "月毎目標値",
    "mcs": "MCS",
    "shiruru": "SHIRURU",
}
