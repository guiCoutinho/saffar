import customtkinter as ctk
from typing import Optional, Tuple
from app.core.excel_reader import ExcelData
from app.core.whatsapp import WhatsAppBot
from app.core.profile_store import ProfileStore
from app.ui.tabs.tab_excel import TabExcel
from app.ui.tabs.tab_message import TabMessage
from app.ui.tabs.tab_connect import TabConnect
from app.ui.tabs.tab_send import TabSend


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Saffar — Automação WhatsApp")
        self.geometry("700x600")
        self.resizable(True, True)

        self._data: Optional[ExcelData] = None
        self._excel_path: Optional[str] = None
        self._message: str = ""
        self._bot = WhatsAppBot()
        self.profile_store = ProfileStore()

        self._build()

    def _build(self):
        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=16, pady=16)

        for name in ["📂 Excel", "✏️ Mensagem", "📱 WhatsApp", "🚀 Enviar"]:
            self._tabs.add(name)

        self._tab_excel = TabExcel(self._tabs.tab("📂 Excel"), app=self, on_loaded=self._on_excel_loaded)
        self.tab_excel = self._tab_excel
        self._tab_excel.pack(fill="both", expand=True)

        self._tab_message = TabMessage(self._tabs.tab("✏️ Mensagem"), on_message_change=self._on_message_change)
        self._tab_message.pack(fill="both", expand=True)

        self._tab_connect = TabConnect(self._tabs.tab("📱 WhatsApp"), bot=self._bot)
        self._tab_connect.pack(fill="both", expand=True)

        self._tab_send = TabSend(
            self._tabs.tab("🚀 Enviar"),
            bot=self._bot,
            get_data=self._get_data,
            get_message=self._tab_message.get_message,
            app=self,
        )
        self._tab_send.pack(fill="both", expand=True)

    def _on_excel_loaded(self, data: ExcelData, path: str):
        self._data = data
        self._excel_path = path
        first_row = data.rows[0] if data.rows else {}
        self._tab_message.set_columns(data.columns, first_row)

    def _on_message_change(self, message: str):
        self._message = message

    def _get_data(self) -> Tuple[Optional[ExcelData], Optional[str]]:
        return self._data, self._excel_path
