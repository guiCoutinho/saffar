import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Callable, List, Optional, TYPE_CHECKING

import customtkinter as ctk

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
        self._first_row: dict = {}
        self._build()
        self._refresh_template_list()

    def _build(self):
        ctk.CTkLabel(self, text="2. Compor Mensagem", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(
            self,
            text="Use os botões abaixo para inserir campos da planilha na mensagem.",
            text_color="gray",
        ).pack()

        ctk.CTkLabel(self, text="Campos disponíveis:", font=ctk.CTkFont(weight="bold")).pack(pady=(16, 4))

        self._placeholders_frame = ctk.CTkScrollableFrame(self, height=60, orientation="horizontal")
        self._placeholders_frame.pack(fill="x", padx=20)

        # Template controls
        tpl_frame = ctk.CTkFrame(self, fg_color="transparent")
        tpl_frame.pack(fill="x", padx=20, pady=(12, 0))

        ctk.CTkLabel(tpl_frame, text="Templates:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 8))

        self._tpl_var = tk.StringVar(value=_PLACEHOLDER_TEMPLATE)
        self._tpl_menu = ctk.CTkOptionMenu(
            tpl_frame,
            variable=self._tpl_var,
            values=[_PLACEHOLDER_TEMPLATE],
            width=220,
            command=self._on_template_select,
        )
        self._tpl_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(tpl_frame, text="Salvar", width=80, command=self._save_template).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            tpl_frame, text="Excluir", width=80,
            fg_color=("gray50", "gray30"), hover_color=("gray40", "gray20"),
            command=self._delete_template,
        ).pack(side="left")

        ctk.CTkLabel(self, text="Mensagem:", font=ctk.CTkFont(weight="bold")).pack(pady=(12, 4), anchor="w", padx=20)

        self._textbox = ctk.CTkTextbox(self, height=200)
        self._textbox.pack(fill="both", expand=True, padx=20)
        self._textbox.bind("<KeyRelease>", self._on_key)

        self._lbl_preview_title = ctk.CTkLabel(self, text="Preview (primeira linha):", font=ctk.CTkFont(weight="bold"))
        self._lbl_preview_title.pack(pady=(12, 4), anchor="w", padx=20)

        self._lbl_preview = ctk.CTkLabel(self, text="—", wraplength=500, justify="left", text_color="gray")
        self._lbl_preview.pack(anchor="w", padx=20, pady=(0, 20))

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

    def set_columns(self, columns: List[str], first_row: dict):
        for w in self._placeholders_frame.winfo_children():
            w.destroy()
        self._first_row = first_row
        for col in columns:
            btn = ctk.CTkButton(
                self._placeholders_frame,
                text=col,
                width=80,
                command=lambda c=col: self._insert_placeholder(c),
            )
            btn.pack(side="left", padx=4, pady=4)

    def _insert_placeholder(self, col: str):
        self._textbox.insert("insert", f"{{{{{col}}}}}")
        self._textbox.focus()
        self._notify()

    def _on_key(self, _event):
        self._notify()

    def _notify(self):
        msg = self.get_message()
        self._on_message_change(msg)
        self._update_preview(msg)

    def _update_preview(self, template: str):
        if not self._first_row:
            return
        preview = template
        for key, value in self._first_row.items():
            preview = preview.replace(f"{{{{{key}}}}}", str(value))
        self._lbl_preview.configure(text=preview or "—")

    def get_message(self) -> str:
        return self._textbox.get("1.0", "end-1c")
