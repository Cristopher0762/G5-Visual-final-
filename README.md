# G5-visual: página web con cámara, Python y YOLO

Esta versión integra la página HTML/CSS/JavaScript con la detección de los dos ZIP entregados. Usa la versión de eventos y pausas como base, ya que contiene todo el detector inicial y añade los servicios temporales.

## Inicio rápido en Windows

1. Extrae **todo** el ZIP. No ejecutes los archivos dentro del comprimido.
2. Instala **Python 3.11** si no lo tienes: <https://www.python.org/downloads/>.
3. Abre `instalar.bat`. Se crea `.venv`, se instalan las dependencias de `requirements.txt` y se genera automáticamente `.env` desde `.env.example` para activar Supabase. Esta instalación necesita Internet y puede tardar, especialmente por PyTorch.
4. Cuando termine correctamente, abre `iniciar.bat`. Se abre <http://localhost:8765/>. Deja abierta la ventana de Python.
5. Selecciona **Cámara con Python** e inicia sesión:

**Acceso inicial:** `admin2` · contraseña temporal: `12345678`. La cuenta `admin1` es una cuenta de trabajador heredada y también conserva la contraseña `12345678` hasta que la desactives. Inicia sesión como administrador, cambia tu contraseña desde el menú de perfil y crea cuentas individuales en **Usuarios**. Después puedes desactivar la cuenta heredada si ya no se necesita.

6. El administrador puede crear cuentas de tipo **Trabajador** o **Administrador** desde la sección **Usuarios**. Entra con una cuenta de trabajador para pulsar **Iniciar monitoreo**. También puedes usar **Conectar cámara** para ver el encuadre sin registrar una sesión.
7. La primera conexión descarga el modelo oficial `yolov8n-pose.pt` en `models/`. No son imágenes de tu cámara.
8. Siéntate de forma cómoda, muestra la cabeza y ambos hombros y pulsa **Calibrar postura**. Mantente estable hasta completar 15 observaciones válidas.
9. **Pausar** detiene y libera la cámara sin finalizar la sesión. **Reanudar** continúa el registro. **Finalizar** guarda el cierre para los informes.
10. Para cerrar el programa, detén el monitoreo y pulsa `Ctrl+C` en la consola de Python.

Para la detección real abre la dirección que muestra Python, en lugar de abrir `web/index.html` directamente. El modo **Datos de prueba** conserva la demostración original y mantiene sus registros separados de los reales.

## Qué incluye

- Cámara adquirida con OpenCV en el mismo equipo donde se ejecuta Python.
- YOLOv8 para presencia, cantidad de personas y confianza; YOLOv8 Pose para puntos corporales opcionales.
- Estados originales: **Presente**, **Posible ausencia**, **Ausente confirmado** y **Retorno**.
- Confirmación de ausencia después de 5 segundos por defecto; los negativos breves se descartan.
- Un único evento por ausencia continua, con inicio, cierre y duración. La duración utiliza reloj monotónico, aunque cambie la hora de Windows.
- Aviso de pausa activa después de 45 minutos de trabajo continuo por defecto. Una ausencia confirmada, la pausa manual o un descanso detienen ese contador.
- Descansos con duración y recuento de pausas completadas; no se suman como uso activo de aplicaciones.
- Estimación de alineación 2D tras calibración. Se comparan inclinación de hombros y desplazamiento lateral de cabeza con tu referencia. Una desviación debe durar 4 segundos por defecto para generar una alerta; se evita repetir la misma alerta mientras persiste.
- Los puntos poco visibles, varias personas o una calibración con demasiado movimiento producen **sin medición**, y no una falsa postura correcta o incorrecta.
- Configuración desde la página: índice de cámara, confianza, ausencia, pausa, confirmación de postura, FPS objetivo y CPU/GPU.
- Estadísticas e informes PDF con registros reales, separados de las sesiones de demostración.
- Persistencia central en Supabase PostgreSQL para cuentas, sesiones, eventos y configuración.
- SQLite (`data/g5.sqlite3`) conserva una copia local de las sesiones y permite persistencia local; no es la base de datos central compartida entre computadores.
- En modo conectado, las cuentas se autentican y administran en Supabase. Solo el administrador puede crear, editar y desactivar cuentas.
- Contraseñas protegidas con PBKDF2-HMAC-SHA256 y sal individual; el usuario puede cambiar su contraseña desde el menú de perfil.
- Desactivar una cuenta impide nuevos accesos y revoca sus sesiones activas, pero conserva las sesiones e historial para auditoría.
- El último administrador no puede desactivarse ni perder su rol. La cámara y sus fotogramas quedan asociados a un trabajador para evitar que otra cuenta vea su captura.
- Acceso verificado por Python y control de cámara reservado al trabajador. El administrador consulta metadatos e informes; no recibe la imagen de la cámara.
- Avisos claros si faltan dependencias, no se abre la cámara, fallan las imágenes o se pierde la conexión con Python.

