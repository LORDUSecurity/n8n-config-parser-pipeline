#!/usr/bin/env python3
"""
Example CSV Parser — A working BYOP implementation.

Parses CSV/text files and generates a styled Excel report.
Copy this to scripts/your_parser.py to try the pipeline with sample data.
"""
import csv
import io
import os

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def process_all_files(directory: str) -> dict:
    """Parse CSV/text files from a directory into structured data."""
    results = {}
    for fname in sorted(os.listdir(directory)):
        filepath = os.path.join(directory, fname)
        if not os.path.isfile(filepath):
            continue

        stem = os.path.splitext(fname)[0]
        records = []

        with open(filepath, 'r', errors='replace') as f:
            content = f.read().strip()

        if not content:
            results[stem] = {'hostname': stem, 'records': [], 'record_count': 0}
            continue

        # Try CSV first, fall back to line-by-line
        try:
            reader = csv.DictReader(io.StringIO(content))
            if reader.fieldnames:
                for row in reader:
                    records.append(dict(row))
        except Exception:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    records.append({'value': line})

        results[stem] = {
            'hostname': stem,
            'records': records,
            'record_count': len(records),
            'columns': list(records[0].keys()) if records else [],
        }

    return results


def generate_excel(
    data: dict,
    output_path: str,
    switch_dir: str = None,
    switch_devices: dict = None,
) -> None:
    """Generate a styled Excel workbook from parsed CSV data."""
    wb = openpyxl.Workbook()

    # Styles
    header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    title_font = Font(name='Calibri', bold=True, size=14, color='2F5496')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    # Remove default sheet
    wb.remove(wb.active)

    for device_name, device_data in data.items():
        ws = wb.create_sheet(title=device_name[:31])  # Excel sheet name limit
        records = device_data.get('records', [])

        # Title row
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(device_data.get('columns', [])), 1))
        title_cell = ws.cell(row=1, column=1, value=device_name)
        title_cell.font = title_font

        if not records:
            ws.cell(row=3, column=1, value='No records found')
            continue

        # Headers
        columns = list(records[0].keys())
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=3, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        # Data rows
        for row_idx, record in enumerate(records, 4):
            for col_idx, col_name in enumerate(columns, 1):
                cell = ws.cell(row=row_idx, column=col_idx,
                               value=record.get(col_name, ''))
                cell.border = thin_border
                cell.font = Font(name='Calibri', size=10)

        # Auto-size columns
        for col_idx, col_name in enumerate(columns, 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            max_len = max(
                len(str(col_name)),
                max((len(str(r.get(col_name, ''))) for r in records), default=0)
            )
            ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    # If no data, create a summary sheet
    if not wb.sheetnames:
        ws = wb.create_sheet(title='Summary')
        ws.cell(row=1, column=1, value='No data to display')

    wb.save(output_path)
