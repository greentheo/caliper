# Caliper — dev entrypoints. The loop is the product; these keep the dev loop tight.
# No activation needed: targets resolve the env python (override with CALIPER_PY=...).
.PHONY: test review loop board fmt run gen refine run-llm refine-llm fit serve install tools

CALIPER_PY ?= $(firstword $(wildcard /opt/anaconda3/envs/caliper/bin/python $(HOME)/anaconda3/envs/caliper/bin/python $(HOME)/miniforge3/envs/caliper/bin/python) python)

# Intake/refine use the deterministic OFFLINE parser by default (reproducible). Pass LLM=1 to route
# through Claude instead (needs ANTHROPIC_API_KEY — see .env.example). `run-llm`/`refine-llm` are aliases.
NOLLM := --no-llm
ifdef LLM
NOLLM :=
endif

install: ## editable-install caliper into the env (makes the `caliper` command available)
	$(CALIPER_PY) -m pip install -e ".[dev]"

# The optional tools, pinned. Bump a ref deliberately (and let CI prove it). Your own checkouts are left
# alone: an editable whittle install, or vendor/unfold-to-sheets as a symlink to a checkout you work in.
WHITTLE_REF ?= 5363df559c355aa3934ad25d00e110c98ca4814a
UNFOLD_REF  ?= 8fc66c9419643da5b2f448014bc6fc20d2db07cd

tools:  ## optional tools: whittle (studies) into the env, unfold-to-sheets (cut plans, on node) into vendor/
	@if $(CALIPER_PY) -m pip show whittle 2>/dev/null | grep -q '^Editable project location'; then \
		echo "whittle: an editable install of your own checkout, left as is"; \
	else $(CALIPER_PY) -m pip install -q "whittle @ git+https://github.com/greentheo/whittle.git@$(WHITTLE_REF)"; fi
	@if [ -L vendor/unfold-to-sheets ]; then \
		echo "unfold-to-sheets: vendor/ links to your own checkout, left as is"; \
	else [ -e vendor/unfold-to-sheets ] || git clone -q https://github.com/greentheo/unfold-to-sheets.git vendor/unfold-to-sheets; \
		git -C vendor/unfold-to-sheets fetch -q origin && git -C vendor/unfold-to-sheets checkout -q $(UNFOLD_REF); fi
	@command -v node >/dev/null || echo "note: cut plans also need node (https://nodejs.org)"

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
