"""Servidor local de la página y API; no depende de Flask ni de servicios externos."""
import hmac
import json
import mimetypes
import secrets
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,unquote

from g5_visual.infrastructure.persistence.sqlite_repository import SqliteRepository
from g5_visual.infrastructure.persistence.supabase_client import SupabaseCloudClient, AccountAlreadyActiveError
from g5_visual.infrastructure.vision.camera_runtime import CameraRuntime

class Application:
    def __init__(self,root,data_path=None):
        self.root=Path(root);self.repo=SqliteRepository(data_path or self.root/"data"/"g5.sqlite3")
        self.runtime=CameraRuntime(self.repo,self.root);self.logins={};self.lock=threading.RLock()
        self.cloud=SupabaseCloudClient(device_id_path=self.root/"data"/"device_id")
        self.cloud_cache={}

    def user_for_identity(self,identity):
        return identity.get("cloud_user") or self.repo.user_by_username(identity["username"])

    def login(self,username,password):
        cloud_token=None;cloud_user=None
        if self.cloud.enabled:
            try:
                remote=self.cloud.login(username,password)
            except AccountAlreadyActiveError:
                raise
            except PermissionError:
                return None
            cloud_token=remote["token"];cloud_user=remote["user"]
            user={**cloud_user,"password_hash":"","password_salt":""}
        else:
            user=self.repo.user_by_username(username)
            if not user or not self.repo.verify_password(password,user["password_hash"],user["password_salt"]):
                return None
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
        with self.lock:
            now=time.monotonic()
            self.logins={k:v for k,v in self.logins.items() if v["expires"]>now}
            self.logins[token]={"username":user["username"],"user_id":user["id"],"csrf":csrf,"expires":now+12*3600,
                                "cloud_token":cloud_token,"cloud_user":cloud_user,"device_id":remote.get("device_id") if cloud_token else None}
        if cloud_token:
            self.repo.cloud_sync=lambda item, t=cloud_token: self.cloud.sync_session(t,item)
            self.repo.cloud_settings_save=lambda value,t=cloud_token: self.cloud.save_settings(t,value)
            try:
                settings=self.cloud.settings(cloud_token)
                if settings and not (self.runtime.thread and self.runtime.thread.is_alive()):
                    self.runtime.configure(settings)
            except RuntimeError:
                pass
        return token,csrf,user

    def state(self,identity):
        user=self.user_for_identity(identity)
        if not user or user["id"]!=identity["user_id"]:
            raise PermissionError("La cuenta está desactivada o ya no existe.")
        public={k:user[k] for k in ("id","nombres","apellidos","name","username","role","employeeId","active","createdAt")}
        camera=self.runtime.snapshot(heartbeat=False)
        active_employee=self.runtime.owner_employee_id or (camera.get("session") or {}).get("employeeId")
        if user["role"]=="worker" and active_employee==user["employeeId"]:
            with self.runtime.lock:self.runtime.heartbeat=time.monotonic()
        if user["role"]=="worker" and active_employee and active_employee!=user["employeeId"]:
            camera["status"]="idle";camera["presence_state"]="Cámara ocupada por otro trabajador"
            camera["session"]=None;camera["session_id"]=None;camera["rest"]=None;camera["alert"]=None
        if identity.get("cloud_token"):
            cached=self.cloud_cache.get(user["id"])
            if not cached or time.monotonic()-cached["at"]>3:
                remote_sessions=self.cloud.sessions(identity["cloud_token"])
                remote_workers=self.cloud.users(identity["cloud_token"]) if user["role"]=="admin" else [user]
                cached={"at":time.monotonic(),"sessions":remote_sessions,"workers":remote_workers}
                self.cloud_cache[user["id"]]=cached
            sessions=list(cached["sessions"])
            workers=cached["workers"]
        else:
            sessions=self.repo.sessions(None if user["role"]=="admin" else user["employeeId"])
            workers=self.repo.users(include_inactive=True)
        current=camera.pop("session",None)
        if current and (user["role"]=="admin" or current.get("employeeId")==user["employeeId"]):
            sessions=[item for item in sessions if item["id"]!=current["id"]]+[current]
        status={"running":"active","break":"break","paused":"paused","idle":"offline"}[camera["status"]]
        if camera["status"]=="running" and camera["presence_state"]=="Ausente confirmado":status="away"
        latest_by_employee={}
        for item in sessions:
            employee=item.get("employeeId")
            if employee and (employee not in latest_by_employee or str(item.get("startedAt", ""))>str(latest_by_employee[employee].get("startedAt", ""))):
                latest_by_employee[employee]=item
        employees=[]
        for worker in workers:
            if worker["role"]=="worker" and (user["role"]=="admin" or worker["id"]==user["id"]):
                latest=latest_by_employee.get(worker["employeeId"])
                remote_status={"running":"active","break":"break","paused":"paused","idle":"offline"}.get((latest or {}).get("status"),"offline")
                worker_status=("inactive" if not worker["active"] else status if worker["employeeId"]==self.runtime.owner_employee_id else remote_status)
                employees.append({"id":worker["employeeId"],"name":worker["name"],"job":"Trabajador" if worker["active"] else "Cuenta desactivada","status":worker_status})
        return {"user":public,"csrf":identity["csrf"],"camera":camera,"sessions":sessions,
                "employees":employees,"version":"2.1","source":"camera"}


