# CVE Data Processing Script

These scripts process CVE (Common Vulnerabilities and Exposures) data from the CVE Project repository and filters it for web-relevant vulnerabilities to create a knowledge base for cybersecurity reconnaissance.

## Overview

The `CVE_data_processing.py` script:

- Processes CVE data from the official [CVE Project repository](https://github.com/CVEProject/cvelistV5.git)
- Intelligently filters for web-relevant vulnerabilities using multiple criteria including network attack vectors (CVSS), web-related products (apache, nginx, wordpress, etc.), and web-specific vulnerability types (XSS, SQL injection, CSRF, etc.)
- Extracts structured data including impact descriptions, CVSS metrics, and references
- Outputs CSV format suitable for ingestion into an Amazon Bedrock Knowledge Base and agent contextualization

This filtered dataset enables agents to access targeted vulnerability intelligence rather at runtime, and was aimed at demonstrating how knowledge bases can provide domain-specific context to improve agent effectiveness in specialized tasks, rather than being complete.

Due to AWS Bedrock Knowledge Base's **50MB file size limit** ([AWS documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-ds.html)), large CSV files need to be split before upload. This is done through `split_file.sh`

## Usage

### Basic Usage

Process web-relevant CVEs from 2020 onwards:

```bash
python3 CVE_data_processing.py
```

### Command Line Options

```bash
python3 CVE_data_processing.py [OPTIONS]
```

**Options:**

- `--input-dir PATH` - Path to CVE directory (default: `./cvelistV5`)
- `--output-file FILE` - Output CSV file path (default: `processed_cves_for_bedrock.csv`)
- `--start-year YEAR` - Only process CVEs from this year onwards (default: 2020)
- `--max-files N` - Maximum number of files to process (default: unlimited)
- `--max-relevant N` - Maximum number of web-relevant CVEs to output (default: unlimited)

### Examples

**Process 100 web-relevant CVEs from 2022:**

```bash
python3 CVE_data_processing.py --start-year 2022 --max-relevant 100
```

**Process all CVEs from 2024:**

```bash
python3 CVE_data_processing.py --start-year 2024
```

**Use custom input/output paths:**

```bash
python3 CVE_data_processing.py --input-dir /path/to/cvelistV5 --output-file my_cves.csv
```

## Output Format

The script outputs data in CSV format with the following 9 columns:

- `id` - Unique identifier (same as cve_id)
- `content` - Full formatted CVE description with all details
- `cve_id` - CVE identifier (e.g., CVE-2023-12345)
- `severity` - CVSS severity level (LOW/MEDIUM/HIGH/CRITICAL/Unknown)
- `base_score` - CVSS base score (0.0-10.0)
- `attack_vector` - Attack vector (NETWORK/ADJACENT_NETWORK/LOCAL/PHYSICAL/Unknown)
- `exploit_available` - Whether exploits are publicly available (true/false)
- `patch_available` - Whether patches/fixes are available (true/false)
- `published_date` - Date the CVE was published (ISO format)


## Results

Full processing of the entire CVE database (as of 2025-06-11):

**Command:**

```bash
python3 knowledge-base/CVE_data_processing.py --output-file=knowledge-base/processed_cves_for_bedrock.csv --start-year 1999
```

**Results:**

```
Completed processing. 67997 web-relevant CVEs extracted from 297701 total files.
Web relevance rate: 22.8%
Processed CVE data saved to knowledge-base/processed_cves_for_bedrock.csv
```

This processed **67,997 web-relevant CVEs** from a total of **297,701 CVE files**, achieving a **22.8% web relevance rate**.