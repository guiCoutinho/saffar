import sys
import subprocess
import os
import threading

# Fixa o diretório dos navegadores do Playwright ANTES de qualquer uso.
# Em apps congelados pelo PyInstaller, o Playwright define
# PLAYWRIGHT_BROWSERS_PATH=0 por padrão (playwright/_impl/_transport.py),
# fazendo-o procurar o Chromium dentro da pasta temporária _MEIxxxx do
# .exe — que muda a cada execução. Já o `playwright install` baixa para
# %LOCALAPPDATA%\ms-playwright. Sem esta linha, instalação e execução
# apontam para lugares diferentes e o "Conectar WhatsApp" falha com
# "Executable doesn't exist" em máquinas que só têm o .exe.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ms-playwright"),
)

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

    result = subprocess.run(
        [node_exe, cli_path, "install", "chromium"],
        env=get_driver_env(),
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "sem detalhes").strip()[-400:]
        raise RuntimeError(f"playwright install retornou código {result.returncode}: {detail}")


def _chromium_ok() -> bool:
    """
    Verifica se o executável do Chromium desta versão do Playwright existe
    de fato no disco. A flag de primeira execução NÃO é confiável sozinha:
    versões antigas do app podiam gravá-la mesmo com a instalação incompleta,
    e o download pode ter sido interrompido em outra máquina.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


def ensure_chromium():
    if os.path.exists(FIRST_RUN_FLAG) and _chromium_ok():
        return

    # Flag órfã (instalação anterior falhou ou ficou incompleta): remove e reinstala.
    if os.path.exists(FIRST_RUN_FLAG):
        os.remove(FIRST_RUN_FLAG)

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

    # O download leva minutos: rodar em thread mantém a janela responsiva
    # (subprocess.run direto congelaria a UI e o Windows marcaria "não respondendo")
    state = {"done": False, "error": None}

    def _work():
        try:
            _install_chromium()
            if not _chromium_ok():
                raise RuntimeError(
                    "A instalação terminou, mas o executável do Chromium não foi encontrado. "
                    "Verifique a conexão com a internet e o espaço em disco, e abra o Saffar novamente."
                )
            os.makedirs(os.path.dirname(FIRST_RUN_FLAG), exist_ok=True)
            with open(FIRST_RUN_FLAG, "w") as f:
                f.write("")
        except Exception as e:
            state["error"] = e
        state["done"] = True

    def _poll():
        if not state["done"]:
            root.after(200, _poll)
            return
        if state["error"] is not None:
            lbl.configure(text=f"Erro ao instalar Chromium: {state['error']}", text_color="red")
            bar.stop()
        else:
            root.destroy()

    threading.Thread(target=_work, daemon=True).start()
    root.after(200, _poll)
    root.mainloop()

    if state["error"] is not None or not state["done"]:
        sys.exit(1)


def main():
    ensure_chromium()
    from app.ui.app_window import AppWindow
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
