import sys
import subprocess
import os
import customtkinter as ctk


FIRST_RUN_FLAG = os.path.join(os.environ.get("APPDATA", "."), "Saffar", ".chromium_installed")


def ensure_chromium():
    if os.path.exists(FIRST_RUN_FLAG):
        return

    root = ctk.CTk()
    root.title("Saffar — Configuração Inicial")
    root.geometry("400x160")
    root.resizable(False, False)
    ctk.set_appearance_mode("dark")

    ctk.CTkLabel(root, text="Configurando Saffar...", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(24, 8))
    lbl = ctk.CTkLabel(root, text="Baixando navegador (Chromium). Aguarde...", text_color="gray")
    lbl.pack()
    bar = ctk.CTkProgressBar(root, mode="indeterminate")
    bar.pack(pady=12, padx=40, fill="x")
    bar.start()

    root.update()

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.makedirs(os.path.dirname(FIRST_RUN_FLAG), exist_ok=True)
        open(FIRST_RUN_FLAG, "w").close()
    except Exception as e:
        lbl.configure(text=f"Erro ao instalar Chromium: {e}", text_color="red")
        bar.stop()
        root.mainloop()
        sys.exit(1)

    root.destroy()


def main():
    ensure_chromium()
    from app.ui.app_window import AppWindow
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