## Aplicaciones y tiempo activo

En **Windows**, un adaptador usa las API del sistema para leer únicamente el nombre del proceso en primer plano y el tiempo desde la última interacción. No lee teclas, textos, títulos de ventana ni contenidos de documentos. El tiempo se asigna a una sola aplicación y requiere presencia en el intervalo anterior e interacción en los últimos 120 segundos.

En Linux/macOS ese adaptador devuelve **no disponible**. Los tiempos de aplicaciones quedan sin datos; no se inventan. La detección de cámara y presencia sí puede utilizarse con las dependencias adecuadas.

La presencia detectada **no mide atención, concentración, identidad ni productividad**. La estimación corporal es una comparación geométrica 2D, no una evaluación médica; una cámara frontal no permite medir con fiabilidad la profundidad cervical.

## Configurar la cámara

Antes de guardar ajustes pulsa **Desconectar** o **Pausar**. Cambiar los ajustes finaliza la sesión anterior para conservar la coherencia de sus umbrales.

| Ajuste | Predeterminado | Uso |
|---|---|---|
| Índice | 0 | Prueba 1, 2, etc. si corresponde a otra cámara |
| Confianza YOLO | 0,45 | Umbral para aceptar personas |
| Ausencia | 5 s | Descarta pérdidas breves de detección |
| Aviso de pausa | 45 min | Ciclo de trabajo continuo del archivo original |
| Confirmación de postura | 4 s | Evita avisos por movimientos breves |
| FPS objetivo | 8 | Límite de procesamiento; el rendimiento real se muestra en pantalla |
| Procesamiento | CPU | GPU 0 requiere NVIDIA y una instalación compatible de PyTorch CUDA |

La cámara se configura a 640 × 480 cuando el dispositivo lo permite. La versión de detección de personas sin pose utiliza `yolov8n.pt`. Si ocurre un error de GPU, selecciona CPU. No se garantiza una tasa de FPS o una precisión concreta sin medir el equipo y las condiciones de luz y encuadre.

Los recordatorios personales conservan sus ajustes en el navegador. El aviso automático de **trabajo continuo real** se configura en **Cámara → Configurar → Aviso de pausa**; es el contador del servicio Python original y no cuenta los avisos como descansos ya realizados.

## Privacidad y funcionamiento local

- Se guardan solo metadatos de sesiones, eventos, tiempos y configuración. No se escriben fotos ni videos.
- La inferencia se ejecuta localmente. No hay servicios de inferencia remotos ni envío de imágenes a terceros.
- Para mostrar la vista previa, Python entrega imágenes JPEG en memoria al navegador **por la conexión HTTP local del mismo PC**. Esta es la adaptación web respecto del requisito original de no transmitir fotogramas: existe transporte local de la vista previa, pero no un envío a servidores externos. No se incluye un modo de vigilancia por red.
- El servidor normal escucha solo en `127.0.0.1`. La aplicación está preparada para uso y demostración locales; no publiques este servidor en Internet. Cambia la contraseña temporal del administrador antes de utilizar datos reales.
- Al cerrar sesión desde el trabajador se libera la cámara. Si la página pierde su conexión de eventos, Python pausa y libera la captura cuando transcurren unos 25 segundos sin comunicación.
- La conexión de eventos mantiene la página actualizada aunque cambies entre sus apartados. Las sesiones se guardan primero en SQLite y se sincronizan de forma asíncrona con Supabase; no existe una cola duradera independiente para reintentar indefinidamente una sincronización fallida, por lo que la conexión debe mantenerse y la sincronización debe verificarse en las pruebas. Los informes guardados son fotografías de los metadatos al momento de generarlos y deben generarse de nuevo para incluir eventos posteriores.

## Otras formas de iniciar

Desde una terminal en la carpeta del proyecto:

```bash
python -m venv .venv
```

En Windows, sin activar scripts de PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

En Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Para otro puerto:

```bash
python main.py --port 8766
```

Abre la dirección impresa en consola. Para preparar los modelos y después usar el equipo sin Internet:

```bash
python preparar_modelos.py
```

## Problemas frecuentes

