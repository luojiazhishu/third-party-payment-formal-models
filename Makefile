SHELL := /bin/bash
PY ?= python3

MODELS_DIR  := models
RUN_DIR     := scripts
RESULTS_DIR := results

# Parallelism passed to run.py (-j). Override on the CLI: make verify JOBS=12
JOBS ?= 4

RUN_SCRIPT   := $(RUN_DIR)/run.py
FIX_SCRIPT   := $(RUN_DIR)/fix.py
PARSE_SCRIPT := $(RUN_DIR)/parse.py

# verify -> fix -> parse have a strict order; never run them in parallel.
.NOTPARALLEL:

.PHONY: help print-config verify fix parse all clean

help:
	@echo "make all : verify -> fix -> parse(per results/*)"
	@echo ""
	@$(MAKE) --no-print-directory print-config

print-config:
	@echo "---- Current configuration ----"
	@echo "PY          = $(PY)"
	@echo "MODELS_DIR  = $(MODELS_DIR)"
	@echo "RUN_DIR     = $(RUN_DIR)"
	@echo "RESULTS_DIR = $(RESULTS_DIR)"
	@echo "JOBS        = $(JOBS)"
	@echo "Scripts     = $(RUN_SCRIPT), $(FIX_SCRIPT), $(PARSE_SCRIPT)"
	@echo "--------------------------------"

# 1) run.py: run all models in models/ -> results/
verify:
	@echo "[STEP] verify"
	$(PY) $(RUN_SCRIPT) -d $(MODELS_DIR) -j $(JOBS) -o $(RESULTS_DIR)

# 2) fix.py: recursively fix all .spthy under results/
fix: verify
	@echo "[STEP] fix"
	$(PY) $(FIX_SCRIPT) $(RESULTS_DIR)

parse: fix
	@echo "[STEP] parse"
	$(PY) $(PARSE_SCRIPT) -r=$(RESULTS_DIR) --csv

all: print-config parse
	@echo ""
	@echo "[DONE] Pipeline completed."
	@echo "  Results root: $(RESULTS_DIR)"

clean:
	rm -rf $(RESULTS_DIR) log/ run.log
