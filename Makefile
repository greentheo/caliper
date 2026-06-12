# Caliper — dev entrypoints. The loop is the product; these keep the dev loop tight.
# No activation needed: targets resolve the env python (override with CALIPER_PY=...).
.PHONY: test review loop board fmt run install

CALIPER_PY ?= $(firstword $(wildcard /opt/anaconda3/envs/caliper/bin/python $(HOME)/anaconda3/envs/caliper/bin/python $(HOME)/miniforge3/envs/caliper/bin/python) python)

install: ## editable-install caliper into the env (makes the `caliper` command available)
	$(CALIPER_PY) -m pip install -e ".[dev]"

run:    ## run the loop on an intent: make run INTENT="a 60mm bracket for 2020 with four M5 holes"
	$(CALIPER_PY) -m caliper.cli run "$(INTENT)" --no-llm --yes

test:   ## regression guard: pytest only
	bash nightshift/hooks/regression_guard.sh

review: ## full pre-commit guard: pytest + ruff + diff summary
	bash nightshift/review.sh

loop:   ## one bounded dev iteration (board + guard + next task)
	bash nightshift/loop.sh

board:  ## print the kanban
	@cat pm/BOARD.md

fmt:    ## autoformat with ruff (if installed)
	-ruff check --fix src tests
