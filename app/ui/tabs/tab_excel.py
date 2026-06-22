import re
import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable, List, Optional

import customtkinter as ctk

from app.core.excel_reader import ExcelData, load_excel

if TYPE_CHECKING:
    from app.ui.app_window import AppWindow


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def _format_last_sent(iso: Optional[str]) -> str:
    if not iso:
        return "nunca"
    try:
        dt = datetime.fromisoformat(iso)
        # convert to local time if UTC-aware
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "nunca"


class TabExcel(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", on_loaded: Callable[[ExcelData, str], None]):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._on_loaded = on_loaded
        self._file_path: Optional[str] = None

        # public: keyed by normalized phone -> BooleanVar
        self.contact_vars: dict[str, tk.BooleanVar] = {}
        # normalized phone -> (name, raw_phone)
        self._contact_info: dict[str, tuple[str, str]] = {}

        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        ctk.CTkLabel(
            self,
            text="1. Carregar Planilha Excel",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(20, 8))
        ctk.CTkLabel(
            self,
            text="Selecione o arquivo .xlsx com os contatos.",
            text_color="gray",
        ).pack()

        self._btn_open = ctk.CTkButton(
            self, text="Selecionar arquivo Excel", command=self._open_file
        )
        self._btn_open.pack(pady=16)

        self._lbl_file = ctk.CTkLabel(self, text="Nenhum arquivo selecionado", text_color="gray")
        self._lbl_file.pack()

        ctk.CTkLabel(self, text="Colunas detectadas:", font=ctk.CTkFont(weight="bold")).pack(
            pady=(20, 4)
        )

        self._cols_frame = ctk.CTkScrollableFrame(self, height=80)
        self._cols_frame.pack(fill="x", padx=20)

        # Action buttons row
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.pack(fill="x", padx=20, pady=(16, 4))

        self._btn_select_all = ctk.CTkButton(
            self._btn_frame,
            text="Selecionar todos",
            width=160,
            command=self._select_all,
        )
        self._btn_select_all.pack(side="left", padx=(0, 8))

        self._btn_deselect_all = ctk.CTkButton(
            self._btn_frame,
            text="Desmarcar todos",
            width=160,
            command=self._deselect_all,
        )
        self._btn_deselect_all.pack(side="left")

        # Contacts scrollable list
        self._contacts_frame = ctk.CTkScrollableFrame(self, label_text="Contatos")
        self._contacts_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def _open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not path:
            return
        try:
            data = load_excel(path)
            self._file_path = path
            self._lbl_file.configure(text=path, text_color="white")
            self._show_columns(data)
            self._load_contacts(data)
            self._on_loaded(data, path)
        except Exception as e:
            messagebox.showerror("Erro ao abrir arquivo", str(e))

    def _show_columns(self, data: ExcelData):
        for w in self._cols_frame.winfo_children():
            w.destroy()
        for col in data.columns:
            ctk.CTkLabel(
                self._cols_frame,
                text=col,
                fg_color=("gray80", "gray30"),
                corner_radius=6,
                padx=8,
                pady=2,
            ).pack(side="left", padx=4, pady=4)

    # ------------------------------------------------------------------
    # Contact list
    # ------------------------------------------------------------------

    def _load_contacts(self, data: ExcelData):
        # Clear previous list
        for w in self._contacts_frame.winfo_children():
            w.destroy()
        self.contact_vars.clear()
        self._contact_info.clear()

        phone_col = data.phone_column
        # Try to detect a name column
        name_col = self._detect_name_column(data.columns)

        profile_store = self.app.profile_store

        # Header row
        header = ctk.CTkFrame(self._contacts_frame, fg_color=("gray75", "gray25"))
        header.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(header, text="", width=30).pack(side="left", padx=4)
        ctk.CTkLabel(header, text="Nome", width=200, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text="Telefone", width=160, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)
        ctk.CTkLabel(header, text="Último envio", width=160, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=4)

        for row in data.rows:
            raw_phone = str(row.get(phone_col, "")).strip() if phone_col else ""
            if not raw_phone:
                continue

            norm_phone = _normalize_phone(raw_phone)
            if not norm_phone:
                continue

            name = str(row.get(name_col, "")).strip() if name_col else ""

            # Upsert into profile store
            profile_store.upsert_contact(norm_phone, name)

            # Fetch last_sent_at
            last_sent_iso = profile_store.get_last_sent_at(norm_phone)
            last_sent_str = _format_last_sent(last_sent_iso)

            var = tk.BooleanVar(value=True)
            self.contact_vars[norm_phone] = var
            self._contact_info[norm_phone] = (name, raw_phone)

            row_frame = ctk.CTkFrame(self._contacts_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=1)

            cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=30)
            cb.pack(side="left", padx=4)

            ctk.CTkLabel(row_frame, text=name, width=200, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row_frame, text=raw_phone, width=160, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row_frame, text=last_sent_str, width=160, anchor="w").pack(side="left", padx=4)

    @staticmethod
    def _detect_name_column(columns: List[str]) -> Optional[str]:
        keywords = ["nome", "name", "cliente", "contato", "contact"]
        for col in columns:
            if any(kw in col.lower() for kw in keywords):
                return col
        return None

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select_all(self):
        for var in self.contact_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.contact_vars.values():
            var.set(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_phones(self) -> List[str]:
        """Return normalized phone numbers of all checked contacts."""
        return [phone for phone, var in self.contact_vars.items() if var.get()]

    def uncheck_contact(self, phone: str) -> None:
        """Uncheck a contact by normalized phone (called on successful send)."""
        norm = _normalize_phone(phone)
        if norm in self.contact_vars:
            self.contact_vars[norm].set(False)
