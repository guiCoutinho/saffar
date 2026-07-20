"""Atualização automática via GitHub Releases.

Fluxo: ao iniciar, o app consulta o último release do repositório; se a tag
for mais nova que app/version.py, baixa o .exe anexado ao release e dispara
um script que troca o executável depois que o app fecha.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Optional

from app.version import __version__

GITHUB_REPO = "guiCoutinho/saffar"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass
class UpdateInfo:
    version: str
    download_url: str


def _version_tuple(tag: str) -> tuple:
    """'v1.2.3' -> (1, 2, 3); tolera prefixos e sufixos na tag.

    Sempre retorna 3 componentes (completa com zeros) para evitar comparações
    entre tuplas de tamanhos diferentes — sem isso 'v1.2' viraria (1, 2) e
    seria considerado *menor* que (1, 2, 0), disparando atualização indevida.
    """
    nums = [int(n) for n in re.findall(r"\d+", tag)[:3]]
    nums += [0] * (3 - len(nums))
    return tuple(nums)


def check_for_update(timeout: float = 10.0) -> Optional[UpdateInfo]:
    """Retorna dados da nova versão se o último release do GitHub for mais novo.

    Só se aplica ao app empacotado (.exe); rodando do código-fonte retorna None.
    Erros de rede/API (inclusive repositório ainda sem releases) sobem como
    exceção — o chamador decide silenciá-los.
    """
    if not getattr(sys, "frozen", False):
        return None
    req = urllib.request.Request(
        _API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Saffar"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    tag = str(data.get("tag_name") or "")
    if not tag or _version_tuple(tag) <= _version_tuple(__version__):
        return None
    asset = next(
        (a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".exe")),
        None,
    )
    if asset is None:
        return None
    return UpdateInfo(version=tag.lstrip("vV"), download_url=asset["browser_download_url"])


def download_update(info: UpdateInfo, timeout: float = 60.0, on_progress=None) -> str:
    """Baixa o novo executável para a pasta do atual; retorna o caminho baixado.

    `on_progress(baixado, total)` é chamado a cada bloco (total=0 quando o
    servidor não informa Content-Length), permitindo exibir o percentual.
    """
    target = sys.executable + ".new"
    req = urllib.request.Request(info.download_url, headers={"User-Agent": "Saffar"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(target, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress(downloaded, total)
    except Exception:
        # Sem isso, um download interrompido deixaria um .exe.new de ~80MB órfão
        try:
            os.remove(target)
        except OSError:
            pass
        raise
    return target


def _build_update_script(pid: int, new_exe: str, exe_path: str) -> str:
    # O move só funciona depois que o bootloader do PyInstaller (processo pai)
    # solta o .exe, o que leva alguns segundos após o fechamento — daí as 30
    # tentativas. O timeout após o move dá tempo do antivírus terminar de
    # escanear o arquivo novo; reabrir cedo demais causa "Failed to load
    # Python DLL" na extração do onefile.
    return f"""@echo off
setlocal enabledelayedexpansion
:wait
timeout /t 1 /nobreak >nul
tasklist /fi "PID eq {pid}" 2>nul | find "{pid}" >nul && goto wait
set tries=0
:swap
move /y "{new_exe}" "{exe_path}" >nul 2>&1
if errorlevel 1 (
    set /a tries+=1
    if !tries! lss 30 (
        timeout /t 1 /nobreak >nul
        goto swap
    )
)
timeout /t 5 /nobreak >nul
start "" "{exe_path}"
del "%~f0"
"""


def apply_update_and_restart(new_exe: str) -> None:
    """Dispara o script que espera o app fechar, troca o .exe e reabre.

    O Windows não permite sobrescrever um executável em execução, por isso a
    troca é feita por um .bat externo depois que este processo encerra. O
    chamador deve fechar o aplicativo logo após esta função retornar.
    """
    script = _build_update_script(os.getpid(), new_exe, sys.executable)
    bat_path = os.path.join(tempfile.gettempdir(), "saffar_update.bat")
    # cmd lê .bat na página de código OEM; gravar em outra codificação
    # corromperia caminhos com acento
    with open(bat_path, "w", encoding="oem", errors="replace") as f:
        f.write(script)
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
