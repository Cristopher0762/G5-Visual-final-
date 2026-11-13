from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from g5_visual.application.services.vision_service import VisionService
from g5_visual.domain.models.configuracion_pausa import ConfiguracionPausa
from g5_visual.infrastructure.capture.opencv_capture_adapter import OpenCVCaptureAdapter
from g5_visual.infrastructure.vision.yolo_detector_adapter import YoloDetectorAdapter
from g5_visual.presentation.controllers.capture_controller import CaptureController
from g5_visual.presentation.views.camera_window import OpenCVWindow


def main() -> int:
    # Ajusta estos valores para las pruebas y criterios de aceptación del equipo.
    config = ConfiguracionPausa(
        umbral_pausa_segundos=45 * 60,       # RF-05 / HU-03: 45 minutos
        umbral_ausencia_segundos=5.0,       # descarta falsos negativos breves
        duracion_aviso_segundos=10.0,       # aviso visible durante 10 segundos
    )
    capture = OpenCVCaptureAdapter(camera_index=0, width=640, height=480)
    detector = YoloDetectorAdapter(model_path="yolov8n.pt", confidence=0.45)
    vision_service = VisionService(detector=detector)
    view = OpenCVWindow(window_name="G5-Visual | Monitoreo")
    controller = CaptureController(capture=capture, vision=vision_service, view=view, config=config)
    try:
        controller.run()
    except (RuntimeError, OSError) as exc:
        print(f"Error al iniciar G5-Visual: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nMonitoreo interrumpido por el usuario.")
    finally:
        capture.release()
        view.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
