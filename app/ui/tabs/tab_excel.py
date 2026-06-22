import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Callable, Optional
from app.core.excel_reader import ExcelData, load_excel


class TabExcel(ctk.CTkFrame):
    def __init__(self, master, on_loaded: Callable[[ExcelData, str], None]):
        super().__init__(master, fg_color="transparent")
        self._on_loaded = on_loaded
        self._file_path: Optional[str] = None
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="1. Carregar Planilha Excel", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 8))
        ctk.CTkLabel(self, text="Selecione o arquivo .xlsx com os contatos.", text_color="gray").pack()

        self._btn_open = ctk.CTkButton(self, text="Selecionar arquivo Excel", command=self._open_file)
        self._btn_open.pack(pady=16)

        self._lbl_file = ctk.CTkLabel(self, text="Nenhum arquivo selecionado", text_color="gray")
        self._lbl_file.pack()

        ctk.CTkLabel(self, text="Colunas detectadas:", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 4))

        self._cols_frame = ctk.CTkScrollableFrame(self, height=80)
        self._cols_frame.pack(fill="x", padx=20)

        ctk.CTkLabel(self, text="Preview (primeiras 5 linhas):", font=ctk.CTkFont(weight="bold")).pack(pady=(16, 4))

        self._preview = ctk.CTkTextbox(self, height=120, state="disabled")
        self._preview.pack(fill="x", padx=20, pady=(0, 20))

    def _open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not path:
            return
        try:
            data = load_excel(path)
            self._file_path = path
            self._lbl_file.configure(text=path, text_color="white")
            self._show_columns(data)
            self._show_preview(data)
            self._on_loaded(data, path)
        except Exception as e:
            messagebox.showerror("Erro ao abrir arquivo", str(e))

    def _show_columns(self, data: ExcelData):
        for w in self._cols_frame.winfo_children():
            w.destroy()
        for col in data.columns:
            ctk.CTkLabel(self._cols_frame, text=col, fg_color=("gray80", "gray30"), corner_radius=6, padx=8, pady=2).pack(side="left", padx=4, pady=4)

    def _show_preview(self, data: ExcelData):
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        header = " | ".join(data.columns)
        self._preview.insert("end", header + "\n" + "-" * len(header) + "\n")
        for row in data.rows[:5]:
            line = " | ".join(str(row.get(c, "")) for c in data.columns)
            self._preview.insert("end", line + "\n")
        self._preview.configure(state="disabled")
