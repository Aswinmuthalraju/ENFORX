.PHONY: telegram openclaw demo install

install:
	pip install -r requirements.txt

telegram:
	source venv/bin/activate && python telegram_bot.py

openclaw:
	source venv/bin/activate && python openclaw_tool.py "Buy 5 shares of AAPL"

demo:
	source venv/bin/activate && python demo.py
