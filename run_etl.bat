@echo off
rem Wrapper para o Agendador de Tarefas do Windows.
rem Agende este .bat com "Executar estando o usuario conectado ou nao".
cd /d %~dp0
call .venv\Scripts\activate.bat
python -m etl run --carteira todas
exit /b %ERRORLEVEL%
