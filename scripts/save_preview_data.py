"""BigQuery にロードする変換後データをローカルに保存する（確認用）。

main.py と同じ抽出・加工処理（etl.pipeline.build_all）を実行するが、
BigQuery へは書き込まず、preview_data/ ディレクトリに Parquet として保存する。
保存したファイルは notebooks/check_head.ipynb で確認できる。

実行:
    python scripts/save_preview_data.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from etl import pipeline  # noqa: E402（sys.path 設定後に import する必要があるため）

PREVIEW_DIR = BASE_DIR / "preview_data"


def _stringify_mixed_object_columns(df):
    """object 型カラム（数値と文字列が混在する場合がある）を文字列型に統一する。

    Parquet 保存時に pyarrow が型推論に失敗するのを避けるための確認用の変換。
    """
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype("string")
    return df


def main():
    bq_tables, _ = pipeline.build_all()

    PREVIEW_DIR.mkdir(exist_ok=True)
    for name, df in bq_tables.items():
        path = PREVIEW_DIR / f"{name}.parquet"
        _stringify_mixed_object_columns(df).to_parquet(path, index=False)
        print(f"{name}: {df.shape[0]}行 x {df.shape[1]}列 -> {path}")


if __name__ == "__main__":
    main()
