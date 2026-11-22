# LaTeX row-input regression check

The original `table09_rows.tex` has 21 correctly terminated rows, including its final row. A minimal article using booktabs with `\input{table09_rows.tex}` followed by `\bottomrule` reproduces `Misplaced \noalign` under Tectonic 0.15.0 / TeX Live 2022 bundle. Replacing the input with `\TableRows`, defined as `\newcommand{\TableRows}[1]{\csname @@input\endcsname{#1}}`, builds a PDF successfully with the same row contents.

Fourteen row-fragment inputs in `rev1.tex` now use the primitive wrapper. Complete-table and preamble inputs retain normal LaTeX input. The source checker and Overleaf packager recognize both commands. The generated row data and numerical values are unchanged.

Full marked and clean manuscripts subsequently compiled successfully with Tectonic 0.15.0. Outputs: `rev1.pdf` and `rev_clean.pdf`; logs: `marked_build.log`, `clean_build.log`. Remaining warnings concern box layout and bibliography metadata; PDF layout review remains separate.
