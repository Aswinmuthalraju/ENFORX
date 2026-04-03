.PHONY: demo install test clean

install:
	pip install -r requirements.txt
	@echo "Copy .env.template to .env and fill in your keys"

demo:
	python demo.py

demo-single:
	python demo.py --scenario $(S)

openclaw:
	python openclaw_tool.py "Buy 5 shares of AAPL"

test:
	python -m pytest tests/ -v

clean:
	find . -name '__pycache__' -type d -exec rm -rf {} +
	rm -f enforx_audit.log
