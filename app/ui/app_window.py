import json
import os
import re
import threading
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Tuple
from app.core import updater
from app.core.resources import icon_path
from app.core.excel_reader import ExcelData
from app.core.whatsapp import WhatsAppBot
from app.core.profile_store import ProfileStore
from app.version import __version__
from app.ui import theme
from app.ui.tabs.tab_excel import TabExcel
from app.ui.tabs.tab_message import TabMessage
from app.ui.tabs.tab_connect import TabConnect
from app.ui.tabs.tab_send import TabSend

_UI_STATE_PATH = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "ui_state.json")


class AppWindow(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        super().__init__()

        self.title(f"Saffar — Automação WhatsApp  v{__version__}")
        # 660 de altura cabe (com barra de título e taskbar) em telas de 768px
        self.geometry(self._restore_geometry() or "900x660")
        self.minsize(780, 600)
        self.resizable(True, True)
        self._apply_icon()

        self._data: Optional[ExcelData] = None
        self._excel_path: Optional[str] = None
        self._message: str = ""
        self._bot = WhatsAppBot()
        self.profile_store = ProfileStore()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-o>", lambda _e: self._tab_excel._open_file())
        # Espera a janela abrir antes de checar atualização (não bloqueia o uso)
        self.after(1500, self._check_updates_async)
        self.after(1000, self._poll_status)

    def _build(self):
        # Rodapé com status global (visível em qualquer aba)
        footer = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=("gray86", "gray14"))
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        self._lbl_conn = ctk.CTkLabel(
            footer, text="● Desconectado", text_color=theme.RED_ERR, font=ctk.CTkFont(size=12)
        )
        self._lbl_conn.pack(side="left", padx=(16, 14))
        self._lbl_sel = ctk.CTkLabel(
            footer, text="Nenhum contato carregado", text_color="gray", font=ctk.CTkFont(size=12)
        )
        self._lbl_sel.pack(side="left")
        ctk.CTkLabel(
            footer, text=f"v{__version__}", text_color="gray", font=ctk.CTkFont(size=12)
        ).pack(side="right", padx=16)

        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=16, pady=(10, 8))

        for name in ["Contatos", "Mensagem", "WhatsApp", "Envio"]:
            self._tabs.add(name)

        self._tab_excel = TabExcel(self._tabs.tab("Contatos"), app=self, on_loaded=self._on_excel_loaded)
        self.tab_excel = self._tab_excel
        self._tab_excel.pack(fill="both", expand=True)

        self._tab_message = TabMessage(
            self._tabs.tab("Mensagem"),
            on_message_change=self._on_message_change,
            profile_store=self.profile_store,
        )
        self._tab_message.pack(fill="both", expand=True)

        self._tab_send = TabSend(
            self._tabs.tab("Envio"),
            bot=self._bot,
            get_data=self._get_data,
            get_message=self._tab_message.get_message,
            app=self,
        )
        self._tab_send.pack(fill="both", expand=True)

        self._tab_connect = TabConnect(
            self._tabs.tab("WhatsApp"),
            bot=self._bot,
            is_sending=self._tab_send.is_sending,
        )
        self._tab_connect.pack(fill="both", expand=True)

    def _poll_status(self):
        connected = self._bot.is_connected()
        self._lbl_conn.configure(
            text="● Conectado" if connected else "● Desconectado",
            text_color=theme.GREEN_OK if connected else theme.RED_ERR,
        )
        total = len(self._tab_excel.contact_vars)
        if total:
            n = sum(1 for v in self._tab_excel.contact_vars.values() if v.get())
            self._lbl_sel.configure(text=f"{n} de {total} contatos selecionados")
        else:
            self._lbl_sel.configure(text="Nenhum contato carregado")
        self.after(1000, self._poll_status)

    def _on_excel_loaded(self, data: ExcelData, path: str):
        self._data = data
        self._excel_path = path
        self._tab_message.set_columns(data.columns, data.rows)

    def _on_message_change(self, message: str):
        self._message = message

    def _get_data(self) -> Tuple[Optional[ExcelData], Optional[str]]:
        return self._data, self._excel_path

    def _restore_geometry(self) -> Optional[str]:
        """Recupera tamanho/posição da última sessão, se ainda couber na tela."""
        try:
            with open(_UI_STATE_PATH, encoding="utf-8") as f:
                geo = str(json.load(f).get("geometry", ""))
            m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", geo)
            if not m:
                return None
            w, h, x, y = map(int, m.groups())
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if w < 700 or h < 550 or x < -50 or y < -50 or x > sw - 200 or y > sh - 200:
                return None
            return geo
        except Exception:
            return None

    def _save_geometry(self):
        try:
            os.makedirs(os.path.dirname(_UI_STATE_PATH), exist_ok=True)
            with open(_UI_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump({"geometry": self.geometry()}, f)
        except OSError:
            pass

    def _apply_icon(self):
        path = icon_path()
        if not path:
            return
        try:
            self.iconbitmap(path)
            # O CustomTkinter aplica o ícone padrão dele com atraso (~200ms)
            # e sobrescreveria o nosso; reaplica depois
            self.after(400, lambda: self.iconbitmap(path))
        except Exception:
            pass  # ícone é cosmético: nunca impede o app de abrir

    # ------------------------------------------------------------------
    # Atualização automática
    # ------------------------------------------------------------------

    @staticmethod
    def _updater_log(msg: str):
        """Registra o resultado da verificação para diagnóstico em campo."""
        try:
            path = os.path.join(os.environ.get("APPDATA", "."), "Saffar", "logs", "updater.log")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
        except OSError:
            pass

    def _check_updates_async(self):
        # A thread só grava o resultado; quem toca na UI é o polling via after()
        # na thread principal — after() disparado de outra thread é instável
        # no app empacotado
        result = {"info": None, "done": False}

        def work():
            try:
                result["info"] = updater.check_for_update()
                self._updater_log(f"verificação ok: {result['info']}")
            except Exception as e:
                self._updater_log(f"falha na verificação: {e!r}")
            finally:
                result["done"] = True

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not result["done"]:
                self.after(500, poll)
                return
            if result["info"] is not None:
                self._prompt_update(result["info"])

        self.after(500, poll)

    def _prompt_update(self, info: "updater.UpdateInfo"):
        if not messagebox.askyesno(
            "Atualização disponível",
            f"Uma nova versão do Saffar está disponível: v{info.version}\n"
            f"(você está usando a v{__version__}).\n\n"
            "Atualizar agora? O aplicativo será reiniciado ao final do download.",
            parent=self,
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

        state = {"done": False, "new_exe": None, "error": None}

        def work():
            try:
                state["new_exe"] = updater.download_update(info)
            except Exception as e:
                state["error"] = e
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not state["done"]:
                self.after(300, poll)
                return
            if state["error"] is not None:
                self._updater_log(f"falha no download: {state['error']!r}")
                self._update_failed(win, state["error"])
            else:
                self._updater_log(f"download concluído: {state['new_exe']}")
                self._finish_update(win, state["new_exe"])

        self.after(300, poll)

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
        self._save_geometry()
        # Fecha o navegador e o banco antes de encerrar o processo — sem isso
        # o Chromium fica aberto órfão no Windows
        self._bot.shutdown(timeout=3)
        self.profile_store.close()
        self.destroy()
