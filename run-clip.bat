@echo off
REM Menjalankan aplikasi dengan skor semantik CLIP aktif (eksperimen).
REM Butuh torch + open_clip_torch di venv (lihat requirements-clip.txt dan README).
REM Pertama kali dipakai butuh internet untuk mengunduh bobot model (~600 MB).
set CLIP_QUALITY=1
call "%~dp0run.bat"
