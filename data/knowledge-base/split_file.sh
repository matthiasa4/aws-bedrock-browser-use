#!/bin/bash

# Function to display usage
usage() {
    echo "Usage: $0 <input_file> [lines_per_file] [output_prefix]"
    echo ""
    echo "Arguments:"
    echo "  input_file      - The CSV file to split (required)"
    echo "  lines_per_file  - Number of lines per split file (default: 10000)"
    echo "  output_prefix   - Prefix for output files (default: based on input filename)"
    echo ""
    echo "Example:"
    echo "  $0 cve.csv 5000 cve_split_"
    echo "  $0 data.csv"
    exit 1
}

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    echo "Error: Input file is required"
    usage
fi

# Parse arguments
INPUT_FILE="$1"
LINES_PER_FILE="${2:-10000}"
OUTPUT_PREFIX="${3:-$(basename "$INPUT_FILE" .csv)_part_}"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' does not exist"
    exit 1
fi

# Create temporary header file
HEADER_FILE="header_$(basename "$INPUT_FILE")"

echo "Splitting '$INPUT_FILE' into files with $LINES_PER_FILE lines each..."
echo "Output prefix: $OUTPUT_PREFIX"

# Count header line first
head -n 1 "$INPUT_FILE" > "$HEADER_FILE"

# Now split body into files with specified number of lines each
tail -n +2 "$INPUT_FILE" | split -l "$LINES_PER_FILE" - "$OUTPUT_PREFIX"

# Prepend header to each part
for file in ${OUTPUT_PREFIX}*; do
    # Skip if no files match the pattern
    [ -e "$file" ] || continue
    
    cat "$HEADER_FILE" "$file" > "${file}.csv"
    rm "$file"
done

# Clean up temporary header file
rm "$HEADER_FILE"

echo "Split complete! Created files: ${OUTPUT_PREFIX}*.csv"
