import os
import threading
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Tuple
from app.core import updater
from app.core.excel_reader import ExcelData
from app.core.whatsapp import WhatsAppBot
from app.core.profile_store import ProfileStore
from app.version import __version__
from app.ui.tabs.tab_excel import TabExcel
from app.ui.tabs.tab_message import TabMessage
from app.ui.tabs.tab_connect import TabConnect
from app.ui.tabs.tab_send import TabSend


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"Saffar — Automação WhatsApp  v{__version__}")
        self.geometry("700x600")
        self.resizable(True, True)

        self._data: Optional[ExcelData] = None
        self._excel_path: Optional[str] = None
        self._message: str = ""
        self._bot = WhatsAppBot()
        self.profile_store = ProfileStore()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Espera a janela abrir antes de checar atualização (não bloqueia o uso)
        self.after(1500, self._check_updates_async)

    def _build(self):
        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=16, pady=16)

        for name in ["📂 Excel", "✏️ Mensagem", "📱 WhatsApp", "🚀 Enviar"]:
            self._tabs.add(name)

        self._tab_excel = TabExcel(self._tabs.tab("📂 Excel"), app=self, on_loaded=self._on_excel_loaded)
        self.tab_excel = self._tab_excel
        self._tab_excel.pack(fill="both", expand=True)

        self._tab_message = TabMessage(
            self._tabs.tab("✏️ Mensagem"),
            on_message_change=self._on_message_change,
            profile_store=self.profile_store,
        )
        self._tab_message.pack(fill="both", expand=True)

        self._tab_send = TabSend(
            self._tabs.tab("🚀 Enviar"),
            bot=self._bot,
            get_data=self._get_data,
            get_message=self._tab_message.get_message,
            app=self,
        )
        self._tab_send.pack(fill="both", expand=True)

        self._tab_connect = TabConnect(
            self._tabs.tab("📱 WhatsApp"),
            bot=self._bot,
            is_sending=self._tab_send.is_sending,
        )
        self._tab_connect.pack(fill="both", expand=True)

    def _on_excel_loaded(self, data: ExcelData, path: str):
        self._data = data
        self._excel_path = path
        first_row = data.rows[0] if data.rows else {}
        self._tab_message.set_columns(data.columns, first_row)

    def _on_message_change(self, message: str):
        self._message = message

    def _get_data(self) -> Tuple[Optional[ExcelData], Optional[str]]:
        return self._data, self._excel_path

    # ------------------------------------------------------------------
    # Atualização automática
    # ------------------------------------------------------------------

    def _check_updates_async(self):
        def work():
            try:
                info = updater.check_for_update()
            except Exception:
                return  # sem internet / API indisponível: segue normalmente
            if info is not None:
                self.after(0, lambda: self._prompt_update(info))

        threading.Thread(target=work, daemon=True).start()

    def _prompt_update(self, info: "updater.UpdateInfo"):
        if not messagebox.askyesno(
            "Atualização disponível",
            f"Uma nova versão do Saffar está disponível: v{info.version}\n"
            f"(você está usando a v{__version__}).\n\n"
            "Atualizar agora? O aplicativo será reiniciado ao final do download.",
        ):
            return

        win = ctk.CTkToplevel(self)
        win.title("Atualizando...")
        win.geometry("380x130")
        win.resizable(False, False)
        win.grab_set()
        ctk.CTkLabel(
            win, text=f"Baixando a versão {info.version}...",
            font=ctk.CTkFont(weight="bold"),
        ).pack(pady=(24, 8))
        bar = ctk.CTkProgressBar(win, mode="indeterminate", width=300)
        bar.pack()
        bar.start()

        def work():
            try:
                new_exe = updater.download_update(info)
            except Exception as e:
                self.after(0, lambda: self._update_failed(win, e))
                return
            self.after(0, lambda: self._finish_update(win, new_exe))

        threading.Thread(target=work, daemon=True).start()

    def _update_failed(self, win, error: Exception):
        win.destroy()
        messagebox.showerror(
            "Atualização",
            f"Não foi possível baixar a atualização:\n{error}\n\n"
            f"Você pode baixar manualmente em:\n{updater.RELEASES_URL}",
        )

    def _finish_update(self, win, new_exe: str):
        win.destroy()
        try:
            updater.apply_update_and_restart(new_exe)
        except Exception as e:
            self._update_failed_cleanup(new_exe)
            messagebox.showerror(
                "Atualização",
                f"Não foi possível aplicar a atualização:\n{e}\n\n"
                f"Você pode baixar manualmente em:\n{updater.RELEASES_URL}",
            )
            return
        self._bot.shutdown(timeout=3)
        self.profile_store.close()
        self.destroy()

    @staticmethod
    def _update_failed_cleanup(new_exe: str):
        try:
            os.remove(new_exe)
        except OSError:
            pass

    def _on_close(self):
        if self._tab_send.is_sending() and not messagebox.askyesno(
            "Sair",
            "Há envios em andamento. Sair agora interrompe a campanha.\nDeseja realmente sair?",
        ):
            return
        # Fecha o navegador e o banco antes de encerrar o processo — sem isso
        # o Chromium fica aberto órfão no Windows
        self._bot.shutdown(timeout=3)
        self.profile_store.close()
        self.destroy()
