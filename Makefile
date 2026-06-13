# Caliper — dev entrypoints. The loop is the product; these keep the dev loop tight.
# No activation needed: targets resolve the env python (override with CALIPER_PY=...).
.PHONY: test review loop board fmt run gen refine run-llm refine-llm fit serve install

CALIPER_PY ?= $(firstword $(wildcard /opt/anaconda3/envs/caliper/bin/python $(HOME)/anaconda3/envs/caliper/bin/python $(HOME)/miniforge3/envs/caliper/bin/python) python)

# Intake/refine use the deterministic OFFLINE parser by default (reproducible). Pass LLM=1 to route
# through Claude instead (needs ANTHROPIC_API_KEY — see .env.example). `run-llm`/`refine-llm` are aliases.
NOLLM := --no-llm
ifdef LLM
NOLLM :=
endif

install: ## editable-install caliper into the env (makes the `caliper` command available)
	$(CALIPER_PY) -m pip install -e ".[dev]"

run:    ## run on an intent: make run INTENT="a 60mm bracket ... four M5 holes"  [LLM=1 → Claude path]
	$(CALIPER_PY) -m caliper.cli run "$(INTENT)" $(NOLLM) --yes

gen:    ## LLM-authored generator (any part): make gen INTENT="a phone stand for a 7mm-thick phone"
	$(CALIPER_PY) -m caliper.cli gen "$(INTENT)" --yes

refine: ## refine a prior run: make refine SOURCE=runs/run_0000 INSTRUCTION="..."  [LLM=1 → Claude path]
	$(CALIPER_PY) -m caliper.cli refine "$(SOURCE)" "$(INSTRUCTION)" $(NOLLM)

run-llm:    ## run via the Claude LLM path (needs ANTHROPIC_API_KEY): make run-llm INTENT="..."
	@$(MAKE) run LLM=1 INTENT="$(INTENT)"

refine-llm: ## refine via Claude: make refine-llm SOURCE=runs/run_0000 INSTRUCTION="..."
	@$(MAKE) refine LLM=1 SOURCE="$(SOURCE)" INSTRUCTION="$(INSTRUCTION)"

fit:    ## fit a prior part to a reference STL: make fit SOURCE=runs/run_0000 REF=obstacle=examples/obstacle.stl [CLEAR=2]
	$(CALIPER_PY) -m caliper.cli fit "$(SOURCE)" --ref "$(or $(REF),obstacle=examples/obstacle.stl)" $(if $(CLEAR),--min-clearance $(CLEAR),)

assemble: ## measure a multi-part assembly: make assemble ASM=examples/assembly.yaml
	$(CALIPER_PY) -m caliper.cli assemble "$(or $(ASM),examples/assembly.yaml)"

insert: ## author a part between two interfaces (needs ANTHROPIC_API_KEY): make insert
	$(CALIPER_PY) -m caliper.cli insert "$(or $(ASM),examples/insert_demo.yaml)" \
		--between "$(or $(BETWEEN),post_left,post_right)" --as "$(or $(AS),crossbar)" \
		--intent "$(or $(INTENT),a cross-bar)" --fit "$(or $(FIT),slip)" \
		--save "$(or $(SAVE),examples/inserted.yaml)"

serve:  ## launch the webapp (3D viewer + refine loop): make serve  [PORT=8000]
	$(CALIPER_PY) -m caliper.cli serve --port $(or $(PORT),8000)

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
