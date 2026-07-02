"""BigQuery へのデータフレーム書き込み。

Colab の `DataFrame.to_gbq` の代わりに BigQuery クライアントの
`load_table_from_dataframe` を使い、テーブルを毎回洗い替え（WRITE_TRUNCATE）する。
"""

from google.cloud import bigquery

from . import config


class BigQueryWriter:
    """BigQuery へテーブルを書き込むためのラッパ。"""

    def __init__(self, client, project_id=None, dataset=None):
        self.client = client
        self.project_id = project_id or config.BIGQUERY_PROJECT_ID
        self.dataset = dataset or config.BIGQUERY_DATASET

    def write(self, df, table_name):
        """データフレームを指定テーブルへ洗い替え書き込みする。"""
        table_id = f"{self.project_id}.{self.dataset}.{table_name}"
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        job = self.client.load_table_from_dataframe(
            df, table_id, job_config=job_config
        )
        job.result()  # 完了まで待機
        print(f"{table_name} を書き込みました（{len(df)}行）")