class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True

    def __init__(self,*args,**kwargs):
        self.stopping=threading.Event()
        super().__init__(*args,**kwargs)

    def shutdown(self):
        self.stopping.set()
        super().shutdown()

    def server_close(self):
        self.stopping.set()
        super().server_close()


def handler_for(app,allow_preview=False):
    class Handler(BaseHTTPRequestHandler):
        server_version="G5Visual/2"

        def log_message(self,format,*args):
            if args and str(args[1] if len(args)>1 else "").startswith("5"):
                super().log_message(format,*args)

        def allowed_host(self):
            host=self.headers.get("Host","").split(":")[0]
            return host in ({"localhost","127.0.0.1","[::1]","terminal.local"} if allow_preview else {"localhost","127.0.0.1"})

        def send_bytes(self,payload,content_type,status=200,cookie=None):
            self.send_response(status);self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(payload)));self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff");self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            if cookie:self.send_header("Set-Cookie",cookie)
            self.end_headers()
            try:self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):pass

        def json(self,data,status=200,cookie=None):
            self.send_bytes(json.dumps(data,ensure_ascii=False,allow_nan=False).encode(),"application/json; charset=utf-8",status,cookie)

        def identity(self):
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get("Cookie",""))
            except Exception:return None,None
            token=cookie.get("g5_session");token=token.value if token else ""
            with app.lock:identity=app.logins.get(token)
            if not identity or identity["expires"]<time.monotonic():return None,None
            user=app.user_for_identity(identity)
            if not user or user["id"]!=identity["user_id"]:
                with app.lock:app.logins.pop(token,None)
                return None,None
            return token,identity

        def do_GET(self):
            if not self.allowed_host():self.json({"error":"Solo se permite acceso local."},403);return
            path=urlparse(self.path).path
            if path=="/api/health":
                self.json({"ok":True,"service":"g5-visual","version":"2.0","missing":app.runtime.missing_dependencies()});return
            if path.startswith("/api/"):
                token,identity=self.identity()
                if not identity:self.json({"error":"Inicia sesión para continuar."},401);return
                if path=="/api/state":self.json(app.state(identity));return
                if path=="/api/users":
                    user=app.user_for_identity(identity)
                    if user["role"]!="admin":self.json({"error":"Solo el administrador puede gestionar usuarios."},403);return
                    self.json({"users":app.cloud.users(identity["cloud_token"]) if identity.get("cloud_token") else app.repo.users()});return
                if path=="/api/events":
                    self.send_response(200);self.send_header("Content-Type","text/event-stream")
                    self.send_header("Cache-Control","no-store");self.send_header("X-Accel-Buffering","no")
                    self.end_headers()
                    last_heartbeat=time.monotonic()
                    try:
                        while not self.server.stopping.is_set() and token in app.logins and identity["expires"]>time.monotonic():
                            if identity.get("cloud_token") and time.monotonic()-last_heartbeat>=20:
                                try:
                                    app.cloud.heartbeat(identity["cloud_token"])
                                    last_heartbeat=time.monotonic()
                                except PermissionError:
                                    with app.lock:app.logins.pop(token,None)
                                    if identity.get("cloud_user",{}).get("role")=="worker" and app.runtime.owner_employee_id==identity.get("cloud_user",{}).get("employeeId"):
                                        app.runtime.stop(finish=True)
                                    self.wfile.write(("data: "+json.dumps({"authExpired":True})+"\n\n").encode());self.wfile.flush()
                                    return
                                except RuntimeError:
                                    # Si no puede renovar el lease durante 90 s, detiene la captura local.
                                    if time.monotonic()-last_heartbeat>=90:
                                        with app.lock:app.logins.pop(token,None)
                                        if identity.get("cloud_user",{}).get("role")=="worker" and app.runtime.owner_employee_id==identity.get("cloud_user",{}).get("employeeId"):
                                            app.runtime.stop(finish=True)
                                        self.wfile.write(("data: "+json.dumps({"authExpired":True})+"\n\n").encode());self.wfile.flush()
                                        return
                            payload=json.dumps(app.state(identity),ensure_ascii=False)
                            self.wfile.write(("data: "+payload+"\n\n").encode());self.wfile.flush()
                            self.server.stopping.wait(1)
                    except (BrokenPipeError,ConnectionResetError,OSError):pass
                    return
                if path=="/api/camera/frame.jpg":
                    user=app.user_for_identity(identity)
                    if user["role"]!="worker":self.json({"error":"La imagen solo está disponible para el trabajador."},403);return
                    with app.runtime.lock:
                        if app.runtime.owner_employee_id and app.runtime.owner_employee_id!=user["employeeId"]:
                            self.json({"error":"La cámara está siendo utilizada por otro trabajador."},403);return
                        frame=app.runtime.frame
                    if frame:self.send_bytes(frame,"image/jpeg")
                    else:self.json({"error":"Aún no hay imagen disponible."},503)
                    return
                self.json({"error":"Ruta no encontrada."},404);return
            relative=unquote(path.lstrip("/")) or "index.html"
            file=(app.root/"web"/relative).resolve();web=(app.root/"web").resolve()
            if web not in file.parents or not file.is_file():self.json({"error":"Archivo no encontrado."},404);return
            self.send_bytes(file.read_bytes(),(mimetypes.guess_type(file)[0] or "application/octet-stream")+("; charset=utf-8" if file.suffix in (".js",".css",".html") else ""))

        def do_POST(self):
            if not self.allowed_host():self.json({"error":"Solo se permite acceso local."},403);return
            origin=self.headers.get("Origin")
            if origin and urlparse(origin).netloc!=self.headers.get("Host"):
                self.json({"error":"Origen no permitido."},403);return
            if not self.headers.get("Content-Type","").startswith("application/json"):
                self.json({"error":"Se requiere JSON."},415);return
            try:
                length=int(self.headers.get("Content-Length","0"))
                if length<0 or length>16384:raise ValueError("Solicitud demasiado grande.")
                body=json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body,dict):raise ValueError("El contenido debe ser un objeto JSON.")
                path=urlparse(self.path).path
                if path=="/api/login":
                    username=str(body.get("username",""))[:50];password=str(body.get("password",""))[:200]
                    result=app.login(username,password)
                    if not result:self.json({"error":"Usuario o contraseña incorrectos."},401);return
                    token,csrf,user=result
                    public={k:user[k] for k in ("id","nombres","apellidos","name","username","role","employeeId","active","createdAt")}
                    self.json({"user":public,"csrf":csrf},cookie=f"g5_session={token}; HttpOnly; SameSite=Strict; Path=/");return
                token,identity=self.identity()
                if not identity:self.json({"error":"Inicia sesión para continuar."},401);return
                if not hmac.compare_digest(self.headers.get("X-G5-CSRF",""),identity["csrf"]):
                    self.json({"error":"Recarga la página para renovar la sesión."},403);return
                user=app.user_for_identity(identity)
                if path=="/api/account/password":
                    if identity.get("cloud_token"):
                        app.cloud.change_password(identity["cloud_token"],str(body.get("current_password","")),str(body.get("new_password","")))
                    else:
                        app.repo.change_password(user["id"],str(body.get("current_password","")),str(body.get("new_password","")))
                    self.json({"ok":True});return
                if path=="/api/logout":
                    if user["role"]=="worker" and app.runtime.monitor.data and app.runtime.monitor.data.get("employeeId")==user["employeeId"]:app.runtime.stop()
                    if identity.get("cloud_token"):
                        app.cloud.logout(identity["cloud_token"])
                    with app.lock:app.logins.pop(token,None)
                    self.json({"ok":True},cookie="g5_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0");return
                if path.startswith("/api/admin/users/") or path=="/api/admin/users":
                    if user["role"]!="admin":self.json({"error":"Solo el administrador puede gestionar usuarios."},403);return
                    if path=="/api/admin/users":
                        if body.get("action")=="create":
                            if identity.get("cloud_token"):
                                result=app.cloud.create_user(identity["cloud_token"],nombres=str(body.get("nombres","")),apellidos=str(body.get("apellidos","")),username=str(body.get("username","")),password=str(body.get("password","")),role=str(body.get("role","worker")))
                                self.json(result,201);return
                            created=app.repo.create_user(str(body.get("nombres","")),str(body.get("apellidos","")),str(body.get("username","")),str(body.get("password","")),str(body.get("role","worker")))
                            self.json({"ok":True,"user":{k:created[k] for k in ("id","nombres","apellidos","name","username","role","employeeId","active","createdAt")}},201);return
                        self.json({"error":"Acción de usuario no válida."},400);return
                    parts=path.strip("/").split("/");user_id=parts[-1]
                    if len(parts)>=5 and parts[-2]=="deactivate":user_id=parts[-1]
                    if path.endswith("/deactivate"):
                        target_id=parts[-2]
                        if identity.get("cloud_token"):
                            app.cloud.deactivate_user(identity["cloud_token"],target_id)
                            self.json({"ok":True});return
                        target=next((x for x in app.repo.users() if x["id"]==target_id),None)
                        if not target:self.json({"error":"Usuario no encontrado."},404);return
                        if target_id==user["id"]:self.json({"error":"No puedes desactivar tu propia cuenta."},400);return
                        if target["role"]=="admin" and sum(1 for x in app.repo.users(False) if x["role"]=="admin")<=1:self.json({"error":"No puedes desactivar al último administrador."},400);return
                        app.repo.deactivate_user(target_id)
                        with app.lock:
                            app.logins={k:v for k,v in app.logins.items() if v.get("user_id")!=target_id}
                        if target["role"]=="worker" and app.runtime.monitor.data and app.runtime.monitor.data.get("employeeId")==target["employeeId"]:app.runtime.stop()
                        self.json({"ok":True});return
                    if path.endswith("/reactivate"):
                        target_id=parts[-2]
                        if identity.get("cloud_token"):
                            app.cloud.reactivate_user(identity["cloud_token"],target_id)
                        else:
                            app.repo.reactivate_user(target_id)
                        self.json({"ok":True});return
                    if path.endswith("/reset-password"):
                        target_id=parts[-2]
                        new_password=str(body.get("new_password",""))
                        if len(new_password)<8 or len(new_password)>200:
                            self.json({"error":"La contraseña temporal debe tener entre 8 y 200 caracteres."},400);return
                        if target_id==user["id"]:
                            self.json({"error":"Usa la opción de cambio de contraseña de tu propia cuenta."},400);return
                        if identity.get("cloud_token"):
                            app.cloud.reset_password(identity["cloud_token"],target_id,new_password)
                        else:
                            app.repo.reset_password(target_id,new_password)
                            with app.lock:
                                app.logins={k:v for k,v in app.logins.items() if v.get("user_id")!=target_id}
                        self.json({"ok":True});return
                    if path.endswith("/update"):
                        target_id=parts[-2]
                        if identity.get("cloud_token"):
                            result=app.cloud.update_user(identity["cloud_token"],user_id=target_id,nombres=str(body.get("nombres","")),apellidos=str(body.get("apellidos","")),username=str(body.get("username","")),role=str(body.get("role","worker")))
                            self.json(result);return
                        if target_id==user["id"] and str(body.get("role","admin"))!="admin":
                            self.json({"error":"No puedes cambiar tu propio rol. Otro administrador puede hacerlo."},400);return
                        updated=app.repo.update_user(target_id,str(body.get("nombres","")),str(body.get("apellidos","")),str(body.get("username","")),str(body.get("role","worker")))
                        self.json({"ok":True,"user":{k:updated[k] for k in ("id","nombres","apellidos","name","username","role","employeeId","active","createdAt")}});return
                    self.json({"error":"Ruta de administración no encontrada."},404);return
                if user["role"]!="worker":
                    self.json({"error":"La cámara se controla desde el perfil del trabajador."},403);return
                runtime=app.runtime
                active_employee=runtime.owner_employee_id or (runtime.monitor.data or {}).get("employeeId")
                if active_employee and active_employee!=user["employeeId"] and runtime.thread and runtime.thread.is_alive():
                    raise RuntimeError("La cámara está siendo utilizada por otro trabajador.")
                if path=="/api/camera/start":runtime.start(monitor=False,employee_id=user["employeeId"])
                elif path=="/api/session/start":runtime.start(monitor=True,employee_id=user["employeeId"])
                elif path in ("/api/camera/stop","/api/session/pause"):runtime.stop()
                elif path=="/api/session/finish":runtime.stop(finish=True)
                elif path=="/api/camera/settings":runtime.configure({k:v for k,v in body.items() if k in runtime.settings})
                elif path=="/api/camera/calibrate":
                    with runtime.lock:
                        if runtime.state!="ready":raise ValueError("Conecta la cámara antes de calibrar.")
                        if not runtime.settings["pose_enabled"]:raise ValueError("Activa la estimación de postura en la configuración.")
                        runtime.monitor.posture.calibrate()
                elif path=="/api/break/start":
                    duration=float(body.get("duration",300))
                    if not 10<=duration<=1800:raise ValueError("Duración de pausa no válida.")
                    with runtime.lock:runtime.monitor.start_break(str(body.get("name","Pausa saludable"))[:80],duration,str(body.get("reminderId","r1"))[:100])
                elif path=="/api/break/finish":
                    with runtime.lock:runtime.monitor.finish_break()
                elif path=="/api/reminder/snooze":
                    with runtime.lock:runtime.monitor.snooze(300)
                else:self.json({"error":"Ruta no encontrada."},404);return
                self.json(app.state(identity))
            except AccountAlreadyActiveError as exc:self.json({"error":str(exc)},409)
            except PermissionError as exc:self.json({"error":str(exc)},403)
            except (ValueError,TypeError) as exc:self.json({"error":str(exc)},400)
            except RuntimeError as exc:self.json({"error":str(exc)},503)
            except Exception as exc:
                print("Error API:",type(exc).__name__,str(exc),flush=True)
                self.json({"error":"Ocurrió un error interno. Revisa la consola de Python."},500)
    return Handler


def create_server(root,port=8765,data_path=None,preview=False):
    app=Application(root,data_path)
    server=LocalServer(("0.0.0.0" if preview else "127.0.0.1",port),handler_for(app,preview))
    server.app=app
    return server
