# ETL_auto

Google Colab で運用していた ETL ノートブック（`ETL運用.ipynb`）を、Colab 依存を
排除し、サービスアカウント（API）ベースで動く Python プロジェクトへ移植したもの。

各データソース（参加 / 来店 / イベント / 日報 / MCS / SHIRURU / 目標値）を抽出・
加工し、BigQuery のテーブルへ書き込む。

## ディレクトリ構成

```
ETL_auto/
├── main.py                 # エントリーポイント（全処理をオーケストレーション）
├── requirements.txt
├── credentials/            # サービスアカウント鍵（JSON）を置く ※Git 管理対象外
├── data/                   # CSV 元データを置く ※Git 管理対象外
└── etl/
    ├── config.py           # パス・ID・URL などの設定を一元管理
    ├── auth.py             # サービスアカウント認証（Sheets / BigQuery / Forms）
    ├── store_mapping.py    # 店舗名 ⇔ 店舗番号の辞書
    ├── utils.py            # 共通ヘルパー（CSV 読込・フォーム構造解析など）
    ├── meetup.py           # 参加データ        → bq_meetup
    ├── order.py            # 来店データ        → bq_order
    ├── event.py            # イベントデータ    → bq_event
    ├── report.py           # 日報（旧/新フォーム）→ bq_report / bq_report2
    ├── aggregate.py        # 日次データ集計    → df_daily
    ├── user.py             # 個人データ        → bq_user
    ├── mcs.py              # MCS              → bq_mcs
    ├── shiruru.py          # SHIRURU          → bq_srr
    ├── goal.py             # 目標値            → bq_goal / bq_goal_monthly
    └── bigquery_writer.py  # BigQuery への書き込み
```

## 準備

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. サービスアカウント鍵の配置（`credentials/`）

Colab の `google.colab.auth`（ユーザー OAuth）を廃止し、単一のサービスアカウント
（`daily-report`）に Sheets / Drive / BigQuery / Google フォームの権限を集約して
認証する。以下の JSON を `credentials/` に配置する。

- `daily-report-451612-0a0691c91c6b.json` … Sheets / Drive / BigQuery / フォーム 共通

ファイル名は `etl/config.py`（`SERVICE_ACCOUNT_FILE`）で変更可能。

必要な権限（このサービスアカウントのメールアドレスに付与する）:

- 対象スプレッドシートに、サービスアカウントのメールアドレスを閲覧（必要に応じて
  編集）権限で共有する
- BigQuery のデータセットに対する書き込み権限（例: `BigQuery Data Editor`）
- Google フォームは、フォームの所有者がサービスアカウントに共有しておく

### 3. 元データの配置（`data/`）

以下のサブフォルダに CSV を配置する（フォルダ名は `etl/config.py` で変更可能）。

- `data/人別_Meetup参加者_2510更新/` … 参加データ CSV
- `data/来店数/` … 来店データ CSV
- `data/枠別_Meetup開催企業_2510更新/` … イベントデータ CSV

### 4. 設定値の確認

`etl/config.py` の BigQuery プロジェクト ID・データセット、各スプレッドシート
URL、フォーム ID を必要に応じて調整する。

## 実行

```bash
python main.py
```

## 元ノートブックからの主な変更点

- `google.colab.drive` によるマウントを廃止し、ローカルの `data/` を参照
- `google.colab.auth` によるユーザー OAuth を廃止し、サービスアカウント認証に統一
- `DataFrame.to_gbq` を BigQuery クライアントの `load_table_from_dataframe`
  （WRITE_TRUNCATE）に置き換え
- 役割ごとにファイルを分割して構造化
- `.shape` / `.head()` / `.columns` などの確認専用コードを削除
- イベントテーブルへの書き込みは元ノートブックに合わせて既定で無効（`main.py` 参照）
- 店舗別日報シートの書き出しは任意機能とし、`config.STORE_REPORT_SPREADSHEET_URL`
  を設定した場合のみ実行
