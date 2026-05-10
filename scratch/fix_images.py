import glob
import os

files = glob.glob("infrastructure/k8s/manifests/*.yaml")
files.append("infrastructure/k8s/tekton/pipeline-migrate-single-vnf.yaml")

for fpath in files:
    try:
        with open(fpath, "r") as f:
            lines = f.readlines()
            
        changed = False
        new_lines = []
        for line in lines:
            if "image:" in line and "localhost:32000/" not in line:
                # find the image part
                parts = line.split("image:")
                prefix = parts[0]
                image = parts[1].strip().strip("\"'")
                base_image = image.split("/")[-1]
                new_line = f"{prefix}image: localhost:32000/{base_image}\n"
                new_lines.append(new_line)
                changed = True
            else:
                new_lines.append(line)
                
        if changed:
            with open(fpath, "w") as f:
                f.writelines(new_lines)
            print(f"Updated {fpath}")
    except Exception as e:
        print(f"Skipped {fpath}: {e}")
