# G5-Visual — monitoreo local, eventos y pausas activas

Prototipo de escritorio monolítico organizado por capas con MVC en presentación. OpenCV captura la cámara, YOLOv8n detecta la clase `person`, el servicio de eventos aplica reglas temporales para las ausencias y el servicio de pausas controla el tiempo de trabajo continuo y presenta una alerta visual.

## Requisitos cubiertos en esta iteración

- **RF-01/RF-02:** captura local con OpenCV y detección YOLO de presencia.
- **RF-03/RF-04:** máquina de estados `Presente`, `Posible ausencia`, `Ausente confirmado` y `Retorno`; registra inicio, fin y duración de ausencias confirmadas.
- **RF-05/HU-03:** contador de trabajo continuo con umbral configurable; valor inicial de ejemplo: 45 minutos.
- **RF-06:** alerta visual de pausa activa durante 10 segundos después de alcanzar el umbral.
- **Modelo conceptual:** `Sesion`, `EventoAusencia`, `EventoPausa` y `ConfiguracionPausa`.
- **RNF-02:** no se guardan ni transmiten fotogramas o videos. Solo se mantienen objetos de sesión y eventos en memoria en esta iteración.

## Estructura

```text
G5-Visual/
├── main.py
├── requirements.txt
├── README.md
├── tests/
│   ├── test_event_service.py
│   └── test_pause_service.py
└── src/g5_visual/
    ├── presentation/
    │   ├── controllers/capture_controller.py
    │   └── views/camera_window.py
    ├── application/services/
    │   ├── vision_service.py
    │   ├── event_service.py
    │   └── pause_service.py
    ├── domain/
    │   ├── models/
    │   │   ├── detection_result.py
    │   │   ├── session_state.py
    │   │   ├── sesion.py
    │   │   ├── evento_ausencia.py
    │   │   ├── evento_pausa.py
    │   │   └── configuracion_pausa.py
    │   └── ports/
    └── infrastructure/
        ├── capture/opencv_capture_adapter.py
        └── vision/yolo_detector_adapter.py
```

## Reglas temporales implementadas

1. Si YOLO detecta una persona, el estado queda en `Presente` (o pasa momentáneamente a `Retorno` si existía una ausencia confirmada).
2. Cuando deja de detectar una persona, el estado pasa a `Posible ausencia` y empieza un reloj monotónico.
3. Si la detección reaparece antes de `umbral_ausencia_segundos`, se descarta la posible ausencia y **no** se crea un evento.
4. Si la ausencia dura al menos el umbral, se crea `EventoAusencia` con inicio en el primer negativo y estado `Ausente confirmado`.
5. Cuando la persona reaparece, se cierra el evento y se muestra `Retorno`. Si se cierra la aplicación mientras una ausencia está confirmada, se cierra el evento al finalizar la sesión.
6. El contador de trabajo continuo sigue avanzando durante posibles ausencias breves, pero se pausa durante una ausencia confirmada. Al llegar al umbral de pausa, se agrega un `EventoPausa`, el contador comienza un nuevo ciclo y se muestra el aviso visual durante el tiempo configurado.

El contador usa reloj monotónico para calcular intervalos y fechas de calendario para los eventos. Así se evita que un cambio manual de hora del sistema altere los umbrales.

## Configuración

En `main.py` se configuran estos valores:

```python
ConfiguracionPausa(
    umbral_pausa_segundos=45 * 60,
    umbral_ausencia_segundos=5.0,
    duracion_aviso_segundos=10.0,
)
```

Para hacer pruebas rápidas, por ejemplo, usa `umbral_pausa_segundos=60` y `umbral_ausencia_segundos=2.0`. Restaura los valores acordados antes de la demostración final. Los 45 minutos y 5 segundos son valores iniciales configurables; el umbral definitivo de ausencia debe validarse con los criterios de aceptación del equipo.

## Instalación y ejecución

Recomendado: Python 3.10 o 3.11. Desde una terminal, dentro de `G5-Visual`:

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### Linux Mint / Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

La primera ejecución puede descargar los pesos `yolov8n.pt` si no están disponibles localmente. Esto descarga el modelo, no imágenes de la cámara. Pulsa **Q** o **Esc** para finalizar. Si la cámara no es la predeterminada, cambia `camera_index=0` en `main.py`.

## Pruebas automatizadas

Las pruebas usan un reloj simulado, no necesitan cámara ni pesos YOLO:

```bash
# Desde la raíz del proyecto
PYTHONPATH=src python -m unittest discover -s tests -v
```

En PowerShell también puedes usar `$env:PYTHONPATH="src"; python -m unittest discover -s tests -v`.

## Privacidad y alcance pendiente

- Los fotogramas se procesan en memoria; el código no usa `cv2.imwrite`, `VideoWriter`, almacenamiento de imágenes ni inferencia remota.
- Ultralytics puede descargar los pesos del modelo durante la primera ejecución. Si el entorno exige operar sin red, prepara los pesos localmente antes y ejecuta con el equipo desconectado.
- La sesión y sus eventos se mantienen **solo en memoria** y se pierden al cerrar la aplicación. Todavía no se ha implementado repositorio local, persistencia, reportes ni exportación; eso se hará como módulo independiente, guardando únicamente metadatos y nunca imágenes/videos.
- La detección `person` indica que hay una persona en el encuadre; no identifica a un usuario concreto.
- RNF-01 (15 FPS), RNF-03 (alerta en máximo 1,5 s), consumo de CPU y precisión son objetivos que deben medirse en el equipo de referencia. Las pruebas unitarias comprueban la lógica temporal, no certifican rendimiento real ni precisión de YOLO.

## Capas y MVC

- **Presentación:** el controlador coordina captura, servicios y vista; la vista dibuja estado, contador y alerta.
- **Aplicación:** `VisionService`, `EventService` y `PauseService` orquestan visión, transiciones y pausas.
- **Dominio:** las entidades y la enumeración de estados contienen los datos y vocabulario del negocio.
- **Infraestructura:** los adaptadores encapsulan OpenCV y Ultralytics/YOLO.
