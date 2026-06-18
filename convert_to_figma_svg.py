#!/usr/bin/env python3
import argparse
import base64
import os
import re
import subprocess
import sys
from pathlib import Path
from PIL import Image

def clean_svg_for_figma(svg_path: Path):
    """Post-processes an SVG file to make it 100% compatible with Figma.
    
    1. Removes <?xml ... ?> and <!DOCTYPE ... > declarations.
    2. Strips "pt" units from the width and height attributes in the main <svg> tag.
    """
    if not svg_path.exists():
        return
        
    content = svg_path.read_text(encoding="utf-8")
    
    # 1. Remove XML declaration and DOCTYPE (known to fail Figma SVG imports)
    content = re.sub(r'<\?xml[^>]*\?>\s*', '', content)
    content = re.sub(r'<!DOCTYPE[^>]*>\s*', '', content, flags=re.DOTALL)
    
    # 2. Strip "pt" units from width and height in the main <svg> tag
    content = re.sub(r'(<svg[^>]*\s+width="[\d.]+)(pt)(")', r'\1\3', content)
    content = re.sub(r'(<svg[^>]*\s+height="[\d.]+)(pt)(")', r'\1\3', content)
    
    svg_path.write_text(content, encoding="utf-8")

def convert_pdf_to_svg(pdf_path: Path, out_path: Path):
    """Converts a vector PDF to a vector SVG using pdftocairo and cleans it for Figma."""
    print(f"Converting PDF: {pdf_path} -> SVG: {out_path} using pdftocairo...")
    try:
        # Run pdftocairo to export vector SVG
        cmd = ["pdftocairo", "-svg", str(pdf_path), str(out_path)]
        subprocess.run(cmd, check=True)
        
        # Post-process for Figma compatibility
        clean_svg_for_figma(out_path)
        print(f"Successfully converted and optimized: {out_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during pdftocairo conversion: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'pdftocairo' command not found. Please install poppler-utils.", file=sys.stderr)
        sys.exit(1)

def convert_raster_to_svg(img_path: Path, out_path: Path, mime_type: str):
    """Wraps a raster PNG/JPG image into an SVG shell with Base64 encoding for Figma import."""
    print(f"Wrapping raster image: {img_path} -> SVG: {out_path}...")
    try:
        # Get dimensions
        with Image.open(img_path) as img:
            width, height = img.size
            
        # Encode image to base64
        img_data = img_path.read_bytes()
        b64_data = base64.b64encode(img_data).decode("utf-8")
        
        # Build SVG template
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
            f'  <image width="{width}" height="{height}" href="data:{mime_type};base64,{b64_data}"/>\n'
            f'</svg>\n'
        )
        
        # Save SVG
        out_path.write_text(svg_content, encoding="utf-8")
        print(f"Successfully wrapped image into vector shell: {out_path}")
    except Exception as e:
        print(f"Error wrapping raster image: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Convert any PDF or PNG/JPG file to a Figma-compatible SVG."
    )
    parser.add_argument(
        "file_path", 
        type=str, 
        help="Path to the input PDF or image file (PNG, JPG, JPEG)."
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default=None, 
        help="Custom path for the output SVG file. (Default: same name as input with .svg extension)"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.file_path).resolve()
    if not input_path.exists():
        print(f"Error: File '{args.file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Output path resolution
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_suffix(".svg")
        
    # Check extension
    suffix = input_path.suffix.lower()
    
    if suffix == ".pdf":
        convert_pdf_to_svg(input_path, output_path)
    elif suffix == ".png":
        convert_raster_to_svg(input_path, output_path, "image/png")
    elif suffix in [".jpg", ".jpeg"]:
        convert_raster_to_svg(input_path, output_path, "image/jpeg")
    else:
        print(f"Error: Unsupported file type '{suffix}'. Supported formats are: .pdf, .png, .jpg, .jpeg", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
