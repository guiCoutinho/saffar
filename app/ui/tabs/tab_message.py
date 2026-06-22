import customtkinter as ctk
from typing import Callable, List


class TabMessage(ctk.CTkFrame):
    def __init__(self, master, on_message_change: Callable[[str], None]):
        super().__init__(master, fg_color="transparent")
        self._on_message_change = on_message_change
        self._build()

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

        ctk.CTkLabel(self, text="Mensagem:", font=ctk.CTkFont(weight="bold")).pack(pady=(16, 4), anchor="w", padx=20)

        self._textbox = ctk.CTkTextbox(self, height=200)
        self._textbox.pack(fill="both", expand=True, padx=20)
        self._textbox.bind("<KeyRelease>", self._on_key)

        self._lbl_preview_title = ctk.CTkLabel(self, text="Preview (primeira linha):", font=ctk.CTkFont(weight="bold"))
        self._lbl_preview_title.pack(pady=(12, 4), anchor="w", padx=20)

        self._lbl_preview = ctk.CTkLabel(self, text="—", wraplength=500, justify="left", text_color="gray")
        self._lbl_preview.pack(anchor="w", padx=20, pady=(0, 20))

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
        if not hasattr(self, "_first_row") or not self._first_row:
            return
        preview = template
        for key, value in self._first_row.items():
            preview = preview.replace(f"{{{{{key}}}}}", str(value))
        self._lbl_preview.configure(text=preview or "—")

    def get_message(self) -> str:
        return self._textbox.get("1.0", "end-1c")
