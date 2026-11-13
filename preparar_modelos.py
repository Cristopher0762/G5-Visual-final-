"""Descarga los dos modelos oficiales antes de trabajar sin Internet."""
from pathlib import Path
from ultralytics import YOLO

root=Path(__file__).resolve().parent
(root/'models').mkdir(exist_ok=True)
for name in ('yolov8n.pt','yolov8n-pose.pt'):
    path=root/'models'/name
    print('Preparando',name,flush=True)
    YOLO(str(path))
print('Modelos listos. Las imágenes de cámara no intervienen en esta descarga.')
