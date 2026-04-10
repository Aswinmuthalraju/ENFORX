.PHONY: install test clean demo bot website

install:
	pip install -r core/requirements.txt
	@echo "Copy .env.example to .env and fill in your keys"

demo:
	PYTHONPATH=./core python -m src.cli --interactive

demo-single:
	PYTHONPATH=./core python -m src.cli $(S)

openclaw:
	cd plugin && openclaw gateway start

test:
	PYTHONPATH=./core python -m pytest core/tests/ -v

bot:
	python bot/telegram_bot.py

website:
	cd ENFORX-WEB && npm run dev

clean:
	find . -name '__pycache__' -type d -exec rm -rf {} +
	rm -f enforx_audit.log core/enforx_audit.log