- **Faltan cv2, torch o ultralytics:** ejecuta de nuevo `instalar.bat` y revisa el error de instalación. Usa el Python de `.venv`, no otra instalación del sistema.
- **No abre la cámara:** cierra Zoom/Teams/otras aplicaciones, permite la cámara para aplicaciones de escritorio en Windows y prueba otro índice.
- **Primera conexión tarda:** puede estar descargando el modelo. Comprueba la consola y la conexión a Internet. No se sustituyen las detecciones con resultados falsos si la descarga falla.
- **Error de CUDA:** usa CPU. La instalación de CUDA depende del equipo y no se configura automáticamente.
- **No calibra postura:** muestra ambos hombros y cabeza, mejora la luz, mantente estable y asegúrate de que solo hay una persona en el encuadre.
- **Pérdida de cámara o inferencia demasiado lenta:** el intervalo se marca como técnico y se excluye del tiempo observado; no se interpreta como ausencia. Baja el objetivo de FPS o prueba otro equipo/modelo.
- **No abre el puerto:** usa `python main.py --port 8766` y abre la dirección que aparezca.
- **Datos vacíos:** en el modo real solo aparecen sesiones de cámara registradas. Inicia el monitoreo y selecciona su fecha en estadísticas o informes.

## Código reutilizado y estructura

`EventService`, `PauseService`, `Sesion`, `EventoAusencia`, `EventoPausa`, los puertos y los adaptadores provienen de los ZIP entregados. La versión inicial está contenida en la de eventos y pausas. Se conservaron sus pruebas; se corrigió el cierre temporal y se añadieron métodos para suspender el contador sin contar tiempo de cámara desconectada.

- `main.py`: inicia el servidor y abre el navegador.
- `web_server.py`: sirve la página y la API local; utiliza la biblioteca estándar de Python.
- `web/`: página original adaptada, `backend.js`, HTML, JavaScript y CSS.
- `src/g5_visual/application/services/`: servicios originales y nuevas reglas de monitoreo/postura.
- `src/g5_visual/infrastructure/vision/camera_runtime.py`: captura, YOLO, vista local y liberación de recursos.
- `src/g5_visual/infrastructure/persistence/`: repositorio SQLite de metadatos.
- `src/g5_visual/infrastructure/capture/windows_activity.py`: aplicaciones en primer plano en Windows.
- `desktop.py`: entrada de escritorio original. Puede usarse por separado, sin abrir al mismo tiempo la cámara de la web.
- `DOCUMENTACION_ORIGINAL.md`: documentación del ZIP de eventos y pausas sin sustituir su contenido.
- `tests/`: pruebas originales y nuevas pruebas de integración.

## Pruebas

Desde la raíz del proyecto, en Windows:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

También puedes abrir `probar.bat`. En Linux/macOS:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Las pruebas usan relojes, resultados de detección y solicitudes locales controladas. Comprueban la lógica temporal, las métricas, la persistencia, el acceso a la API y las reglas de calibración. No abren una cámara ni descargan pesos para aprobar.

Durante la preparación se verificaron estas pruebas, la sintaxis JavaScript y los flujos de interfaz disponibles. El entorno de preparación no dispone de cámara física ni de las dependencias/modelos de YOLO; **la captura física, la inferencia real y el rendimiento deberán comprobarse en tu equipo**. No se afirma que se hayan medido FPS o precisión de cámara aquí.

## Referencias técnicas

- YOLOv8 y tareas compatibles: <https://docs.ultralytics.com/models/yolov8/>
- Inferencia en memoria y resultados: <https://docs.ultralytics.com/modes/predict/>
- Puntos de pose: <https://docs.ultralytics.com/tasks/pose/>
- OpenCV VideoCapture: <https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html>

## Persistencia central en Supabase

La integración con PostgreSQL y las funciones centrales se describe en [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md). `instalar.bat` crea `.env` automáticamente en cada computador. Las cámaras y YOLO siguen ejecutándose localmente; usuarios, sesiones, eventos y configuraciones centrales se gestionan/sincronizan con Supabase. No distribuyas claves privilegiadas ni copies `data/device_id` entre equipos.


## Regla de sesión por cuenta

Una cuenta solo puede iniciar sesión desde un computador a la vez. Si ya está activa, un segundo acceso se rechaza con un mensaje claro. La sesión se renueva con un heartbeat y caduca tras 90 segundos sin conexión, para liberar cuentas cuando un computador se apaga inesperadamente.


## Administración de cuentas (actualización)

La administración permite desactivar y reactivar cuentas, y restablecer la contraseña de otro usuario mediante una contraseña temporal de al menos 8 caracteres. Al restablecer una contraseña se invalidan las sesiones de esa cuenta; al reactivarla, el usuario debe iniciar sesión nuevamente. La sesión del administrador que realiza estas operaciones se conserva.

En instalaciones conectadas a Supabase, después de actualizar el ZIP también debe desplegarse la versión incluida de `supabase/functions/g5-admin/index.ts` en el proyecto Supabase para habilitar las nuevas acciones en la base central. La función `g5-api` incluida también contiene un ajuste para conservar la sesión actual al cambiar la propia contraseña.
