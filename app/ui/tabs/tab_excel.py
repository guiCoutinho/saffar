import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

import customtkinter as ctk

from app.core.excel_reader import (
    ExcelData, UnidadeInadimplente, load_excel, preview_excel,
    parse_inadimplentes, _detect_phone_column, _detect_name_column,
)
from app.core.phone_utils import (
    normalize_phone as _normalize_phone,
    split_phones as _split_phones,
)

if TYPE_CHECKING:
    from app.ui.app_window import AppWindow


def _format_phone(norm: str) -> str:
    """Format a normalized (digits-only) Brazilian phone number."""
    if len(norm) in (12, 13) and norm.startswith("55"):
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


# Column widths (pixels)
_COL_CB = 36
_COL_SENT = 150
_COL_DATA_MIN = 130


def _configure_dynamic_grid(frame: ctk.CTkFrame, n_data_cols: int) -> None:
    """Configure grid: col 0 = checkbox, cols 1..n = data, col n+1 = last-sent/action."""
    frame.columnconfigure(0, minsize=_COL_CB, weight=0)
    for i in range(n_data_cols):
        frame.columnconfigure(i + 1, minsize=_COL_DATA_MIN, weight=1)
    frame.columnconfigure(n_data_cols + 1, minsize=_COL_SENT, weight=0)


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
        self.result: Optional[Tuple[int, str, List[str]]] = None  # (header_row_0indexed, phone_col, display_cols)

        self._header_var = tk.StringVar(value="1")
        self._phone_var = tk.StringVar(value="")
        self._columns: List[str] = []
        self._col_vars: dict[str, tk.BooleanVar] = {}

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
        self._phone_menu = ctk.CTkOptionMenu(
            phone_sel, variable=self._phone_var, values=["—"], width=220,
            command=lambda _: self._rebuild_col_checkboxes(),
        )
        self._phone_menu.pack(side="left", padx=8)

        # Display columns selector
        ctk.CTkLabel(
            self, text="Colunas a exibir na lista de contatos:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=16, pady=(10, 2))
        self._cols_check_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray22"), corner_radius=8)
        self._cols_check_frame.pack(fill="x", padx=16, pady=(0, 8))

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
        if 0 <= header_0 < len(self._raw_rows):
            self._columns = [str(c).strip() for c in self._raw_rows[header_0] if str(c).strip()]
        else:
            self._columns = []
        detected = _detect_phone_column(self._columns)
        values = self._columns if self._columns else ["—"]
        self._phone_menu.configure(values=values)
        self._phone_var.set(detected if detected else (values[0] if values else "—"))
        self._rebuild_col_checkboxes()

    def _rebuild_col_checkboxes(self):
        for w in self._cols_check_frame.winfo_children():
            w.destroy()
        self._col_vars.clear()
        if not self._columns:
            ctk.CTkLabel(self._cols_check_frame, text="Nenhuma coluna detectada.", text_color="gray").pack(padx=12, pady=6)
            return

        phone_col = self._phone_var.get()
        name_col = _detect_name_column(self._columns)
        cols_per_row = 4
        for i, col in enumerate(self._columns):
            is_phone = col == phone_col
            default_on = is_phone or col == name_col
            var = tk.BooleanVar(value=default_on)
            self._col_vars[col] = var
            r, c = divmod(i, cols_per_row)
            cb = ctk.CTkCheckBox(
                self._cols_check_frame,
                text=_truncate(col, 18),
                variable=var,
                width=160,
            )
            if is_phone:
                cb.configure(state="disabled")
            cb.grid(row=r, column=c, padx=10, pady=4, sticky="w")

    def _confirm(self):
        raw = self._header_var.get().strip()
        if not raw.isdigit():
            messagebox.showwarning("Atenção", "Informe um número de linha válido.", parent=self)
            return
        phone_col = self._phone_var.get()
        if not phone_col or phone_col == "—":
            messagebox.showwarning("Atenção", "Selecione a coluna do telefone.", parent=self)
            return
        # Always include phone_col; add other checked columns in original order
        display_cols = [
            col for col in self._columns
            if col == phone_col or self._col_vars.get(col, tk.BooleanVar(value=False)).get()
        ]
        if not display_cols:
            display_cols = [phone_col]
        self.result = (int(raw) - 1, phone_col, display_cols)
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
        norm = _normalize_phone(raw)
        if not _is_valid_phone(norm):
            self._lbl_error.configure(text="Número inválido. Use DDD + 8 ou 9 dígitos.")
            return
        self.result = norm
        self.destroy()


# ---------------------------------------------------------------------------
# Add contact dialog
# ---------------------------------------------------------------------------

class AddContactDialog(ctk.CTkToplevel):
    """Dialog to manually add a single contact."""

    def __init__(self, master, display_cols: List[str], phone_col: Optional[str]):
        super().__init__(master)
        self.title("Adicionar contato")
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[Tuple[dict, str]] = None  # (row_dict, norm_phone)
        self._display_cols = display_cols
        self._phone_col = phone_col
        self._extra_phone = phone_col not in (display_cols or [])
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._build()
        self.after(50, self._center)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self):
        pad = {"padx": 24, "pady": 6}
        ctk.CTkLabel(
            self, text="Novo contato", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=24, pady=(16, 8))

        for col in self._display_cols:
            hint = " (ex: 11999998888)" if col == self._phone_col else ""
            ctk.CTkLabel(self, text=f"{col}{hint}:", anchor="w").pack(anchor="w", padx=24, pady=(4, 0))
            entry = ctk.CTkEntry(self, width=320)
            entry.pack(**pad)
            self._entries[col] = entry

        if self._extra_phone:
            ctk.CTkLabel(self, text="Telefone (ex: 11999998888):", anchor="w").pack(anchor="w", padx=24, pady=(4, 0))
            entry = ctk.CTkEntry(self, width=320, placeholder_text="DDD + número")
            entry.pack(**pad)
            self._entries["__phone__"] = entry

        self._lbl_error = ctk.CTkLabel(self, text="", text_color="#E05252", height=18)
        self._lbl_error.pack(padx=24)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(8, 20))
        ctk.CTkButton(
            btn_row, text="Cancelar", width=120, fg_color="gray40", command=self.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Adicionar", width=120, command=self._confirm).pack(side="right")

        self.bind("<Return>", lambda _: self._confirm())
        if self._entries:
            self.after(100, lambda: next(iter(self._entries.values())).focus_set())

    def _confirm(self):
        row = {col: entry.get().strip() for col, entry in self._entries.items()}

        # Validate that at least one non-phone field has a value
        non_phone = [v for col, v in row.items() if col not in (self._phone_col, "__phone__")]
        if non_phone and not any(non_phone):
            self._lbl_error.configure(text="Informe pelo menos o nome do contato.")
            return

        phone_key = self._phone_col if not self._extra_phone else "__phone__"
        raw = row.get(phone_key, "")
        norm = _normalize_phone(raw)
        if not _is_valid_phone(norm):
            self._lbl_error.configure(text="Número inválido. Use DDD + 8 ou 9 dígitos.")
            return

        if self._phone_col:
            row[self._phone_col] = norm
        row.pop("__phone__", None)

        self.result = (row, norm)
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
        # columns chosen for display (set at import time)
        self._display_cols: List[str] = []
        # last loaded ExcelData (needed for inadimplentes filter)
        self._excel_data: Optional[ExcelData] = None

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

        self._btn_inadimplentes = ctk.CTkButton(
            self._btn_frame,
            text="Filtrar Inadimplentes",
            width=180,
            fg_color=("#B5451B", "#8B3214"),
            hover_color=("#9A3A16", "#6E2710"),
            command=self._import_inadimplentes,
            state="disabled",
        )
        self._btn_inadimplentes.pack(side="left", padx=(16, 0))

        self._btn_add_contact = ctk.CTkButton(
            self._btn_frame,
            text="+ Adicionar contato",
            width=160,
            fg_color=("#1A6B35", "#14532A"),
            hover_color=("#155829", "#0F3D1E"),
            command=self._add_contact_manually,
        )
        self._btn_add_contact.pack(side="left", padx=(16, 0))

        self._btn_clear = ctk.CTkButton(
            self._btn_frame,
            text="Limpar lista",
            width=130,
            fg_color=("#8B1A1A", "#6B1212"),
            hover_color=("#6B1212", "#500E0E"),
            command=self._clear_contacts,
        )
        self._btn_clear.pack(side="right")

        self._btn_remove = ctk.CTkButton(
            self._btn_frame,
            text="Remover selecionados",
            width=180,
            fg_color=("#7A4A0A", "#5C3608"),
            hover_color=("#5C3608", "#402605"),
            command=self._remove_selected,
        )
        self._btn_remove.pack(side="right", padx=(0, 8))

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

        header_row, phone_col, display_cols = dialog.result
        try:
            data = load_excel(path, header_row=header_row, phone_column=phone_col)
            self._file_path = path
            self._display_cols = display_cols
            self._excel_data = data
            self._lbl_file.configure(text=path, text_color="white")
            self._show_columns(data)
            self._load_contacts(data)
            self._on_loaded(data, path)
            self._btn_inadimplentes.configure(state="normal")
        except Exception as e:
            messagebox.showerror("Erro ao abrir arquivo", str(e))

    def _import_inadimplentes(self):
        if self._excel_data is None:
            return
        path = filedialog.askopenfilename(
            title="Selecionar relatório de inadimplentes",
            filetypes=[("Excel files", "*.xlsx *.xls")],
        )
        if not path:
            return
        try:
            inadimplentes = parse_inadimplentes(path)
        except Exception as e:
            messagebox.showerror("Erro ao ler inadimplentes", str(e))
            return

        if not inadimplentes:
            messagebox.showwarning("Atenção", "Nenhuma unidade inadimplente encontrada no arquivo.")
            return

        # Detect the unit column in the contacts data
        unidade_col = next(
            (c for c in self._excel_data.columns if c.strip().lower() == "unidade"), None
        )
        if unidade_col is None:
            messagebox.showwarning(
                "Atenção",
                "A planilha de contatos não possui coluna 'Unidade'.\n"
                "O filtro de inadimplentes requer essa coluna.",
            )
            return

        # Build enriched rows: keep only units that appear in inadimplentes
        new_rows = []
        for row in self._excel_data.rows:
            unit = str(row.get(unidade_col, "")).strip()
            if unit in inadimplentes:
                info = inadimplentes[unit]
                enriched = dict(row)
                enriched["Meses em aberto"] = ", ".join(info.competencias) if info.competencias else "—"
                enriched["Total"] = info.total if info.total else "—"
                new_rows.append(enriched)

        if not new_rows:
            messagebox.showinfo(
                "Sem correspondência",
                "Nenhum contato da planilha corresponde às unidades inadimplentes.",
            )
            return

        # Add new columns to display list if not already there
        new_display_cols = list(self._display_cols)
        for col in ("Meses em aberto", "Total"):
            if col not in new_display_cols:
                new_display_cols.append(col)

        filtered_data = ExcelData(
            columns=self._excel_data.columns + [
                c for c in ("Meses em aberto", "Total") if c not in self._excel_data.columns
            ],
            rows=new_rows,
            phone_column=self._excel_data.phone_column,
        )
        self._display_cols = new_display_cols
        self._load_contacts(filtered_data)
        # Notifica o app para que tab_send e tab_message usem os dados filtrados/enriquecidos
        self._on_loaded(filtered_data, self._file_path)
        messagebox.showinfo(
            "Filtro aplicado",
            f"{len(new_rows)} contato(s) de {len(inadimplentes)} unidade(s) inadimplente(s) selecionado(s).",
        )

    def _add_contact_manually(self):
        if self._excel_data is None:
            display_cols = ["Nome", "Telefone"]
            phone_col = "Telefone"
        else:
            display_cols = self._display_cols or self._excel_data.columns[:2]
            phone_col = self._excel_data.phone_column

        dialog = AddContactDialog(self, display_cols, phone_col)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        row, norm_phone = dialog.result

        if self._excel_data is None:
            self._excel_data = ExcelData(
                columns=display_cols,
                rows=[row],
                phone_column=phone_col,
            )
            self._display_cols = display_cols
            self._show_columns(self._excel_data)
            self._btn_inadimplentes.configure(state="normal")
            self._on_loaded(self._excel_data, "")
        else:
            self._excel_data.rows.append(row)
            self._on_loaded(self._excel_data, self._file_path or "")

        self._load_contacts(self._excel_data)

    def _remove_selected(self):
        if self._excel_data is None:
            return
        selected = {phone for phone, var in self.contact_vars.items() if var.get()}
        if not selected:
            messagebox.showinfo("Atenção", "Nenhum contato selecionado para remover.")
            return
        if not messagebox.askyesno(
            "Remover contatos",
            f"Remover {len(selected)} contato(s) selecionado(s) da lista?",
        ):
            return
        phone_col = self._excel_data.phone_column
        new_rows = []
        for row in self._excel_data.rows:
            raw = str(row.get(phone_col, "")).strip() if phone_col else ""
            phones = [_normalize_phone(p) for p in _split_phones(raw)] if raw else []
            if not any(p in selected for p in phones):
                new_rows.append(row)
        self._excel_data.rows[:] = new_rows
        self._load_contacts(self._excel_data)
        self._on_loaded(self._excel_data, self._file_path or "")

    def _clear_contacts(self):
        if not messagebox.askyesno(
            "Limpar lista",
            "Tem certeza que deseja remover todos os contatos da lista?",
        ):
            return
        self._excel_data = None
        self._display_cols = []
        self._file_path = None
        self.contact_vars.clear()
        self._contact_info.clear()
        self._all_vars.clear()
        for w in self._contacts_frame.winfo_children():
            w.destroy()
        for w in self._cols_frame.winfo_children():
            w.destroy()
        self._lbl_file.configure(text="Nenhum arquivo selecionado", text_color="gray")
        self._btn_inadimplentes.configure(state="disabled")

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
        display_cols = self._display_cols or ([phone_col] if phone_col else data.columns[:1])
        n = len(display_cols)
        last_col = n + 1
        profile_store = self.app.profile_store

        # Single table frame — all rows grid into this, guaranteeing column alignment
        table = ctk.CTkFrame(self._contacts_frame, fg_color="transparent")
        table.pack(fill="both", expand=True)
        _configure_dynamic_grid(table, n)
        self._table = table

        # Header: grid row 0
        hdr_color = ("gray75", "gray25")
        _cb_placeholder = ctk.CTkLabel(table, text="", width=_COL_CB, fg_color=hdr_color)
        _cb_placeholder.grid(row=0, column=0, sticky="nsew", padx=(0, 0), pady=(0, 2))
        for i, col in enumerate(display_cols):
            ctk.CTkLabel(
                table, text=col, anchor="w",
                font=ctk.CTkFont(weight="bold"), fg_color=hdr_color,
            ).grid(row=0, column=i + 1, sticky="ew", padx=0, pady=(0, 2))
        ctk.CTkLabel(
            table, text="Último envio", anchor="w",
            font=ctk.CTkFont(weight="bold"), fg_color=hdr_color,
        ).grid(row=0, column=last_col, sticky="ew", padx=0, pady=(0, 2))

        # Batch DB: collect valid contacts, upsert all and fetch last_sent in 2 queries
        name_col = _detect_name_column(data.columns)
        contact_batch: list[tuple[str, str]] = []
        for row in data.rows:
            raw = str(row.get(phone_col, "")).strip() if phone_col else ""
            name = str(row.get(name_col or "", "")).strip()
            for raw_phone in (_split_phones(raw) if raw else []):
                norm = _normalize_phone(raw_phone)
                if norm and _is_valid_phone(norm):
                    contact_batch.append((norm, name))
        last_sent_map = profile_store.upsert_contacts_batch(contact_batch)

        grid_row = 1
        for row in data.rows:
            raw_phone_cell = str(row.get(phone_col, "")).strip() if phone_col else ""
            name = str(row.get(name_col or "", "")).strip()
            row_bg = ("gray88", "gray17") if grid_row % 2 == 0 else ("gray82", "gray20")

            if not raw_phone_cell:
                self._add_invalid_row(table, grid_row, name, "", row, display_cols, phone_col)
                grid_row += 1
                continue

            phone_parts = _split_phones(raw_phone_cell)
            for raw_phone in phone_parts:
                norm_phone = _normalize_phone(raw_phone)
                if not norm_phone or not _is_valid_phone(norm_phone):
                    self._add_invalid_row(table, grid_row, name, raw_phone, row, display_cols, phone_col)
                    grid_row += 1
                    continue

                last_sent_str = _format_last_sent(last_sent_map.get(norm_phone))

                # Telefone repetido reusa o mesmo var: marcar/desmarcar qualquer
                # linha do número reflete em todas e no envio (que é único por número)
                if norm_phone in self.contact_vars:
                    var = self.contact_vars[norm_phone]
                else:
                    var = tk.BooleanVar(value=True)
                    self.contact_vars[norm_phone] = var
                self._all_vars.append(var)
                self._contact_info[norm_phone] = (name, raw_phone)

                cb = ctk.CTkCheckBox(table, text="", variable=var, width=_COL_CB, bg_color=row_bg)
                cb.grid(row=grid_row, column=0, sticky="nsew", padx=(4, 0), pady=1)

                for i, col in enumerate(display_cols):
                    val = str(row.get(col, "")).strip()
                    if col == phone_col:
                        val = _format_phone(norm_phone)
                    ctk.CTkLabel(table, text=_truncate(val, 36), anchor="w", fg_color=row_bg).grid(
                        row=grid_row, column=i + 1, sticky="ew", padx=4, pady=1
                    )

                ctk.CTkLabel(table, text=last_sent_str, anchor="w", fg_color=row_bg).grid(
                    row=grid_row, column=last_col, sticky="ew", padx=4, pady=1
                )
                grid_row += 1

    def _add_invalid_row(
        self,
        table: ctk.CTkFrame,
        grid_row: int,
        name: str,
        raw_phone: str,
        row_data: dict,
        display_cols: List[str],
        phone_col: Optional[str],
    ) -> None:
        """Render a contact with missing/invalid phone directly into the shared table frame."""
        n = len(display_cols)
        last_col = n + 1
        row_bg = ("gray93", "gray18")

        var = tk.BooleanVar(value=False)
        cb = ctk.CTkCheckBox(table, text="", variable=var, width=_COL_CB, state="disabled", bg_color=row_bg)
        cb.grid(row=grid_row, column=0, sticky="nsew", padx=(4, 0), pady=1)

        phone_lbl: Optional[ctk.CTkLabel] = None
        for i, col in enumerate(display_cols):
            is_phone_col = col == phone_col
            if is_phone_col:
                phone_text = raw_phone if raw_phone else "sem telefone"
                phone_lbl = ctk.CTkLabel(table, text=phone_text, anchor="w", text_color="#E05252", fg_color=row_bg)
                phone_lbl.grid(row=grid_row, column=i + 1, sticky="ew", padx=4, pady=1)
            else:
                val = _truncate(str(row_data.get(col, "")).strip(), 36)
                ctk.CTkLabel(table, text=val, anchor="w", text_color="gray", fg_color=row_bg).grid(
                    row=grid_row, column=i + 1, sticky="ew", padx=4, pady=1
                )

        if phone_lbl is None:
            phone_text = raw_phone if raw_phone else "sem telefone"
            phone_lbl = ctk.CTkLabel(table, text=phone_text, anchor="w", text_color="#E05252", fg_color=row_bg)
            phone_lbl.grid(row=grid_row, column=n, sticky="ew", padx=4, pady=1)

        edit_btn = ctk.CTkButton(
            table, text="Editar", width=80, height=24,
            fg_color=("gray70", "gray35"), hover_color=("gray60", "gray45"),
        )
        edit_btn.grid(row=grid_row, column=last_col, padx=4, pady=1, sticky="w")
        edit_btn.configure(
            command=lambda: self._open_edit_phone(
                name, raw_phone, cb, var, phone_lbl, edit_btn, table, grid_row, last_col, row_bg,
                row_data, phone_col,
            )
        )

    @staticmethod
    def _update_row_phone(row_data: dict, phone_col: Optional[str], old_raw: str, new_norm: str) -> None:
        """Grava o telefone corrigido na linha da planilha em memória.

        Sem isso o envio (que filtra pelas células de _excel_data.rows) pularia
        o contato mesmo com o checkbox marcado. Se a célula tem vários números,
        substitui apenas a parte editada.
        """
        if not phone_col:
            return
        cell = str(row_data.get(phone_col, "")).strip()
        parts = _split_phones(cell)
        if old_raw and old_raw in parts:
            parts[parts.index(old_raw)] = new_norm
            row_data[phone_col] = "; ".join(parts)
        else:
            row_data[phone_col] = new_norm

    def _open_edit_phone(
        self,
        name: str,
        raw_phone: str,
        cb: ctk.CTkCheckBox,
        var: tk.BooleanVar,
        phone_lbl: ctk.CTkLabel,
        edit_btn: ctk.CTkButton,
        table: ctk.CTkFrame,
        grid_row: int,
        last_col: int,
        row_bg: tuple,
        row_data: dict,
        phone_col: Optional[str],
    ) -> None:
        dialog = EditPhoneDialog(self, name, raw_phone)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        norm_phone = dialog.result
        self._update_row_phone(row_data, phone_col, raw_phone, norm_phone)
        self.app.profile_store.upsert_contact(norm_phone, name)
        last_sent_iso = self.app.profile_store.get_last_sent_at(norm_phone)
        last_sent_str = _format_last_sent(last_sent_iso)

        # Update phone label
        phone_lbl.configure(text=_format_phone(norm_phone), text_color=("black", "white"))

        # Replace edit button with last_sent label
        edit_btn.grid_remove()
        ctk.CTkLabel(table, text=last_sent_str, anchor="w", fg_color=row_bg).grid(
            row=grid_row, column=last_col, sticky="ew", padx=4, pady=1
        )

        # Enable checkbox, update colors
        var.set(True)
        cb.configure(state="normal", variable=var)

        # Normalize the row background to the alternating color
        normal_bg = ("gray88", "gray17") if grid_row % 2 == 0 else ("gray82", "gray20")
        cb.configure(bg_color=normal_bg)
        phone_lbl.configure(fg_color=normal_bg)

        self._all_vars.append(var)
        if norm_phone not in self.contact_vars:
            self.contact_vars[norm_phone] = var
        self._contact_info[norm_phone] = (name, norm_phone)

        # Update all other labels in this grid row to normal color
        for widget in table.grid_slaves(row=grid_row):
            if isinstance(widget, ctk.CTkLabel):
                widget.configure(text_color=("black", "white"), fg_color=normal_bg)

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
