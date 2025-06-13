#!/usr/bin/env python3
"""
CVE Data Processor for Cybersecurity Reconnaissance Agent
Filters and extracts web-relevant vulnerability data for Bedrock Knowledge Base
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessedCVE:
    """Structured CVE data for reconnaissance"""

    cve_id: str
    title: str
    description: str
    severity: str
    base_score: float
    attack_vector: str
    attack_complexity: str
    privileges_required: str
    user_interaction: str
    affected_products: list[dict[str, str]]
    cwe_ids: list[str]
    exploit_available: bool
    patch_available: bool
    references: list[dict[str, str]]
    published_date: str
    updated_date: str
    impact_descriptions: list[str]

    def to_document(self) -> str:
        """Convert to searchable document format for Bedrock"""
        doc = f"CVE ID: {self.cve_id}\n"
        doc += f"Title: {self.title}\n" if self.title else ""
        doc += f"Severity: {self.severity} (Score: {self.base_score})\n"
        doc += f"Description: {self.description}\n\n"

        doc += "Attack Details:\n"
        doc += f"- Vector: {self.attack_vector}\n"
        doc += f"- Complexity: {self.attack_complexity}\n"
        doc += f"- Privileges: {self.privileges_required}\n"
        doc += f"- User Interaction: {self.user_interaction}\n\n"

        if self.affected_products:
            doc += "Affected Products:\n"
            for product in self.affected_products:
                vendor = product["vendor"]
                product_name = product["product"]
                version = product.get("version", "N/A")
                doc += f"- {vendor} {product_name} {version}\n"
            doc += "\n"

        if self.cwe_ids:
            doc += f"Weakness Types (CWE): {', '.join(self.cwe_ids)}\n\n"

        if self.impact_descriptions:
            doc += "Impact:\n"
            for impact in self.impact_descriptions:
                doc += f"- {impact}\n"
            doc += "\n"

        doc += f"Exploit Available: {'Yes' if self.exploit_available else 'No'}\n"
        doc += f"Patch Available: {'Yes' if self.patch_available else 'No'}\n"
        doc += f"Published: {self.published_date}\n"
        doc += f"Updated: {self.updated_date}\n\n"

        if self.references:
            doc += "References:\n"
            for ref in self.references[:5]:  # Limit for brevity
                doc += f"- {ref['name']}: {ref['url']}\n"

        return doc

    def to_csv_row(self) -> dict[str, str]:
        """Convert to CSV row format - matches JSON structure exactly
        (id + content + metadata fields)
        """

        def sanitize_field(text: str) -> str:
            """Remove newlines and normalize whitespace for CSV compatibility"""
            if not text:
                return ""
            # Replace newlines and multiple whitespace with single space
            return " ".join(text.replace("\n", " ").replace("\r", " ").split())

        return {
            # Main fields matching JSON structure
            "id": sanitize_field(self.cve_id),
            "content": sanitize_field(self.to_document()),
            # Metadata fields matching JSON structure
            "cve_id": sanitize_field(self.cve_id),
            "severity": sanitize_field(self.severity),
            "base_score": str(self.base_score),
            "attack_vector": sanitize_field(self.attack_vector),
            "exploit_available": "true" if self.exploit_available else "false",
            "patch_available": "true" if self.patch_available else "false",
            "published_date": sanitize_field(self.published_date),
        }


class CVEProcessor:
    """Processes CVE JSON data for reconnaissance agent use"""

    # Web-relevant product keywords
    WEB_PRODUCTS = {
        "apache",
        "nginx",
        "iis",
        "tomcat",
        "jetty",
        "jboss",
        "websphere",
        "wordpress",
        "drupal",
        "joomla",
        "magento",
        "shopify",
        "django",
        "flask",
        "rails",
        "spring",
        "express",
        "fastapi",
        "react",
        "angular",
        "vue",
        "node.js",
        "php",
        "laravel",
        "mysql",
        "postgresql",
        "mongodb",
        "redis",
        "elasticsearch",
        "docker",
        "kubernetes",
        "jenkins",
        "gitlab",
        "github",
    }

    # Web-relevant CWE IDs
    WEB_CWES = {
        "CWE-79",  # XSS
        "CWE-89",  # SQL Injection
        "CWE-22",  # Path Traversal
        "CWE-352",  # CSRF
        "CWE-78",  # OS Command Injection
        "CWE-94",  # Code Injection
        "CWE-287",  # Authentication Bypass
        "CWE-863",  # Authorization Issues
        "CWE-434",  # File Upload
        "CWE-502",  # Deserialization
        "CWE-611",  # XXE
        "CWE-918",  # SSRF
        "CWE-200",  # Information Disclosure
        "CWE-601",  # Open Redirect
    }

    def is_web_relevant(self, cve_data: dict) -> bool:
        """Determine if CVE is relevant for web reconnaissance"""
        # Check CVSS attack vector
        if self._has_network_attack_vector(cve_data):
            return True

        # Check affected products
        if self._has_web_products(cve_data):
            return True

        # Check CWE mappings
        return bool(self._has_web_cwes(cve_data))

    def _has_network_attack_vector(self, cve_data: dict) -> bool:
        """Check if CVE has network attack vector"""
        containers = cve_data.get("containers", {})
        cna = containers.get("cna", {})
        metrics = cna.get("metrics", [])

        for metric in metrics:
            for cvss_version in ["cvssV4_0", "cvssV3_1", "cvssV3_0"]:
                if cvss_version in metric:
                    attack_vector = metric[cvss_version].get("attackVector", "")
                    if attack_vector == "NETWORK":
                        return True
        return False

    def _has_web_products(self, cve_data: dict) -> bool:
        """Check if CVE affects web-related products"""
        containers = cve_data.get("containers", {})
        cna = containers.get("cna", {})
        affected = cna.get("affected", [])

        for product_info in affected:
            vendor = product_info.get("vendor", "").lower()
            product = product_info.get("product", "").lower()

            # Check against web product keywords
            for keyword in self.WEB_PRODUCTS:
                if keyword in vendor or keyword in product:
                    return True

            # Check CPE strings for web technologies
            cpes = product_info.get("cpes", [])
            for cpe in cpes:
                if any(keyword in cpe.lower() for keyword in self.WEB_PRODUCTS):
                    return True
        return False

    def _has_web_cwes(self, cve_data: dict) -> bool:
        """Check if CVE has web-relevant CWE mappings"""
        containers = cve_data.get("containers", {})
        cna = containers.get("cna", {})
        problem_types = cna.get("problemTypes", [])

        for problem_type in problem_types:
            descriptions = problem_type.get("descriptions", [])
            for desc in descriptions:
                cwe_id = desc.get("cweId", "")
                if cwe_id in self.WEB_CWES:
                    return True
        return False

    def extract_cve_data(self, cve_data: dict) -> ProcessedCVE | None:
        """Extract relevant fields from CVE JSON"""
        if not self.is_web_relevant(cve_data):
            return None

        try:
            # Basic metadata
            metadata = cve_data.get("cveMetadata", {})
            cve_id = metadata.get("cveId", "")
            published_date = metadata.get("datePublished", "")
            updated_date = metadata.get("dateUpdated", "")

            # Container data
            containers = cve_data.get("containers", {})
            cna = containers.get("cna", {})

            # Description
            descriptions = cna.get("descriptions", [])
            description = descriptions[0].get("value", "") if descriptions else ""
            title = cna.get("title", "")

            # CVSS metrics
            severity, base_score, attack_details = self._extract_cvss_data(cna)

            # Affected products
            affected_products = self._extract_affected_products(cna)

            # CWE mappings
            cwe_ids = self._extract_cwe_ids(cna)

            # References and exploit info
            references, exploit_available, patch_available = self._extract_references(cna)

            # Impact descriptions
            impact_descriptions = self._extract_impact_descriptions(cve_data)

            return ProcessedCVE(
                cve_id=cve_id,
                title=title,
                description=description,
                severity=severity,
                base_score=base_score,
                attack_vector=attack_details.get("attackVector", "Unknown"),
                attack_complexity=attack_details.get("attackComplexity", "Unknown"),
                privileges_required=attack_details.get("privilegesRequired", "Unknown"),
                user_interaction=attack_details.get("userInteraction", "Unknown"),
                affected_products=affected_products,
                cwe_ids=cwe_ids,
                exploit_available=exploit_available,
                patch_available=patch_available,
                references=references,
                published_date=published_date,
                updated_date=updated_date,
                impact_descriptions=impact_descriptions,
            )

        except Exception as e:
            cve_id = cve_data.get("cveMetadata", {}).get("cveId", "Unknown")
            print(f"Error processing CVE {cve_id}: {e}")
            return None

    def _extract_cvss_data(self, cna: dict) -> tuple:
        """Extract CVSS severity and attack details"""
        metrics = cna.get("metrics", [])

        for metric in metrics:
            # Prefer newer CVSS versions
            for cvss_version in ["cvssV4_0", "cvssV3_1", "cvssV3_0", "cvssV2_0"]:
                if cvss_version in metric:
                    cvss_data = metric[cvss_version]
                    severity = cvss_data.get("baseSeverity", "Unknown")
                    base_score = cvss_data.get("baseScore", 0.0)

                    attack_details = {
                        "attackVector": cvss_data.get("attackVector", "Unknown"),
                        "attackComplexity": cvss_data.get("attackComplexity", "Unknown"),
                        "privilegesRequired": cvss_data.get("privilegesRequired", "Unknown"),
                        "userInteraction": cvss_data.get("userInteraction", "Unknown"),
                    }

                    return severity, base_score, attack_details

        return "Unknown", 0.0, {}

    def _extract_affected_products(self, cna: dict) -> list[dict[str, str]]:
        """Extract affected product information"""
        affected = cna.get("affected", [])
        products = []

        for product_info in affected:
            vendor = product_info.get("vendor", "Unknown")
            product = product_info.get("product", "Unknown")

            # Extract version info
            versions = product_info.get("versions", [])
            version_list = []
            for version in versions[:3]:  # Limit to first 3 versions
                version_list.append(version.get("version", ""))

            products.append(
                {
                    "vendor": vendor,
                    "product": product,
                    "version": ", ".join(version_list) if version_list else "N/A",
                }
            )

        return products

    def _extract_cwe_ids(self, cna: dict) -> list[str]:
        """Extract CWE IDs"""
        problem_types = cna.get("problemTypes", [])
        cwe_ids = []

        for problem_type in problem_types:
            descriptions = problem_type.get("descriptions", [])
            for desc in descriptions:
                cwe_id = desc.get("cweId", "")
                if cwe_id and cwe_id not in cwe_ids:
                    cwe_ids.append(cwe_id)

        return cwe_ids

    def _extract_references(self, cna: dict) -> tuple:
        """Extract references and determine exploit/patch availability"""
        references_data = cna.get("references", [])
        references = []
        exploit_available = False
        patch_available = False

        for ref in references_data:
            url = ref.get("url", "")
            name = ref.get("name", url)
            tags = ref.get("tags", [])

            references.append({"name": name, "url": url, "tags": tags})

            # Check for exploit/patch indicators
            if "exploit" in tags:
                exploit_available = True
            if "patch" in tags or "vendor-advisory" in tags:
                patch_available = True

        return references, exploit_available, patch_available

    def _extract_impact_descriptions(self, cve_data: dict) -> list[str]:
        """Extract impact descriptions from both CNA and ADP containers"""
        impact_descriptions = []
        containers = cve_data.get("containers", {})

        # Extract from CNA container
        cna = containers.get("cna", {})
        cna_impacts = cna.get("impacts", [])
        for impact in cna_impacts:
            descriptions = impact.get("descriptions", [])
            for desc in descriptions:
                value = desc.get("value", "").strip()
                if value and value not in impact_descriptions:
                    impact_descriptions.append(value)

        # Extract from ADP container(s)
        adp_list = containers.get("adp", [])
        for adp in adp_list:
            adp_impacts = adp.get("impacts", [])
            for impact in adp_impacts:
                descriptions = impact.get("descriptions", [])
                for desc in descriptions:
                    value = desc.get("value", "").strip()
                    if value and value not in impact_descriptions:
                        impact_descriptions.append(value)

        return impact_descriptions


def analyze_cve_directory(input_dir: Path, start_year: int = 2020) -> dict[str, int]:
    """Analyze CVE directory to show statistics before processing"""
    cves_dir = input_dir / "cves"
    if not cves_dir.exists():
        print(f"CVEs directory not found at {cves_dir}")
        return {}

    stats = {
        "total_years": 0,
        "total_files": 0,
        "years_to_process": 0,
        "files_to_process": 0,
    }

    for year_dir in sorted(cves_dir.iterdir()):
        if not year_dir.is_dir():
            continue

        try:
            year = int(year_dir.name)
            stats["total_years"] += 1

            # Count files in this year
            year_files = 0
            for range_dir in year_dir.iterdir():
                if range_dir.is_dir():
                    year_files += len(list(range_dir.glob("CVE-*.json")))

            stats["total_files"] += year_files

            if year >= start_year:
                stats["years_to_process"] += 1
                stats["files_to_process"] += year_files

        except ValueError:
            continue

    return stats


def process_cve_directory(
    input_dir: Path,
    output_file: Path,
    start_year: int = 2020,
    max_files: int | None = None,
    max_relevant_cves: int | None = None,
) -> None:
    """Process CVE directory structure and output documents in CSV format

    Args:
        input_dir: Path to cvelistV5 directory
        output_file: Output CSV file for processed CVEs
        start_year: Only process CVEs from this year onwards (default: 2020)
        max_files: Maximum number of files to process (None for all)
        max_relevant_cves: Maximum number of relevant CVEs to output (None for all)
    """
    processor = CVEProcessor()
    processed_count = 0
    files_processed = 0

    cves_dir = input_dir / "cves"
    if not cves_dir.exists():
        print(f"CVEs directory not found at {cves_dir}")
        return

    # Analyze directory first
    print("Analyzing CVE directory...")
    stats = analyze_cve_directory(input_dir, start_year)
    print(f"Found {stats['total_files']} total CVE files across {stats['total_years']} years")
    print(
        f"Will process {stats['files_to_process']} files from "
        f"{stats['years_to_process']} years (starting from {start_year})"
    )

    if max_files:
        print(f"Limited to processing maximum {max_files} files")

    if max_relevant_cves:
        print(f"Will stop after finding {max_relevant_cves} web-relevant CVEs")

    print(f"Processing CVE data from {cves_dir}")
    print(f"Output will be saved to {output_file}")

    with open(output_file, "w", encoding="utf-8") as out_f:
        # Initialize CSV writer
        csv_writer = csv.DictWriter(
            out_f,
            fieldnames=[
                "id",
                "content",
                "cve_id",
                "severity",
                "base_score",
                "attack_vector",
                "exploit_available",
                "patch_available",
                "published_date",
            ],
        )
        csv_headers_written = False

        # Iterate through year directories
        for year_dir in sorted(cves_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            try:
                year = int(year_dir.name)
                if year < start_year:
                    continue
            except ValueError:
                continue

            print(f"Processing year {year}...")

            # Iterate through range directories (0xxx, 1xxx, etc.)
            for range_dir in sorted(year_dir.iterdir()):
                if not range_dir.is_dir():
                    continue

                # Process all JSON files in the range directory
                json_files = list(range_dir.glob("CVE-*.json"))

                for json_file in json_files:
                    if max_files and files_processed >= max_files:
                        print(f"Reached maximum file limit of {max_files}")
                        break

                    if max_relevant_cves and processed_count >= max_relevant_cves:
                        print(f"Reached target of {max_relevant_cves} web-relevant CVEs")
                        break

                    try:
                        with open(json_file, encoding="utf-8") as f:
                            cve_data = json.load(f)
                            processed_cve = processor.extract_cve_data(cve_data)

                            files_processed += 1

                            if processed_cve:
                                # Write CSV header on first row
                                if not csv_headers_written:
                                    csv_writer.writeheader()
                                    csv_headers_written = True

                                # Write CSV row
                                csv_writer.writerow(processed_cve.to_csv_row())
                                processed_count += 1

                                if processed_count % 10 == 0:
                                    print(
                                        f"Processed {processed_count} web-relevant CVEs from "
                                        f"{files_processed} files..."
                                    )

                    except json.JSONDecodeError as e:
                        print(f"JSON decode error in {json_file}: {e}")
                        continue
                    except Exception as e:
                        print(f"Error processing {json_file}: {e}")
                        continue

                if max_files and files_processed >= max_files:
                    break

                if max_relevant_cves and processed_count >= max_relevant_cves:
                    break

            if max_files and files_processed >= max_files:
                break

            if max_relevant_cves and processed_count >= max_relevant_cves:
                break

    print(
        f"Completed processing. {processed_count} web-relevant CVEs extracted from "
        f"{files_processed} total files."
    )
    print(
        f"Web relevance rate: {(processed_count / files_processed * 100):.1f}%"
        if files_processed > 0
        else "No files processed"
    )


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="CVE Data Processor for Cybersecurity Reconnaissance Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process CVEs from 2020 onwards
  python3 CVE_data_processing.py

  # Process all CVEs from 2022 onwards
  python3 CVE_data_processing.py --start-year 2022

  # Process maximum 100 relevant CVEs from custom directory
  python3 CVE_data_processing.py --input-dir /path/to/cvelistV5 --max-relevant 100

  # Process maximum 1000 files from 2023
  python3 CVE_data_processing.py --start-year 2023 --max-files 1000

  # Specify custom output file
  python3 CVE_data_processing.py --output-file my_cves.csv --max-relevant 100
        """,
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default="./cvelistV5",
        help="Path to CVE directory (default: ./cvelistV5)",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default="processed_cves_for_bedrock.csv",
        help="Output CSV file path (default: processed_cves_for_bedrock.csv)",
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2020,
        help="Only process CVEs from this year onwards (default: 2020)",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to process (default: no limit)",
    )

    parser.add_argument(
        "--max-relevant",
        type=int,
        default=None,
        help="Maximum number of web-relevant CVEs to output (default: no limit)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Configuration from arguments
    cve_directory = Path(args.input_dir)
    output_file = Path(args.output_file)
    start_year = args.start_year
    max_files_to_process = args.max_files
    max_relevant_cves = args.max_relevant

    print("CVE Data Processor - Configuration:")
    print(f"  Input directory: {cve_directory}")
    print(f"  Output file: {output_file}")
    print("  Output format: CSV")
    print(f"  Start year: {start_year}")
    print(f"  Max files: {max_files_to_process or 'unlimited'}")
    print(f"  Max relevant CVEs: {max_relevant_cves or 'unlimited'}")
    print()

    # Check if CVE directory exists
    if not cve_directory.exists():
        print(f"CVE directory {cve_directory} not found.")
        print("Clone CVE data from: https://github.com/CVEProject/cvelistV5")
        print("Or specify a different path with --input-dir")
        sys.exit(1)

    # Analyze directory first
    print("Analyzing CVE directory...")
    stats = analyze_cve_directory(cve_directory, start_year)

    # Confirm before processing large amounts
    if stats.get("files_to_process", 0) > 10000:
        response = input(f"About to process {stats['files_to_process']} files. Continue? (y/N): ")
        if response.lower() != "y":
            print("Processing cancelled")
            sys.exit(0)

    # Process CVE directory
    process_cve_directory(
        cve_directory, output_file, start_year, max_files_to_process, max_relevant_cves
    )
    print(f"Processed CVE data saved to {output_file}")
