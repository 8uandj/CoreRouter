PYTHON ?= python3

.PHONY: paper-data check-paper
paper-data:
	$(PYTHON) scripts/paper/make_table11.py
	$(PYTHON) scripts/paper/make_ablation_tables.py
	$(PYTHON) scripts/rev1/summarize_mentor_statistics.py
	$(PYTHON) scripts/paper/make_numbers.py
	$(PYTHON) scripts/paper/make_qos_table.py
	$(PYTHON) scripts/paper/make_load_sweep_figure.py
	$(PYTHON) scripts/paper/make_architecture_figures.py

check-paper:
	$(PYTHON) scripts/paper/check_tex_inputs.py
	$(PYTHON) scripts/check_manifest.py
