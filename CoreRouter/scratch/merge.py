import os

thesis_file = "/home/hung8uandj/Study/CoreRouter/docs/thesis_latex/myThesis.tex"
new_chapters = "/home/hung8uandj/Study/CoreRouter/scratch/new_chapters.tex"
merged_file = "/home/hung8uandj/Study/CoreRouter/docs/thesis_latex/myThesis.tex.tmp"

with open(thesis_file, "r") as f:
    lines = f.readlines()

# keep up to line 447 (index 446)
head_lines = lines[:447]

with open(new_chapters, "r") as f:
    new_lines = f.readlines()

with open(merged_file, "w") as f:
    f.writelines(head_lines)
    f.writelines(new_lines)

os.rename(merged_file, thesis_file)
print("Merge successful.")
