import os

import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from app.core.whatsapp import WhatsAppBot, SESSION_DIR
from app.ui import theme


class TabConnect(ctk.CTkFrame):
    def __init__(self, master, bot: WhatsAppBot, is_sending: Optional[Callable[[], bool]] = None):
        super().__init__(master, fg_color="transparent")
        self._bot = bot
        self._is_sending = is_sending
        self._build()

    def _build(self):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.45, anchor="center")

        self._status_dot = ctk.CTkLabel(
            box, text="● Desconectado", text_color=theme.RED_ERR,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._status_dot.pack(pady=(0, 20))

        self._btn_connect = ctk.CTkButton(
            box,
            text="Conectar WhatsApp",
            width=230,
            height=44,
            command=self._connect,
        )
        self._btn_connect.pack()

        # Só aparece quando há uma sessão conectada
        self._btn_disconnect = ctk.CTkButton(
            box,
            text="Desconectar / Trocar número",
            width=230,
            height=34,
            command=self._disconnect,
            **theme.secondary(),
        )

        if os.path.isdir(SESSION_DIR) and os.listdir(SESSION_DIR):
            hint = "Sessão salva encontrada — o login deve ser automático."
        else:
            hint = "Primeira conexão: tenha o celular em mãos\npara escanear o QR Code."
        self._lbl_info = ctk.CTkLabel(box, text=hint, text_color="gray", wraplength=420, justify="center")
        self._lbl_info.pack(pady=(20, 0))

    def _connect(self):
        self._btn_connect.configure(state="disabled", text="Abrindo navegador...")
        self._lbl_info.configure(
            text="Uma janela do navegador será aberta em segundo plano.\n"
                 "Procure por ela na barra de tarefas do Windows.\n"
                 "Escaneie o QR Code com seu celular se solicitado.\n"
                 "Aguarde — pode levar alguns segundos."
        )
        self._status_dot.configure(text="● Conectando...", text_color=theme.ORANGE_WARN)
        self._bot.launch(on_ready=self._on_ready, on_error=self._on_error)

    def _on_ready(self):
        self.after(0, lambda: self._status_dot.configure(text="● Conectado", text_color=theme.GREEN_OK))
        self.after(0, lambda: self._btn_connect.configure(text="WhatsApp conectado ✓", state="disabled"))
        self.after(0, lambda: self._lbl_info.configure(text="Pronto para enviar mensagens."))
        self.after(0, lambda: self._btn_disconnect.pack(pady=(10, 0), before=self._lbl_info))

    def _on_error(self, msg: str):
        self.after(0, lambda: self._status_dot.configure(text="● Erro na conexão", text_color=theme.RED_ERR))
        self.after(0, lambda: self._btn_connect.configure(state="normal", text="Tentar novamente"))
        self.after(0, lambda: self._lbl_info.configure(
            text=f"Erro: {msg}\n\nFeche o navegador caso ainda esteja aberto e tente novamente."
        ))

    def _disconnect(self):
        if self._is_sending is not None and self._is_sending():
            messagebox.showwarning(
                "Atenção",
                "Há envios em andamento. Aguarde a campanha terminar\nantes de desconectar o WhatsApp.",
            )
            return
        self._btn_disconnect.configure(state="disabled", text="Desconectando...")
        self._status_dot.configure(text="● Desconectando...", text_color=theme.ORANGE_WARN)
        self._lbl_info.configure(text="Fechando o navegador e removendo a sessão salva...")
        self._bot.disconnect(on_done=lambda: self.after(0, self._on_disconnected))

    def _on_disconnected(self):
        self._btn_disconnect.pack_forget()
        self._btn_disconnect.configure(state="normal", text="Desconectar / Trocar número")
        self._status_dot.configure(text="● Desconectado", text_color=theme.RED_ERR)
        self._btn_connect.configure(state="normal", text="Conectar WhatsApp")
        self._lbl_info.configure(
            text="Sessão removida. Clique em Conectar e escaneie o QR Code\ncom o número que deseja usar para os envios."
        )

    def is_connected(self) -> bool:
        return self._bot.is_connected()
