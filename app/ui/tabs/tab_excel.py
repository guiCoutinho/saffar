import re
import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

import customtkinter as ctk

from app.core.excel_reader import ExcelData, load_excel, preview_excel, _detect_phone_column

if TYPE_CHECKING:
    from app.ui.app_window import AppWindow


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def _split_phones(raw: str) -> List[str]:
    """Split a cell that may contain multiple phones separated by ; or ,"""
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p.strip()]


def _format_phone(norm: str) -> str:
    """Format a normalized (digits-only) Brazilian phone number."""
    if len(norm) == 13 and norm.startswith("55"):
        norm = norm[2:]
    if len(norm) == 11:
        return f"({norm[:2]}) {norm[2:7]}-{norm[7:]}"
    if len(norm) == 10:
        return f"({norm[:2]}) {norm[2:6]}-{norm[6:]}"
    return norm


def _is_valid_phone(norm: str) -> bool:
    """Brazilian phone: DDD + 8 or 9 digits (10 or 11 total), optionally prefixed with 55."""
    n = norm[2:] if norm.startswith("55") and len(norm) in (12, 13) else norm
    return len(n) in (10, 11) and n.isdigit()


def _truncate(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


# Column widths (pixels) — must match header and data rows
_COL_CB = 36
_COL_NAME = 220
_COL_PHONE = 170
_COL_SENT = 150


def _configure_row_grid(frame: ctk.CTkFrame) -> None:
    frame.columnconfigure(0, minsize=_COL_CB)
    frame.columnconfigure(1, minsize=_COL_NAME, weight=1)
    frame.columnconfigure(2, minsize=_COL_PHONE)
    frame.columnconfigure(3, minsize=_COL_SENT)


def _format_last_sent(iso: Optional[str]) -> str:
    if not iso:
        return "nunca"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "nunca"


# ---------------------------------------------------------------------------
# Import configuration dialog
# ---------------------------------------------------------------------------

class ExcelImportDialog(ctk.CTkToplevel):
    """Shows a preview of the Excel file and lets the user pick the header row
    and the phone column before the data is loaded into the contact list."""

    def __init__(self, master, file_path: str):
        super().__init__(master)
        self.title("Configurar importação")
        self.resizable(False, False)
        self.grab_set()

        self._file_path = file_path
        self._raw_rows: List[List[str]] = []
        self.result: Optional[Tuple[int, str]] = None  # (header_row_0indexed, phone_col_name)

        self._header_var = tk.StringVar(value="1")
        self._phone_var = tk.StringVar(value="")
        self._columns: List[str] = []

        self._build()
        self._load_preview()
        self.after(50, self._center)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self):
        pad = {"padx": 16, "pady": 6}

        ctk.CTkLabel(
            self,
            text="Pré-visualização das primeiras linhas:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", **pad)

        # Preview table inside a scrollable frame
        self._preview_outer = ctk.CTkFrame(self)
        self._preview_outer.pack(fill="both", padx=16, pady=(0, 8))
        self._preview_frame = ctk.CTkScrollableFrame(self._preview_outer, height=200, width=700)
        self._preview_frame.pack(fill="both")

        # Header row selector
        row_sel = ctk.CTkFrame(self, fg_color="transparent")
        row_sel.pack(fill="x", **pad)
        ctk.CTkLabel(row_sel, text="Linha do cabeçalho (número da linha):").pack(side="left")
        vcmd = (self.register(lambda v: v.isdigit() or v == ""), "%P")
        self._header_entry = ctk.CTkEntry(row_sel, textvariable=self._header_var, width=60, validate="key", validatecommand=vcmd)
        self._header_entry.pack(side="left", padx=8)
        ctk.CTkButton(row_sel, text="Aplicar", width=90, command=self._apply_header).pack(side="left")

        # Phone column selector
        phone_sel = ctk.CTkFrame(self, fg_color="transparent")
        phone_sel.pack(fill="x", **pad)
        ctk.CTkLabel(phone_sel, text="Coluna do telefone/celular:").pack(side="left")
        self._phone_menu = ctk.CTkOptionMenu(phone_sel, variable=self._phone_var, values=["—"], width=220)
        self._phone_menu.pack(side="left", padx=8)

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkButton(btn_row, text="Cancelar", width=120, fg_color="gray40", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Importar", width=120, command=self._confirm).pack(side="right")

    def _load_preview(self):
        try:
            self._raw_rows = preview_excel(self._file_path, nrows=15)
        except Exception as e:
            messagebox.showerror("Erro", str(e), parent=self)
            self.destroy()
            return
        self._render_preview()
        self._apply_header(silent=True)

    def _render_preview(self, highlight_row: int = -1):
        for w in self._preview_frame.winfo_children():
            w.destroy()
        if not self._raw_rows:
            return
        max_cols = max(len(r) for r in self._raw_rows)
        for i, row in enumerate(self._raw_rows):
            is_header = (i == highlight_row)
            bg = ("gray65", "gray20") if is_header else ("gray80", "gray15")
            frame = ctk.CTkFrame(self._preview_frame, fg_color=bg, corner_radius=0)
            frame.pack(fill="x", pady=1)
            # Row number badge
            ctk.CTkLabel(frame, text=str(i + 1), width=28, anchor="e",
                         text_color=("gray40", "gray60"), font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
            for j in range(max_cols):
                val = row[j] if j < len(row) else ""
                font = ctk.CTkFont(weight="bold") if is_header else ctk.CTkFont(size=12)
                ctk.CTkLabel(frame, text=val[:30], width=110, anchor="w", font=font).pack(side="left", padx=2)

    def _apply_header(self, silent=False):
        raw = self._header_var.get().strip()
        if not raw.isdigit():
            if not silent:
                messagebox.showwarning("Atenção", "Informe um número de linha válido.", parent=self)
            return
        row_1based = int(raw)
        header_0 = row_1based - 1
        self._render_preview(highlight_row=header_0)
        # Derive column names from that row
        if 0 <= header_0 < len(self._raw_rows):
            self._columns = [str(c).strip() for c in self._raw_rows[header_0] if str(c).strip()]
        else:
            self._columns = []
        detected = _detect_phone_column(self._columns)
        values = self._columns if self._columns else ["—"]
        self._phone_menu.configure(values=values)
        self._phone_var.set(detected if detected else (values[0] if values else "—"))

    def _confirm(self):
        raw = self._header_var.get().strip()
        if not raw.isdigit():
            messagebox.showwarning("Atenção", "Informe um número de linha válido.", parent=self)
            return
        phone_col = self._phone_var.get()
        if not phone_col or phone_col == "—":
            messagebox.showwarning("Atenção", "Selecione a coluna do telefone.", parent=self)
            return
        self.result = (int(raw) - 1, phone_col)
        self.destroy()


# ---------------------------------------------------------------------------
# Edit phone dialog
# ---------------------------------------------------------------------------

class EditPhoneDialog(ctk.CTkToplevel):
    """Minimal dialog to enter or correct a contact's phone number."""

    def __init__(self, master, contact_name: str, current_phone: str = ""):
        super().__init__(master)
        self.title("Editar telefone")
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[str] = None  # normalized phone on success
        self._name = contact_name
        self._build(current_phone)
        self.after(50, self._center)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self, current_phone: str):
        pad = {"padx": 24, "pady": 8}
        label = self._name or "contato"
        ctk.CTkLabel(self, text=f"Telefone de: {label}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", **pad)
        ctk.CTkLabel(self, text="Informe o número com DDD (ex: 11999998888):", text_color="gray").pack(anchor="w", padx=24, pady=(0, 4))

        self._entry = ctk.CTkEntry(self, placeholder_text="DDD + número", width=280)
        self._entry.pack(padx=24, pady=(0, 4))
        if current_phone:
            self._entry.insert(0, current_phone)

        self._lbl_error = ctk.CTkLabel(self, text="", text_color="#E05252", height=18)
        self._lbl_error.pack(padx=24)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(8, 20))
        ctk.CTkButton(btn_row, text="Cancelar", width=120, fg_color="gray40", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Salvar", width=120, command=self._confirm).pack(side="right")

        self._entry.bind("<Return>", lambda _: self._confirm())
        self.after(100, self._entry.focus_set)

    def _confirm(self):
        raw = self._entry.get().strip()
        norm = re.sub(r"\D", "", raw)
        if not _is_valid_phone(norm):
            self._lbl_error.configure(text="Número inválido. Use DDD + 8 ou 9 dígitos.")
            return
        # Normalize: strip leading 55 country code
        if norm.startswith("55") and len(norm) in (12, 13):
            norm = norm[2:]
        self.result = norm
        self.destroy()


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------

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
        # all vars in display order (contact_vars may skip duplicates, this doesn't)
        self._all_vars: list[tk.BooleanVar] = []

        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(12, 4))

        ctk.CTkLabel(
            top,
            text="1. Carregar Planilha Excel",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        self._btn_open = ctk.CTkButton(
            top, text="Selecionar arquivo", width=160, command=self._open_file
        )
        self._btn_open.pack(side="right")

        self._lbl_file = ctk.CTkLabel(self, text="Nenhum arquivo selecionado", text_color="gray")
        self._lbl_file.pack()

        self._cols_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._cols_frame.pack(fill="x", padx=20, pady=(8, 0))

        # Action buttons row
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.pack(fill="x", padx=20, pady=(8, 4))

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

        dialog = ExcelImportDialog(self, path)
        self.wait_window(dialog)

        if dialog.result is None:
            return  # user cancelled

        header_row, phone_col = dialog.result
        try:
            data = load_excel(path, header_row=header_row, phone_column=phone_col)
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
        ctk.CTkLabel(
            self._cols_frame,
            text="Colunas:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=(0, 6))
        for col in data.columns:
            ctk.CTkLabel(
                self._cols_frame,
                text=col,
                fg_color=("gray80", "gray30"),
                corner_radius=6,
                padx=6,
                pady=2,
            ).pack(side="left", padx=3)

    # ------------------------------------------------------------------
    # Contact list
    # ------------------------------------------------------------------

    def _load_contacts(self, data: ExcelData):
        for w in self._contacts_frame.winfo_children():
            w.destroy()
        self.contact_vars.clear()
        self._contact_info.clear()
        self._all_vars.clear()

        phone_col = data.phone_column
        name_col = self._detect_name_column(data.columns)
        profile_store = self.app.profile_store

        # Header row
        header = ctk.CTkFrame(self._contacts_frame, fg_color=("gray75", "gray25"))
        header.pack(fill="x", pady=(0, 2))
        _configure_row_grid(header)
        ctk.CTkLabel(header, text="", width=_COL_CB).grid(row=0, column=0, padx=(4, 0))
        ctk.CTkLabel(header, text="Nome", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(header, text="Telefone", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(header, text="Último envio", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

        for row in data.rows:
            raw_phone_cell = str(row.get(phone_col, "")).strip() if phone_col else ""
            name = str(row.get(name_col, "")).strip() if name_col else ""

            if not raw_phone_cell:
                self._add_invalid_row(name, "", row)
                continue

            phone_parts = _split_phones(raw_phone_cell)
            for raw_phone in phone_parts:
                norm_phone = _normalize_phone(raw_phone)
                if not norm_phone or not _is_valid_phone(norm_phone):
                    self._add_invalid_row(name, raw_phone, row)
                    continue

                profile_store.upsert_contact(norm_phone, name)
                last_sent_iso = profile_store.get_last_sent_at(norm_phone)
                last_sent_str = _format_last_sent(last_sent_iso)

                var = tk.BooleanVar(value=True)
                self._all_vars.append(var)
                if norm_phone not in self.contact_vars:
                    self.contact_vars[norm_phone] = var
                self._contact_info[norm_phone] = (name, raw_phone)

                row_frame = ctk.CTkFrame(self._contacts_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=1)
                _configure_row_grid(row_frame)

                cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=_COL_CB)
                cb.grid(row=0, column=0, padx=(4, 0))

                ctk.CTkLabel(row_frame, text=_truncate(name, 32), anchor="w").grid(row=0, column=1, sticky="ew", padx=4, pady=2)
                ctk.CTkLabel(row_frame, text=_format_phone(norm_phone), anchor="w").grid(row=0, column=2, sticky="ew", padx=4, pady=2)
                ctk.CTkLabel(row_frame, text=last_sent_str, anchor="w").grid(row=0, column=3, sticky="ew", padx=4, pady=2)

    def _add_invalid_row(self, name: str, raw_phone: str, row_data: dict) -> None:
        """Render a contact with a missing or invalid phone (checkbox disabled, edit button shown)."""
        row_frame = ctk.CTkFrame(self._contacts_frame, fg_color=("gray93", "gray18"))
        row_frame.pack(fill="x", pady=1)
        _configure_row_grid(row_frame)

        var = tk.BooleanVar(value=False)
        cb = ctk.CTkCheckBox(row_frame, text="", variable=var, width=_COL_CB, state="disabled")
        cb.grid(row=0, column=0, padx=(4, 0))

        ctk.CTkLabel(row_frame, text=_truncate(name, 32), anchor="w", text_color="gray").grid(
            row=0, column=1, sticky="ew", padx=4, pady=2
        )

        phone_text = raw_phone if raw_phone else "sem telefone"
        phone_lbl = ctk.CTkLabel(row_frame, text=phone_text, anchor="w", text_color="#E05252")
        phone_lbl.grid(row=0, column=2, sticky="ew", padx=4, pady=2)

        edit_btn = ctk.CTkButton(
            row_frame,
            text="Editar",
            width=80,
            height=24,
            fg_color=("gray70", "gray35"),
            hover_color=("gray60", "gray45"),
        )
        edit_btn.grid(row=0, column=3, padx=4, pady=2, sticky="w")

        edit_btn.configure(
            command=lambda: self._open_edit_phone(name, raw_phone, cb, var, phone_lbl, edit_btn, row_frame)
        )

    def _open_edit_phone(
        self,
        name: str,
        raw_phone: str,
        cb: ctk.CTkCheckBox,
        var: tk.BooleanVar,
        phone_lbl: ctk.CTkLabel,
        edit_btn: ctk.CTkButton,
        row_frame: ctk.CTkFrame,
    ) -> None:
        dialog = EditPhoneDialog(self, name, raw_phone)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        norm_phone = dialog.result
        self.app.profile_store.upsert_contact(norm_phone, name)
        last_sent_iso = self.app.profile_store.get_last_sent_at(norm_phone)
        last_sent_str = _format_last_sent(last_sent_iso)

        # Update phone label
        phone_lbl.configure(text=_format_phone(norm_phone), text_color=("black", "white"))

        # Replace edit button with last_sent label
        edit_btn.grid_remove()
        ctk.CTkLabel(row_frame, text=last_sent_str, anchor="w").grid(
            row=0, column=3, sticky="ew", padx=4, pady=2
        )

        # Enable checkbox and register contact
        var.set(True)
        cb.configure(state="normal", variable=var)
        row_frame.configure(fg_color="transparent")

        self._all_vars.append(var)
        if norm_phone not in self.contact_vars:
            self.contact_vars[norm_phone] = var
        self._contact_info[norm_phone] = (name, norm_phone)

        # Dim the name label back to normal color
        for widget in row_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == _truncate(name, 32):
                widget.configure(text_color=("black", "white"))
                break

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
        for var in self._all_vars:
            var.set(True)

    def _deselect_all(self):
        for var in self._all_vars:
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
