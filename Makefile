# Analyse boursière — marche à blanc
# Cible principale : `make run` (à lancer tous les jours à 17h).

PY ?= python

.PHONY: install run eval dashboard report clean aide

aide:
	@echo "Cibles disponibles :"
	@echo "  make install     Installe les dependances (requirements.txt)"
	@echo "  make run         Execution quotidienne : evaluation veille + analyse + achat papier"
	@echo "  make eval        Evaluation seule des positions de la veille"
	@echo "  make dashboard   Tableau de bord recapitulatif (taux de reussite, P&L cumule)"
	@echo "  make report      Reaffiche le dernier portefeuille (positions JSON)"
	@echo "  make clean       Supprime les caches Python"

install:
	$(PY) -m pip install -r requirements.txt

run:
	$(PY) main.py

eval:
	$(PY) main.py --eval-seulement

dashboard:
	$(PY) dashboard.py

report:
	@$(PY) -c "import json,glob,os; f='data/portefeuille.json'; print(open(f,encoding='utf-8').read() if os.path.exists(f) else 'Aucun portefeuille.')"

clean:
	$(PY) -c "import shutil,glob; [shutil.rmtree(p,ignore_errors=True) for p in glob.glob('**/__pycache__',recursive=True)]"
