import os
import time
import random
import queue
import threading
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext

SESSION_DIR = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "session")


class WhatsAppBot:
    """
    Toda interação com o Playwright ocorre dentro de _worker_loop,
    que roda em uma thread dedicada. Comandos são enviados via _queue.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._connected = False
        self._worker: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # API pública (chamada de qualquer thread)
    # ------------------------------------------------------------------

    def launch(self, on_ready: Callable[[], None], on_error: Callable[[str], None]) -> None:
        self._worker = threading.Thread(
            target=self._worker_loop,
            args=(on_ready, on_error),
            daemon=True,
        )
        self._worker.start()

    def is_connected(self) -> bool:
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
            page.goto("https://web.whatsapp.com")
            page.wait_for_selector('[data-testid="chat-list"]', timeout=120_000)
            self._connected = True
            on_ready()
        except Exception as e:
            on_error(str(e))
            return

        # Loop de tarefas
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
        except Exception:
            pass
        self._connected = False

    def _do_send(self, page: Page, phone: str, message: str) -> None:
        phone_clean = "".join(filter(str.isdigit, phone))

        # 1. Navegar para o chat do número via URL direta
        page.goto(f"https://web.whatsapp.com/send?phone={phone_clean}", wait_until="domcontentloaded")
        _pause(1.5, 3.0)

        # 2. Verificar se o número é válido (popup de número inválido)
        invalid = page.query_selector('[data-testid="popup-contents"]')
        if invalid:
            raise RuntimeError("Número não encontrado no WhatsApp.")

        # 3. Aguardar a caixa de mensagem aparecer
        msg_box = page.wait_for_selector(
            '[data-testid="conversation-compose-box-input"]',
            timeout=20_000,
        )

        # 4. Clicar na caixa de mensagem
        _pause(0.5, 1.0)
        msg_box.click()
        _pause(0.4, 0.9)

        # 5. Digitar a mensagem linha a linha
        for i, line in enumerate(message.split("\n")):
            if i > 0:
                msg_box.press("Shift+Enter")
                _pause(0.2, 0.5)
            msg_box.type(line, delay=_human_delay())

        # 6. Pausa antes de enviar (simula revisão)
        _pause(0.8, 1.8)
        msg_box.press("Enter")

        # 7. Aguardar confirmação de envio
        _pause(0.8, 1.5)


def _human_delay() -> float:
    """Delay em ms entre teclas ao digitar (usado pelo Playwright)."""
    return random.uniform(40, 110)


def _pause(min_s: float, max_s: float) -> None:
    """Pausa entre ações para simular comportamento humano."""
    time.sleep(random.uniform(min_s, max_s))
