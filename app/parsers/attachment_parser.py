import csv
import os
from pathlib import Path
from typing import Optional, Tuple

from app.utils.logger import logger
from config.settings import settings


def normalize(text: str) -> str:
    return text.strip().lower()


def identity_score(cell_text: str) -> Tuple[bool, float, str]:
    """
    Returns (found, confidence, matched_identity)
    Checks name variants, register number, email.
    Confidence: 1.0 = exact, 0.8 = case-insensitive, 0.6 = partial
    """
    cell_lower = normalize(cell_text)
    
    # Check register number (highest confidence)
    reg = settings.register_number.lower()
    if reg in cell_lower:
        return True, 1.0, f"Register Number: {settings.register_number}"

    # Check email
    email_addr = settings.college_email.lower()
    if email_addr in cell_lower:
        return True, 1.0, f"Email: {settings.college_email}"

    # Check name variants
    for variant in settings.name_variants_list:
        variant_lower = variant.lower()
        if variant_lower == cell_lower:
            return True, 1.0, f"Exact name: {variant}"
        if variant_lower in cell_lower:
            return True, 0.8, f"Partial name: {variant}"

    return False, 0.0, ""


class AttachmentParser:

    def parse(self, filepath: str) -> dict:
        """Route to correct parser based on file extension."""
        ext = Path(filepath).suffix.lower()
        result = {
            "filepath": filepath,
            "filename": Path(filepath).name,
            "type": ext,
            "identity_found": False,
            "confidence": 0.0,
            "matched_identity": "",
            "matched_row": "",
            "total_rows_scanned": 0,
            "error": None,
        }

        try:
            if ext in (".xlsx", ".xls"):
                self._parse_excel(filepath, result)
            elif ext == ".csv":
                self._parse_csv(filepath, result)
            elif ext == ".pdf":
                self._parse_pdf(filepath, result)
            elif ext == ".txt":
                self._parse_txt(filepath, result)
            else:
                result["error"] = f"Unsupported file type: {ext}"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error parsing {filepath}: {e}")

        if result["identity_found"]:
            logger.info(
                f"🎯 IDENTITY FOUND in {result['filename']} | "
                f"Match: {result['matched_identity']} | "
                f"Confidence: {result['confidence']:.0%}"
            )
        else:
            logger.info(f"❌ Identity NOT found in {result['filename']}")

        return result

    def _parse_excel(self, filepath: str, result: dict):
        import openpyxl

        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        total_rows = 0
        best_confidence = 0.0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            logger.debug(f"Scanning sheet: {sheet_name}")

            for row in ws.iter_rows(values_only=True):
                total_rows += 1
                row_text = " | ".join(str(cell) for cell in row if cell is not None)

                found, confidence, matched = identity_score(row_text)
                if found and confidence > best_confidence:
                    best_confidence = confidence
                    result["identity_found"] = True
                    result["confidence"] = confidence
                    result["matched_identity"] = matched
                    result["matched_row"] = row_text[:200]

                    if confidence == 1.0:
                        break

            if result["identity_found"] and result["confidence"] == 1.0:
                break

        result["total_rows_scanned"] = total_rows
        wb.close()

    def _parse_csv(self, filepath: str, result: dict):
        total_rows = 0
        best_confidence = 0.0

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                total_rows += 1
                row_text = " | ".join(str(cell) for cell in row)
                found, confidence, matched = identity_score(row_text)
                if found and confidence > best_confidence:
                    best_confidence = confidence
                    result["identity_found"] = True
                    result["confidence"] = confidence
                    result["matched_identity"] = matched
                    result["matched_row"] = row_text[:200]
                    if confidence == 1.0:
                        break

        result["total_rows_scanned"] = total_rows

    def _parse_pdf(self, filepath: str, result: dict):
        import pdfplumber

        total_rows = 0
        best_confidence = 0.0

        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract text
                text = page.extract_text() or ""
                lines = text.split("\n")

                for line in lines:
                    total_rows += 1
                    found, confidence, matched = identity_score(line)
                    if found and confidence > best_confidence:
                        best_confidence = confidence
                        result["identity_found"] = True
                        result["confidence"] = confidence
                        result["matched_identity"] = matched
                        result["matched_row"] = line[:200]
                        if confidence == 1.0:
                            break

                # Also scan tables in PDF
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        if row:
                            row_text = " | ".join(str(c) for c in row if c)
                            total_rows += 1
                            found, confidence, matched = identity_score(row_text)
                            if found and confidence > best_confidence:
                                best_confidence = confidence
                                result["identity_found"] = True
                                result["confidence"] = confidence
                                result["matched_identity"] = matched
                                result["matched_row"] = row_text[:200]

                if result["identity_found"] and result["confidence"] == 1.0:
                    break

        result["total_rows_scanned"] = total_rows

    def _parse_txt(self, filepath: str, result: dict):
        total_rows = 0
        best_confidence = 0.0

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_rows += 1
                found, confidence, matched = identity_score(line)
                if found and confidence > best_confidence:
                    best_confidence = confidence
                    result["identity_found"] = True
                    result["confidence"] = confidence
                    result["matched_identity"] = matched
                    result["matched_row"] = line.strip()[:200]
                    if confidence == 1.0:
                        break

        result["total_rows_scanned"] = total_rows
