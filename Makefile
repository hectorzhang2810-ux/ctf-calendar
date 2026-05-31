PYTHON := python3
VENV := venv
PORT := 5000

.PHONY: all setup install db fetch run clean

all: setup

$(VENV):
	$(PYTHON) -m venv $(VENV)

setup: $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

install: setup

db:
	. $(VENV)/bin/activate && FLASK_APP=app flask init-db

fetch:
	. $(VENV)/bin/activate && FLASK_APP=app flask fetch

run:
	. $(VENV)/bin/activate && FLASK_APP=app flask run --host=0.0.0.0 --port=$(PORT)

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ competitions.db
