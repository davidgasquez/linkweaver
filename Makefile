.PHONY: .uv
.uv:
	@uv --version || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'

.PHONY: setup
setup: .uv
	uv sync --frozen

.PHONY: build
build:
	uv build

.PHONY: test
test:
	uv run -m unittest discover -s tests

.PHONY: publish
publish: build
	uv publish

.PHONY: lint
lint:
	uvx ruff check
	uv run --with ty ty check
