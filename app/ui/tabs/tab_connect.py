import customtkinter as ctk
from app.core.whatsapp import WhatsAppBot


class TabConnect(ctk.CTkFrame):
    def __init__(self, master, bot: WhatsAppBot):
        super().__init__(master, fg_color="transparent")
        self._bot = bot
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

    def _on_error(self, msg: str):
        self.after(0, lambda: self._status_dot.configure(text="● Erro na conexão", text_color="red"))
        self.after(0, lambda: self._btn_connect.configure(state="normal", text="Tentar novamente"))
        self.after(0, lambda: self._lbl_info.configure(
            text=f"Erro: {msg}\n\nFeche o navegador caso ainda esteja aberto e tente novamente."
        ))

    def is_connected(self) -> bool:
        return self._bot.is_connected()
