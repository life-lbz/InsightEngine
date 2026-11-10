"""插件健康监护器（新增）。"""
from __future__ import annotations

import threading
from typing import Any

from factory.component_factory import health_check_all
from observability.alerting import AlertManager
from observability.logger import get_logger
from observability.metrics import RAG_ERROR_COUNTER

logger = get_logger(__name__)


class PluginSupervisor:
    """插件健康监护器。

    功能：
        - 后台线程定期执行 health_check_all
        - 连续 N 次失败后触发告警
        - 健康状态缓存供 /health 端点读取
    """

    def __init__(
        self,
        config: dict,
        check_interval: int = 30,
        alert_threshold: int = 3,
    ) -> None:
        """初始化监护器。

        入参：
            config：顶层配置字典
            check_interval：检查间隔（秒）
            alert_threshold：连续失败多少次后告警
        """
        self.config = config
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        self._failure_count = 0
        self._last_status: dict[str, Any] = {"overall": True}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def check_once(self) -> dict[str, Any]:
        """执行一次健康检查。

        返回：
            health_check_all 的结果
        """
        try:
            status = health_check_all(self.config)
            self._last_status = status

            if status.get("overall"):
                self._failure_count = 0
            else:
                self._failure_count += 1
                RAG_ERROR_COUNTER.labels(error_type="plugin_unhealthy").inc()

                if self._failure_count >= self.alert_threshold:
                    AlertManager.send_critical(
                        title="插件健康检查失败",
                        message=f"连续 {self._failure_count} 次检查不通过: {status}",
                    )

            return status
        except Exception as exc:
            logger.error("plugin_supervisor_check_failed", error=str(exc))
            self._failure_count += 1
            return {"overall": False, "error": str(exc)}

    def start(self) -> None:
        """启动后台监护线程。"""
        if self._thread and self._thread.is_alive():
            return

        def _loop():
            while not self._stop_event.wait(self.check_interval):
                self.check_once()

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="plugin-supervisor"
        )
        self._thread.start()
        logger.info("plugin_supervisor_started", interval=self.check_interval)

    def stop(self) -> None:
        """停止监护线程。"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("plugin_supervisor_stopped")

    @property
    def last_status(self) -> dict[str, Any]:
        """返回最近一次检查结果。"""
        return self._last_status.copy()