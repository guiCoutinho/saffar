import sys
import subprocess
import os
import customtkinter as ctk


FIRST_RUN_FLAG = os.path.join(os.environ.get("APPDATA", "."), "Saffar", ".chromium_installed")


def _install_chromium():
    """
    Instala o Chromium chamando diretamente o driver Node do Playwright.

    IMPORTANTE: NÃO usar `sys.executable -m playwright install`. No executável
    empacotado pelo PyInstaller, `sys.executable` é o próprio Saffar.exe (não o
    Python), então esse comando relançaria o app em loop infinito de janelas.
    O driver (node.exe + cli.js) é resolvido a partir do pacote playwright, que
    é empacotado no .exe via saffar.spec.
    """
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    node_exe, cli_path = compute_driver_executable()
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    subprocess.run(
        [node_exe, cli_path, "install", "chromium"],
        check=True,
        env=get_driver_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def ensure_chromium():
    if os.path.exists(FIRST_RUN_FLAG):
        return

    root = ctk.CTk()
    root.title("Saffar — Configuração Inicial")
    root.geometry("400x160")
    root.resizable(False, False)
    ctk.set_appearance_mode("dark")

    ctk.CTkLabel(root, text="Configurando Saffar...", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(24, 8))
    lbl = ctk.CTkLabel(
        root,
        text="Baixando navegador (Chromium). Isso ocorre apenas na primeira vez.\nAguarde — pode levar alguns minutos...",
        text_color="gray",
        justify="center",
    )
    lbl.pack()
    bar = ctk.CTkProgressBar(root, mode="indeterminate")
    bar.pack(pady=12, padx=40, fill="x")
    bar.start()

    root.update()

    try:
        _install_chromium()
        os.makedirs(os.path.dirname(FIRST_RUN_FLAG), exist_ok=True)
        with open(FIRST_RUN_FLAG, "w") as f:
            f.write("")
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
