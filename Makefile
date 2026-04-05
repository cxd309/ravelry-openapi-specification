.PHONY: generate serve

generate:
	uv run main.py

serve:
	simple-file-server ./docs 8081 ravelry-openapi-specification