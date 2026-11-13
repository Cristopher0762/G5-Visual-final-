"""Inicia la página G5-visual en este equipo."""
from pathlib import Path
import argparse
import sys
import threading
import webbrowser

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))


def load_env_file():
    """Carga .env sin sobrescribir variables ya definidas en el sistema."""
    env_path=ROOT/".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key,value=line.split("=",1)
        key=key.strip();value=value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key]=value


import os
load_env_file()
from web_server import create_server


def main():
    parser=argparse.ArgumentParser(description='G5-visual: servidor local de cámara y página web')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--preview',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--host',default='127.0.0.1',help=argparse.SUPPRESS)
    parser.add_argument('--strictPort',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:server=create_server(ROOT,args.port,preview=args.preview)
    except OSError as exc:
        print(f'No se pudo abrir el puerto {args.port}: {exc}\nPrueba: python main.py --port 8766')
        return 1
    url=f'http://localhost:{server.server_port}/'
    cloud=bool(os.getenv("G5_API_URL"))
    access=('Autenticación y datos centrales: Supabase.' if cloud else 'Modo local SQLite: configura G5_API_URL para activar Supabase.')
    print(f'G5-visual disponible en {url}\n{access}\nCtrl+C para cerrar. La cámara se activa solo desde la página.',flush=True)
    if not args.no_browser:
        threading.Timer(.7,lambda:webbrowser.open(url)).start()
    try:server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:pass
    finally:
        server.app.runtime.stop(finish=True)
        server.app.repo.close()
        server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
