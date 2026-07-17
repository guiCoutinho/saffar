import logging
import os
import shutil
import time
import random
import queue
import threading
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext

from app.core.phone_utils import to_wa_phone

SESSION_DIR = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "session")

# O WhatsApp Web já removeu atributos data-testid em atualizações passadas.
# Cada seletor tem um fallback estrutural para sobreviver a essas mudanças.
_SEL_CHAT_LIST = '[data-testid="chat-list"], #pane-side'
_SEL_COMPOSE_BOX = '[data-testid="conversation-compose-box-input"], footer div[contenteditable="true"]'
_SEL_INVALID_POPUP = '[data-testid="popup-contents"], div[data-animate-modal-popup="true"]'

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

    def shutdown(self, timeout: float = 3.0) -> None:
        """Encerra o navegador ao fechar o app, aguardando o worker finalizar."""
        self.stop()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout)

    def disconnect(self, on_done: Optional[Callable[[], None]] = None) -> None:
        """Fecha o navegador e apaga a sessão salva, permitindo conectar outro número."""
        with self._lock:
            worker_alive = self._worker is not None and self._worker.is_alive()
            self._connected = False
        if worker_alive:
            self._queue.put(("stop", True, on_done))
        else:
            self._clear_session_dir()
            if on_done:
                on_done()

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
            page.wait_for_selector(_SEL_CHAT_LIST, timeout=120_000)
            with self._lock:
                self._connected = True
            on_ready()
        except Exception as e:
            on_error(str(e))
            return

        clear_session = False
        on_done: Optional[Callable] = None

        while True:
            try:
                task = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            if task[0] == "stop":
                clear_session = len(task) > 1 and bool(task[1])
                on_done = task[2] if len(task) > 2 else None
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
        if clear_session:
            self._clear_session_dir()
        if on_done:
            on_done()

    @staticmethod
    def _clear_session_dir() -> None:
        # O Chromium pode segurar arquivos por alguns instantes após fechar
        for _ in range(5):
            try:
                shutil.rmtree(SESSION_DIR)
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(0.5)
        logger.warning("Não foi possível remover a pasta de sessão: %s", SESSION_DIR)

    @staticmethod
    def _wait_chat_or_invalid(page: Page, timeout_s: float = 20.0):
        """Espera abrir o chat (retorna o campo de composição) ou detecta número
        inválido (levanta erro). O que ocorrer primeiro decide o resultado."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if page.query_selector(_SEL_INVALID_POPUP):
                raise RuntimeError("Número não encontrado no WhatsApp.")
            msg_box = page.query_selector(_SEL_COMPOSE_BOX)
            if msg_box:
                return msg_box
            time.sleep(0.3)
        # Estourou o tempo: última checagem do popup antes de reportar timeout
        if page.query_selector(_SEL_INVALID_POPUP):
            raise RuntimeError("Número não encontrado no WhatsApp.")
        raise RuntimeError("Não foi possível abrir a conversa (WhatsApp Web lento ou número inválido).")

    def _do_send(self, page: Page, phone: str, message: str) -> None:
        phone_clean = to_wa_phone(phone)

        try:
            page.goto(
                f"https://web.whatsapp.com/send?phone={phone_clean}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
        except Exception:
            raise RuntimeError("Timeout ao navegar para o chat (conexão lenta ou WhatsApp Web travado).")

        # Aguarda o que aparecer primeiro: o campo de composição (número válido)
        # ou o popup de número inválido. Um intervalo fixo era frágil — em
        # conexão lenta o popup surgia depois da checagem única e o número
        # inválido escapava, virando um timeout genérico do campo de mensagem.
        msg_box = self._wait_chat_or_invalid(page, timeout_s=20.0)

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
