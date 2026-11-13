@echo off
setlocal
cd /d "%~dp0"
echo G5-visual - Instalacion de Python y YOLO en un entorno local
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv ".venv" 2>nul
if not exist ".venv\Scripts\python.exe" py -3 -m venv ".venv" 2>nul
if not exist ".venv\Scripts\python.exe" python -m venv ".venv"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro Python. Instala Python 3.11 y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo Configuracion de Supabase creada automaticamente.
  ) else (
    echo ERROR: No existe .env.example. No se puede configurar Supabase.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Instalacion terminada. Supabase quedo configurado desde .env.
echo Abre iniciar.bat para usar la pagina.
echo La primera conexion de camara descargara el modelo de YOLO.
pause
exit /b 0
:error
echo.
echo No se completo la instalacion. Revisa tu conexion a Internet y el error mostrado arriba.
pause
exit /b 1
