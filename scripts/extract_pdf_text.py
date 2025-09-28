#!/usr/bin/env python3
"""
Script to extract text from PDF files using the preprocessing utilities.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the parent directory to the path to import utils
sys.path.append(str(Path(__file__).parent.parent))

from utils.preprocess import extract_text_from_pdf, clean_basic_artifacts, clean_structure, NumberNormalizer


def parse_arguments():
    parser = argparse.ArgumentParser(description='Extract text from PDF files and save as text files.')
    parser.add_argument('pdf_file', help='Path to the PDF file to process')
    parser.add_argument('-o', '--output_path', help='Output text file path')
    parser.add_argument('-m', '--method', choices=['auto', 'pdfplumber', 'pymupdf', 'pypdf'],
                        default='plumber', help='Extraction method to use (default: plumber)')
    parser.add_argument('--no-clean', action='store_true', help='Skip text cleaning steps')
    return parser.parse_args()


def main():
    args = parse_arguments()

    pdf_file = args.pdf_file

    # Check if PDF file exists
    if not os.path.exists(pdf_file):
        print(f"Error: PDF file '{pdf_file}' not found.")
        sys.exit(1)

    # Determine output file path
    output_file = None
    if args.output_path:
        output_file = args.output_path
        
    try:
        # Extract text from PDF
        print(f"Extracting text from {pdf_file} using method: {args.method}")
        raw_text = extract_text_from_pdf(pdf_file, method=args.method)

        if not args.no_clean:
            # Clean the text
            print("Cleaning basic artifacts...")
            cleaned_text = clean_basic_artifacts(raw_text)

            print("Cleaning structure...")
            cleaned_text = clean_structure(cleaned_text)

            # Normalize numbers
            print("Normalizing numbers...")
            normalizer = NumberNormalizer()
            final_text = normalizer.normalize_numbers(cleaned_text)
            final_text = normalizer.normalize_list_markers(final_text)

            # Collapse lines
            final_text = final_text.replace('\n', ' ').replace('  ', ' ')

        else:
            final_text = raw_text

        # Output the result
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_text)
            print(f"Extracted text saved to {output_file}")
        else:
            print("\n" + "="*50)
            print("EXTRACTED TEXT:")
            print("="*50)
            print(final_text)

        print(f"\nExtraction completed successfully!")
        print(f"Text length: {len(final_text)} characters")

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()