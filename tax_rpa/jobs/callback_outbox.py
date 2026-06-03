import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib import request
from urllib.error import URLError

from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.redaction import redact_sensitive


Transport = Callable[[str, dict[str, Any], dict[str, str], int], "CallbackTransportResponse"]


@dataclass(frozen=True)
class CallbackTransportResponse:
    """回调传输响应，封装作业、回调回调队列相关状态和行为。"""
    status_code: int
    body: str = ""


@dataclass(frozen=True)
class CallbackResult:
    """回调结果结果对象，承载执行状态、证据和后续判断所需字段。"""
    callback_state: str
    outbox_record_path: str | None = None
    http_status: int | None = None
    error: str | None = None


class CallbackOutbox:
    """回调发件箱，负责投递回调并保存待重试或死信记录。"""
    def __init__(
        self,
        *,
        artifacts: JobArtifacts,
        callback_url: str | None,
        callback_secret: str | None = None,
        transport: Transport | None = None,
        timeout_seconds: int = 10,
        dead_letter_after: timedelta = timedelta(hours=24),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """初始化回调回调队列实例，保存依赖、配置和运行上下文。"""
        self.artifacts = artifacts
        self.callback_url = callback_url
        self.callback_secret = callback_secret
        self.transport = transport or _urllib_transport
        self.timeout_seconds = timeout_seconds
        self.dead_letter_after = dead_letter_after
        self.now = now or (lambda: datetime.now().astimezone())

    def deliver(self, payload: dict[str, Any]) -> CallbackResult:
        """投递业务回调，并记录成功、待重试或死信结果。"""
        if not self.callback_url:
            self._log("callback_skipped", "not_configured", payload=payload)
            return CallbackResult(callback_state="not_configured")
        return self._attempt(payload=payload, attempt_count=1, first_attempt_at=self.now())

    def retry_due(self, outbox_record_path: str | Path | None) -> CallbackResult:
        """执行作业、回调回调队列中的retrydue逻辑，供业务流程或相邻模块调用。"""
        if outbox_record_path is None:
            return CallbackResult(callback_state="not_configured")
        record_path = self.artifacts.root / outbox_record_path
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("callback_state") != "pending":
            return CallbackResult(
                callback_state=record.get("callback_state", "not_configured"),
                outbox_record_path=Path(outbox_record_path).as_posix(),
                http_status=record.get("last_http_status"),
                error=record.get("last_error"),
            )
        first_attempt_at = datetime.fromisoformat(record["first_attempt_at"])
        return self._attempt(
            payload=record["payload"],
            attempt_count=int(record["attempt_count"]) + 1,
            first_attempt_at=first_attempt_at,
        )

    def _attempt(
        self,
        *,
        payload: dict[str, Any],
        attempt_count: int,
        first_attempt_at: datetime,
    ) -> CallbackResult:
        """执行作业、回调回调队列中的内部辅助逻辑：attempt。"""
        now = self.now()
        headers = self._headers(payload)
        http_status: int | None = None
        error: str | None = None
        try:
            response = self.transport(
                self.callback_url or "",
                payload,
                headers,
                self.timeout_seconds,
            )
            http_status = response.status_code
            delivered = 200 <= response.status_code <= 299
        except Exception as exc:
            delivered = False
            error = str(exc)

        if delivered:
            self._log(
                "callback_attempt",
                "delivered",
                payload=payload,
                attempt_count=attempt_count,
                http_status=http_status,
            )
            return CallbackResult(
                callback_state="delivered",
                http_status=http_status,
            )

        callback_state = (
            "dead_letter"
            if now - first_attempt_at >= self.dead_letter_after
            else "pending"
        )
        next_attempt_at = None
        if callback_state == "pending":
            next_attempt_at = (now + _backoff(attempt_count)).isoformat()
        record_path = self._write_record(
            payload=payload,
            callback_state=callback_state,
            attempt_count=attempt_count,
            first_attempt_at=first_attempt_at,
            last_attempt_at=now,
            next_attempt_at=next_attempt_at,
            last_http_status=http_status,
            last_error=error,
        )
        self._log(
            "callback_attempt",
            callback_state,
            payload=payload,
            attempt_count=attempt_count,
            http_status=http_status,
            error=error,
            outbox_record_path=record_path,
        )
        return CallbackResult(
            callback_state=callback_state,
            outbox_record_path=record_path,
            http_status=http_status,
            error=error,
        )

    def _headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """执行作业、回调回调队列中的内部辅助逻辑：headers。"""
        headers = {"Content-Type": "application/json"}
        if self.callback_secret:
            body = _payload_bytes(payload)
            signature = hmac.new(
                self.callback_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Tax-Rpa-Signature"] = f"sha256={signature}"
        return headers

    def _write_record(
        self,
        *,
        payload: dict[str, Any],
        callback_state: str,
        attempt_count: int,
        first_attempt_at: datetime,
        last_attempt_at: datetime,
        next_attempt_at: str | None,
        last_http_status: int | None,
        last_error: str | None,
    ) -> str:
        """写入回调队列记录，用于重试和排障。"""
        record = {
            "callback_state": callback_state,
            "callback_url": self.callback_url,
            "payload": payload,
            "attempt_count": attempt_count,
            "first_attempt_at": first_attempt_at.isoformat(),
            "last_attempt_at": last_attempt_at.isoformat(),
            "next_attempt_at": next_attempt_at,
            "last_http_status": last_http_status,
            "last_error": last_error,
        }
        return self.artifacts.write_json("callback_outbox.json", redact_sensitive(record))

    def _log(self, event: str, status: str, **data: Any) -> None:
        """执行作业、回调回调队列中的内部辅助逻辑：log。"""
        self.artifacts.logs_dir.mkdir(parents=True, exist_ok=True)
        payload = data.get("payload") or {}
        item = {
            "time": self.now().isoformat(timespec="seconds"),
            "job_id": payload.get("job_id"),
            "idempotency_key": payload.get("idempotency_key"),
            "event": event,
            "status": status,
            **data,
        }
        with (self.artifacts.logs_dir / "callbacks.jsonl").open(
            "a",
            encoding="utf-8",
        ) as stream:
            stream.write(json.dumps(redact_sensitive(item), ensure_ascii=False) + "\n")


def _payload_bytes(payload: dict[str, Any]) -> bytes:
    """执行作业、回调回调队列中的内部辅助逻辑：载荷bytes。"""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _backoff(attempt_count: int) -> timedelta:
    """执行作业、回调回调队列中的内部辅助逻辑：backoff。"""
    return timedelta(minutes=2 ** min(attempt_count - 1, 10))


def _urllib_transport(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> CallbackTransportResponse:
    """执行作业、回调回调队列中的内部辅助逻辑：urllib传输。"""
    body = _payload_bytes(payload)
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return CallbackTransportResponse(
                status_code=response.status,
                body=response.read().decode("utf-8", errors="replace"),
            )
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc
