@echo off
REM Lanceur quotidien de l'analyse boursiere (marche a blanc).
REM Appele par le Planificateur de taches Windows, chaque jour ouvre a 17h.

cd /d "C:\Users\chris\Desktop\Mes applis\Analyse boursiere"

REM Force l'UTF-8 pour les accents/emojis dans le log
set PYTHONUTF8=1

REM Horodatage dans le log
echo. >> "reports\journal.log"
echo ===== %DATE% %TIME% ===== >> "reports\journal.log"

"C:\Users\chris\AppData\Local\Programs\Python\Python314\python.exe" main.py >> "reports\journal.log" 2>&1
