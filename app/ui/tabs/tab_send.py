import re
import time
import random
import threading
import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING, Callable, Optional, List, Dict

from app.core.excel_reader import ExcelData, render_message, _detect_name_column
from app.core.phone_utils import normalize_phone as _normalize_phone, split_phones
from app.core.whatsapp import WhatsAppBot
from app.core import logger

if TYPE_CHECKING:
    from app.ui.app_window import AppWindow


class TabSend(ctk.CTkFrame):
    def __init__(self, master, bot: WhatsAppBot, get_data: Callable, get_message: Callable[[], str], app: "AppWindow" = None):
        super().__init__(master, fg_color="transparent")
        self._bot = bot
        self._get_data = get_data
        self._get_message = get_message
        self._app = app
        self._log_path: Optional[str] = None
        self._failures: List[Dict] = []
        self._sending = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="4. Enviar Mensagens", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 8))

        interval_frame = ctk.CTkFrame(self, fg_color="transparent")
        interval_frame.pack(pady=8)

        ctk.CTkLabel(interval_frame, text="Intervalo entre envios:").grid(row=0, column=0, columnspan=4, pady=(0, 6))
        ctk.CTkLabel(interval_frame, text="Mínimo (s):").grid(row=1, column=0, padx=8)
        self._entry_min = ctk.CTkEntry(interval_frame, width=70)
        self._entry_min.insert(0, "10")
        self._entry_min.grid(row=1, column=1, padx=4)

        ctk.CTkLabel(interval_frame, text="Máximo (s):").grid(row=1, column=2, padx=8)
        self._entry_max = ctk.CTkEntry(interval_frame, width=70)
        self._entry_max.insert(0, "30")
        self._entry_max.grid(row=1, column=3, padx=4)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=16)

        self._btn_start = ctk.CTkButton(btn_row, text="Iniciar Envios", width=180, height=44, command=self._start)
        self._btn_start.pack(side="left", padx=8)

        self._btn_pause = ctk.CTkButton(btn_row, text="Pausar", width=120, height=44, command=self._toggle_pause, state="disabled", fg_color="gray40", hover_color="gray30")
        self._btn_pause.pack(side="left", padx=8)

        self._progress = ctk.CTkProgressBar(self, width=400)
        self._progress.set(0)
        self._progress.pack(pady=4)

        self._lbl_progress = ctk.CTkLabel(self, text="0 / 0 enviados")
        self._lbl_progress.pack()

        ctk.CTkLabel(self, text="Log em tempo real:", font=ctk.CTkFont(weight="bold")).pack(pady=(16, 4))
        self._log_box = ctk.CTkTextbox(self, height=160, state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _start(self):
        data, excel_path = self._get_data()
        message_template = self._get_message()

        if not data:
            messagebox.showwarning("Atenção", "Carregue uma planilha antes de enviar.")
            return
        if not message_template.strip():
            messagebox.showwarning("Atenção", "Escreva uma mensagem antes de enviar.")
            return
        if not self._bot.is_connected():
            messagebox.showwarning("Atenção", "Conecte o WhatsApp antes de enviar.")
            return
        if not data.phone_column:
            messagebox.showwarning("Atenção", "Nenhuma coluna de telefone detectada. Verifique o nome da coluna (ex: 'telefone', 'celular').")
            return

        try:
            min_s = float(self._entry_min.get())
            max_s = float(self._entry_max.get())
            if min_s >= max_s or min_s < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Intervalo inválido. O mínimo deve ser ≥ 1s e menor que o máximo.")
            return

        # Placeholders que não correspondem a nenhuma coluna iriam literalmente
        # na mensagem para o cliente — avisa antes de começar
        placeholders = set(re.findall(r"\{\{(.+?)\}\}", message_template))
        unknown = sorted(p for p in placeholders if p not in data.columns)
        if unknown and not messagebox.askyesno(
            "Atenção",
            "Os campos abaixo não existem na planilha e serão enviados como texto:\n\n"
            + "\n".join(f"{{{{{p}}}}}" for p in unknown)
            + "\n\nDeseja continuar mesmo assim?",
        ):
            return

        # Get selected phones from Excel tab
        selected_phones: set[str] = set()
        if self._app is not None:
            selected_phones = set(self._app.tab_excel.get_selected_phones())
        else:
            selected_phones = {
                _normalize_phone(p)
                for row in data.rows
                for p in split_phones(str(row.get(data.phone_column, "")))
            }

        if not selected_phones:
            messagebox.showwarning("Atenção", "Nenhum contato selecionado. Marque pelo menos um contato na aba Excel.")
            return

        self._log_path = logger.get_log_path(excel_path or "")
        logger.init_log(self._log_path)
        self._failures = []
        self._sending = True
        self._paused = False
        self._pause_event.set()
        self._btn_start.configure(state="disabled", text="Enviando...")
        self._btn_pause.configure(state="normal", text="Pausar", fg_color="#D97706", hover_color="#B45309")
        threading.Thread(target=self._run_sending, args=(data, message_template, min_s, max_s, selected_phones), daemon=True).start()

    def _run_sending(self, data: ExcelData, template: str, min_s: float, max_s: float, selected_phones: set):
        # Expande células com vários telefones (";" ou ",") em um alvo por número
        # e deduplica: cada número selecionado recebe a mensagem uma única vez
        name_col = _detect_name_column(data.columns)
        seen: set[str] = set()
        targets: list[tuple[dict, str]] = []
        for row in data.rows:
            raw_cell = str(row.get(data.phone_column, "")).strip()
            for part in split_phones(raw_cell):
                norm = _normalize_phone(part)
                if norm in selected_phones and norm not in seen:
                    seen.add(norm)
                    targets.append((row, norm))
        total = len(targets)

        for i, (row, norm_phone) in enumerate(targets):
            # Aguarda se estiver pausado (bloqueia até retomar)
            self._pause_event.wait()

            phone = norm_phone
            nome = str(row.get(name_col or "", "")).strip() or norm_phone
            message = render_message(template, row)

            self._log(f"[{i+1}/{total}] Enviando para {nome} ({phone})...")

            result = {"success": False, "error": None}
            done_event = threading.Event()

            def on_success(r=result, e=done_event):
                r["success"] = True
                e.set()

            def on_error(msg, r=result, e=done_event):
                r["error"] = msg
                e.set()

            # A digitação simula humano (40–110 ms/caractere): mensagens longas
            # levam mais que os 90s base e seriam marcadas como falsa falha
            send_timeout = 90 + 0.15 * len(message)

            self._bot.send_message(phone, message, on_success, on_error)
            done_event.wait(timeout=send_timeout)

            if result["success"]:
                self._log(f"  ✓ Enviado com sucesso.")
                logger.log_result(self._log_path, nome, phone, True)
                if self._app is not None:
                    self.after(0, lambda p=norm_phone: self._app.tab_excel.uncheck_contact(p))
                    self._app.profile_store.record_send(norm_phone, message, "success")
            else:
                if not done_event.is_set():
                    error_msg = f"Timeout: sem resposta em {send_timeout:.0f}s (WhatsApp Web pode estar travado)"
                else:
                    error_msg = result["error"] or "Erro desconhecido"
                self._log(f"  ✗ Falha: {error_msg}")
                logger.log_result(self._log_path, nome, phone, False, error_msg)
                self._failures.append({"nome": nome, "telefone": phone, "motivo": error_msg})
                if self._app is not None:
                    self._app.profile_store.record_send(norm_phone, message, "failure", error_msg)

            self._update_progress(i + 1, total)

            if i < total - 1:
                wait = random.uniform(min_s, max_s)
                self._log(f"  ⏳ Aguardando {wait:.1f}s...")
                time.sleep(wait)

        self.after(0, self._on_done)

    def is_sending(self) -> bool:
        return self._sending

    def _on_done(self):
        self._sending = False
        self._btn_start.configure(state="normal", text="Iniciar Envios")
        self._btn_pause.configure(state="disabled", text="Pausar", fg_color="gray40", hover_color="gray30")
        self._paused = False
        self._pause_event.set()
        if self._failures:
            self._show_failures()
        else:
            messagebox.showinfo("Concluído", f"Todos os envios foram realizados com sucesso!\nLog salvo em: {self._log_path}")

    def _toggle_pause(self):
        if not self._paused:
            self._paused = True
            self._pause_event.clear()
            self._btn_pause.configure(text="Retomar", fg_color="#16A34A", hover_color="#15803D")
            self._log("  ⏸ Envios pausados. Clique em Retomar para continuar.")
        else:
            self._paused = False
            self._pause_event.set()
            self._btn_pause.configure(text="Pausar", fg_color="#D97706", hover_color="#B45309")
            self._log("  ▶ Retomando envios...")

    def _show_failures(self):
        win = ctk.CTkToplevel(self)
        win.title("Envios com falha")
        win.geometry("520x360")
        ctk.CTkLabel(win, text=f"{len(self._failures)} envio(s) falharam:", font=ctk.CTkFont(weight="bold")).pack(pady=12)
        box = ctk.CTkTextbox(win, state="normal")
        box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        for f in self._failures:
            box.insert("end", f"{f['nome']} ({f['telefone']}): {f['motivo']}\n")
        box.configure(state="disabled")
        ctk.CTkLabel(win, text=f"Log completo: {self._log_path}", text_color="gray", wraplength=480).pack(pady=4)
        ctk.CTkButton(win, text="Fechar", command=win.destroy).pack(pady=8)

    def _log(self, text: str):
        self.after(0, lambda t=text: self._append_log(t))

    def _append_log(self, text: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", text + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _update_progress(self, current: int, total: int):
        self.after(0, lambda: self._progress.set(current / total))
        self.after(0, lambda: self._lbl_progress.configure(text=f"{current} / {total} enviados"))
