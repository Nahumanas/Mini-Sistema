@echo off
title Mini-Sistema
cd /d "%~dp0"
echo.
echo  Abriendo el Mini-Sistema en el navegador...
echo  No cierres esta ventana mientras lo uses.
echo.
REM Abre el navegador unos segundos despues, cuando el sistema ya arranco
start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8501"
python -m streamlit run app.py --server.headless true
REM Si se apago con el boton "Apagar el sistema", la ventana se cierra sola
if errorlevel 1 (
  echo.
  echo  Algo salio mal. Copia el mensaje de arriba y pasaselo a Claude.
  pause
)
