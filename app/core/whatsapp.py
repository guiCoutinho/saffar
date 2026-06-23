import logging
import os
import time
import random
import queue
import threading
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext

SESSION_DIR = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "session")

logger = logging.getLogger(__name__)


class WhatsAppBot:
    """
    Toda interação com o Playwright ocorre dentro de _worker_loop,
    que roda em uma thread dedicada. Comandos são enviados via _queue.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._connected = False
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # API pública (chamada de qualquer thread)
    # ------------------------------------------------------------------

    def launch(self, on_ready: Callable[[], None], on_error: Callable[[str], None]) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._worker_loop,
                args=(on_ready, on_error),
                daemon=True,
            )
            self._worker.start()

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def send_message(
        self,
        phone: str,
        message: str,
        on_success: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._queue.put(("send", phone, message, on_success, on_error))

    def stop(self) -> None:
        self._queue.put(("stop",))
        with self._lock:
            self._connected = False

    # ------------------------------------------------------------------
    # Worker — roda inteiramente na thread dedicada do Playwright
    # ------------------------------------------------------------------

    def _worker_loop(self, on_ready: Callable, on_error: Callable) -> None:
        os.makedirs(SESSION_DIR, exist_ok=True)
        try:
            pw = sync_playwright().start()
            context: BrowserContext = pw.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                args=["--start-maximized"],
            )
            page: Page = context.new_page()
            page.goto("https://web.whatsapp.com", timeout=30_000)
            page.wait_for_selector('[data-testid="chat-list"]', timeout=120_000)
            with self._lock:
                self._connected = True
            on_ready()
        except Exception as e:
            on_error(str(e))
            return

        while True:
            try:
                task = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            if task[0] == "stop":
                break
            elif task[0] == "send":
                _, phone, message, on_success, on_error_cb = task
                try:
                    self._do_send(page, phone, message)
                    on_success()
                except Exception as e:
                    on_error_cb(str(e))

        try:
            context.close()
            pw.stop()
        except Exception as e:
            logger.warning("Erro ao fechar Playwright: %s", e)
        with self._lock:
            self._connected = False

    def _do_send(self, page: Page, phone: str, message: str) -> None:
        phone_clean = "".join(filter(str.isdigit, phone))

        try:
            page.goto(
                f"https://web.whatsapp.com/send?phone={phone_clean}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
        except Exception:
            raise RuntimeError("Timeout ao navegar para o chat (conexão lenta ou WhatsApp Web travado).")

        _pause(1.5, 3.0)

        invalid = page.query_selector('[data-testid="popup-contents"]')
        if invalid:
            raise RuntimeError("Número não encontrado no WhatsApp.")

        msg_box = page.wait_for_selector(
            '[data-testid="conversation-compose-box-input"]',
            timeout=20_000,
        )

        _pause(0.5, 1.0)
        msg_box.click()
        _pause(0.4, 0.9)

        for i, line in enumerate(message.split("\n")):
            if i > 0:
                msg_box.press("Shift+Enter")
                _pause(0.2, 0.5)
            msg_box.type(line, delay=_human_delay())

        _pause(0.8, 1.8)
        msg_box.press("Enter")
        _pause(0.8, 1.5)


def _human_delay() -> float:
    """Delay em ms entre teclas ao digitar (usado pelo Playwright)."""
    return random.uniform(40, 110)


def _pause(min_s: float, max_s: float) -> None:
    """Pausa entre ações para simular comportamento humano."""
    time.sleep(random.uniform(min_s, max_s))
