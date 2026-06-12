# Caliper — dev entrypoints. The loop is the product; these keep the dev loop tight.
.PHONY: test review loop board fmt

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
