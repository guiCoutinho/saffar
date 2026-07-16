import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Callable, List, TYPE_CHECKING

import customtkinter as ctk

from app.ui import theme

if TYPE_CHECKING:
    from app.core.profile_store import ProfileStore

_PLACEHOLDER_TEMPLATE = "— selecione um template —"


class TabMessage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_message_change: Callable[[str], None],
        profile_store: "ProfileStore",
    ):
        super().__init__(master, fg_color="transparent")
        self._on_message_change = on_message_change
        self._store = profile_store
        self._rows: List[dict] = []
        self._preview_index = 0
        self._build()
        self._refresh_template_list()

    def _build(self):
        pad = 20

        ctk.CTkLabel(
            self,
            text="Campos da planilha (clique para inserir na mensagem):",
            text_color="gray",
        ).pack(anchor="w", padx=pad, pady=(14, 2))

        self._placeholders_frame = ctk.CTkScrollableFrame(self, height=44, orientation="horizontal", fg_color="transparent")
        self._placeholders_frame.pack(fill="x", padx=pad)

        # Templates
        tpl_frame = ctk.CTkFrame(self, fg_color="transparent")
        tpl_frame.pack(fill="x", padx=pad, pady=(10, 0))

        ctk.CTkLabel(tpl_frame, text="Templates:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 8))

        self._tpl_var = tk.StringVar(value=_PLACEHOLDER_TEMPLATE)
        self._tpl_menu = ctk.CTkOptionMenu(
            tpl_frame,
            variable=self._tpl_var,
            values=[_PLACEHOLDER_TEMPLATE],
            width=230,
            command=self._on_template_select,
        )
        self._tpl_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(tpl_frame, text="Salvar", width=80, command=self._save_template, **theme.secondary()).pack(side="left", padx=(0, 4))
        ctk.CTkButton(tpl_frame, text="Excluir", width=80, command=self._delete_template, **theme.danger()).pack(side="left")

        # Mensagem + contador de caracteres
        msg_header = ctk.CTkFrame(self, fg_color="transparent")
        msg_header.pack(fill="x", padx=pad, pady=(12, 4))
        ctk.CTkLabel(msg_header, text="Mensagem:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self._lbl_count = ctk.CTkLabel(msg_header, text="0 caracteres", text_color="gray", font=ctk.CTkFont(size=12))
        self._lbl_count.pack(side="right")

        self._textbox = ctk.CTkTextbox(self, height=120)
        self._textbox.pack(fill="both", expand=True, padx=pad)
        self._textbox.bind("<KeyRelease>", self._on_key)

        # Painel de preview com navegação entre contatos
        preview = ctk.CTkFrame(self, fg_color=("gray88", "gray16"), corner_radius=8)
        preview.pack(fill="x", padx=pad, pady=(10, 16))

        prev_header = ctk.CTkFrame(preview, fg_color="transparent")
        prev_header.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(prev_header, text="Preview", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(side="left")

        self._btn_next = ctk.CTkButton(
            prev_header, text="›", width=26, height=22, command=lambda: self._nav_preview(1),
            **theme.secondary(),
        )
        self._btn_next.pack(side="right")
        self._lbl_prev_pos = ctk.CTkLabel(prev_header, text="—", text_color="gray", font=ctk.CTkFont(size=12))
        self._lbl_prev_pos.pack(side="right", padx=8)
        self._btn_prev = ctk.CTkButton(
            prev_header, text="‹", width=26, height=22, command=lambda: self._nav_preview(-1),
            **theme.secondary(),
        )
        self._btn_prev.pack(side="right")

        self._lbl_preview = ctk.CTkLabel(
            preview, text="Carregue uma planilha para ver o preview.",
            wraplength=640, justify="left", anchor="w", text_color=("gray25", "gray75"),
        )
        self._lbl_preview.pack(fill="x", padx=12, pady=(4, 10))

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def _refresh_template_list(self):
        templates = self._store.list_templates()
        names = [t[0] for t in templates]
        values = [_PLACEHOLDER_TEMPLATE] + names
        self._tpl_menu.configure(values=values)
        current = self._tpl_var.get()
        if current not in values:
            self._tpl_var.set(_PLACEHOLDER_TEMPLATE)

    def _on_template_select(self, name: str):
        if name == _PLACEHOLDER_TEMPLATE:
            return
        templates = dict(self._store.list_templates())
        body = templates.get(name, "")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", body)
        self._notify()

    def _save_template(self):
        body = self.get_message().strip()
        if not body:
            messagebox.showwarning("Atenção", "Escreva uma mensagem antes de salvar o template.", parent=self)
            return
        current = self._tpl_var.get()
        default_name = current if current != _PLACEHOLDER_TEMPLATE else ""
        name = simpledialog.askstring(
            "Salvar template",
            "Nome do template:",
            initialvalue=default_name,
            parent=self,
        )
        if not name or not name.strip():
            return
        self._store.save_template(name.strip(), body)
        self._refresh_template_list()
        self._tpl_var.set(name.strip())

    def _delete_template(self):
        name = self._tpl_var.get()
        if name == _PLACEHOLDER_TEMPLATE:
            messagebox.showwarning("Atenção", "Selecione um template para excluir.", parent=self)
            return
        if not messagebox.askyesno("Confirmar", f'Excluir o template "{name}"?', parent=self):
            return
        self._store.delete_template(name)
        self._refresh_template_list()

    # ------------------------------------------------------------------
    # Placeholders & message
    # ------------------------------------------------------------------

    def set_columns(self, columns: List[str], rows: List[dict]):
        for w in self._placeholders_frame.winfo_children():
            w.destroy()
        self._rows = rows or []
        self._preview_index = 0
        for col in columns:
            btn = ctk.CTkButton(
                self._placeholders_frame,
                text=col,
                width=80,
                height=26,
                command=lambda c=col: self._insert_placeholder(c),
                **theme.secondary(),
            )
            btn.pack(side="left", padx=4, pady=2)
        self._notify()

    def _insert_placeholder(self, col: str):
        self._textbox.insert("insert", f"{{{{{col}}}}}")
        self._textbox.focus()
        self._notify()

    def _on_key(self, _event):
        self._notify()

    def _notify(self):
        msg = self.get_message()
        self._on_message_change(msg)
        self._lbl_count.configure(text=f"{len(msg)} caracteres")
        self._update_preview(msg)

    def _nav_preview(self, delta: int):
        if not self._rows:
            return
        self._preview_index = (self._preview_index + delta) % len(self._rows)
        self._update_preview(self.get_message())

    def _update_preview(self, template: str):
        if not self._rows:
            self._lbl_prev_pos.configure(text="—")
            self._lbl_preview.configure(text="Carregue uma planilha para ver o preview.")
            return
        row = self._rows[self._preview_index]
        preview = template
        for key, value in row.items():
            preview = preview.replace(f"{{{{{key}}}}}", str(value))
        self._lbl_prev_pos.configure(text=f"{self._preview_index + 1} / {len(self._rows)}")
        self._lbl_preview.configure(text=preview or "—")

    def get_message(self) -> str:
        return self._textbox.get("1.0", "end-1c")
