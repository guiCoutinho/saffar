"""
Script de build do Saffar.
Uso: python build.py
Gera: dist/Saffar.exe
"""
import subprocess
import sys
import os
import shutil


def run(cmd: list, description: str):
    print(f"\n>>> {description}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"ERRO em: {description}")
        sys.exit(result.returncode)


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    # Limpa builds anteriores
    for folder in ("dist", "build"):
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"Removido: {folder}/")

    run(
        [sys.executable, "-m", "PyInstaller", "saffar.spec", "--noconfirm"],
        "Empacotando com PyInstaller",
    )

    exe_path = os.path.join(root, "dist", "Saffar.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\nBuild concluido: dist/Saffar.exe ({size_mb:.1f} MB)")
        print("  O Chromium será baixado automaticamente na primeira execução pelo usuário.")
    else:
        print("\nERRO: Saffar.exe não encontrado após o build.")
        sys.exit(1)


if __name__ == "__main__":
    main()
