.PHONY: install test clean demo bot website server

install:
	pip3 install -r core/requirements.txt
	@echo "Copy .env.example to .env and fill in your keys"

demo:
	PYTHONPATH=./core python3 -m src.cli --interactive

demo-single:
	PYTHONPATH=./core python3 -m src.cli $(S)

openclaw:
	cd plugin && openclaw gateway start

test:
	PYTHONPATH=./core python3 -m pytest core/tests/ -v

bot:
	python3 bot/telegram_bot.py

server:
	uvicorn server:app --reload --port 8000

website:
	cd ENFORX-WEB && npm run dev

clean:
	find . -name '__pycache__' -type d -exec rm -rf {} +
	rm -f enforx_audit.log core/enforx_audit.log
