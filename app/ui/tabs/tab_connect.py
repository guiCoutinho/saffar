import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from app.core.whatsapp import WhatsAppBot


class TabConnect(ctk.CTkFrame):
    def __init__(self, master, bot: WhatsAppBot, is_sending: Optional[Callable[[], bool]] = None):
        super().__init__(master, fg_color="transparent")
        self._bot = bot
        self._is_sending = is_sending
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="3. Conectar WhatsApp", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 8))
        ctk.CTkLabel(
            self,
            text="Clique no botão abaixo para abrir o WhatsApp Web.\nNa primeira vez, escaneie o QR Code com seu celular.\nNas próximas vezes, o login será automático.",
            text_color="gray",
            justify="center",
        ).pack(pady=(0, 20))

        self._btn_connect = ctk.CTkButton(
            self,
            text="Conectar WhatsApp",
            width=200,
            height=44,
            command=self._connect,
        )
        self._btn_connect.pack()

        # Só aparece quando há uma sessão conectada
        self._btn_disconnect = ctk.CTkButton(
            self,
            text="Desconectar / Trocar número",
            width=200,
            height=36,
            fg_color="gray30",
            hover_color="gray20",
            command=self._disconnect,
        )

        self._status_dot = ctk.CTkLabel(self, text="● Desconectado", text_color="red", font=ctk.CTkFont(size=13))
        self._status_dot.pack(pady=16)

        self._lbl_info = ctk.CTkLabel(self, text="", text_color="gray", wraplength=400, justify="center")
        self._lbl_info.pack()

    def _connect(self):
        self._btn_connect.configure(state="disabled", text="Abrindo navegador...")
        self._lbl_info.configure(
            text="Uma janela do navegador será aberta em segundo plano.\n"
                 "Procure por ela na barra de tarefas do Windows.\n"
                 "Escaneie o QR Code com seu celular se solicitado.\n"
                 "Aguarde — pode levar alguns segundos."
        )
        self._status_dot.configure(text="● Conectando...", text_color="orange")
        self._bot.launch(on_ready=self._on_ready, on_error=self._on_error)

    def _on_ready(self):
        self.after(0, lambda: self._status_dot.configure(text="● Conectado", text_color="green"))
        self.after(0, lambda: self._btn_connect.configure(text="WhatsApp conectado ✓", state="disabled"))
        self.after(0, lambda: self._lbl_info.configure(text="Pronto para enviar mensagens."))
        self.after(0, lambda: self._btn_disconnect.pack(pady=(12, 0), before=self._status_dot))

    def _on_error(self, msg: str):
        self.after(0, lambda: self._status_dot.configure(text="● Erro na conexão", text_color="red"))
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
        self._status_dot.configure(text="● Desconectando...", text_color="orange")
        self._lbl_info.configure(text="Fechando o navegador e removendo a sessão salva...")
        self._bot.disconnect(on_done=lambda: self.after(0, self._on_disconnected))

    def _on_disconnected(self):
        self._btn_disconnect.pack_forget()
        self._btn_disconnect.configure(state="normal", text="Desconectar / Trocar número")
        self._status_dot.configure(text="● Desconectado", text_color="red")
        self._btn_connect.configure(state="normal", text="Conectar WhatsApp")
        self._lbl_info.configure(
            text="Sessão removida. Clique em Conectar e escaneie o QR Code\ncom o número que deseja usar para os envios."
        )

    def is_connected(self) -> bool:
        return self._bot.is_connected()
