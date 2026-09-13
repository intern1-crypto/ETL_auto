"""LINE WORKS の Bot 経由でトークルームへメッセージを送信するモジュール。

Error/Warning 通知に使う。認証情報（CLIENT_ID / CLIENT_SECRET / SERVICE_ACCOUNT /
PRIVATE_KEY / BOT_ID / CHANNEL_ID）は config.LINEWORKS_SECRET_FILE の JSON から読み込む。
サービスアカウント方式の JWT Bearer フローでアクセストークンを取得する。
"""

import json
import logging
import time

import requests
from google.auth.crypt import rsa
from google.auth import jwt as google_jwt

from etl.config import LINEWORKS_BOT_ID, LINEWORKS_CHANNEL_ID, LINEWORKS_SECRET_FILE

TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"
API_BASE_URL = "https://www.worksapis.com/v1.0"

_cached_token = None
_cached_token_expires_at = 0.0


def _load_secret():
    with open(LINEWORKS_SECRET_FILE, encoding="utf-8") as f:
        return json.load(f)


def _build_jwt(secret):
    now = int(time.time())
    payload = {
        "iss": secret["CLIENT_ID"],
        "sub": secret["SERVICE_ACCOUNT"],
        "iat": now,
        "exp": now + 3600,
    }
    signer = rsa.RSASigner.from_string(secret["PRIVATE_KEY"])
    return google_jwt.encode(signer, payload).decode("utf-8")


def _fetch_access_token(secret):
    response = requests.post(
        TOKEN_URL,
        data={
            "assertion": _build_jwt(secret),
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": secret["CLIENT_ID"],
            "client_secret": secret["CLIENT_SECRET"],
            "scope": "bot",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    expires_at = time.time() + int(data["expires_in"]) - 60
    return data["access_token"], expires_at


def _get_access_token(secret):
    global _cached_token, _cached_token_expires_at
    if _cached_token is None or time.time() >= _cached_token_expires_at:
        _cached_token, _cached_token_expires_at = _fetch_access_token(secret)
    return _cached_token


def send_message(text, channel_id=None):
    """指定したトークルーム（channel_id 省略時は config.LINEWORKS_CHANNEL_ID）へ
    テキストメッセージを送信する。"""
    secret = _load_secret()
    access_token = _get_access_token(secret)

    response = requests.post(
        f"{API_BASE_URL}/bots/{LINEWORKS_BOT_ID}/channels/{channel_id or LINEWORKS_CHANNEL_ID}/messages",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"content": {"type": "text", "text": text}},
        timeout=10,
    )
    response.raise_for_status()


class LineWorksHandler(logging.Handler):
    """WARNING 以上のログレコードを LINE WORKS のトークルームへ通知する logging ハンドラ。

    通知自体の失敗（ネットワークエラー等）でパイプラインを止めないよう、
    emit 内の例外は self.handleError に委譲する。
    """

    MAX_LENGTH = 1500

    def __init__(self, level=logging.WARNING):
        super().__init__(level=level)
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record):
        try:
            text = self.format(record)
            if len(text) > self.MAX_LENGTH:
                text = text[: self.MAX_LENGTH] + "…(省略)"
            send_message(text)
        except Exception:
            self.handleError(record)
