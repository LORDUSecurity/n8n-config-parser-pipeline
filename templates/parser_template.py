#!/usr/bin/env python3
"""
Parser Template — Interface Contract for BYOP (Bring Your Own Parser)

Copy this file to scripts/your_parser.py and implement the two functions below.
The pipeline calls these functions in order:

    Stage 2: pc.process_all_files(directory)  → dict of parsed data
    Stage 3: pc.generate_excel(data, path, …) → writes an Excel file

Your parser module is imported as `pc` by the pipeline scripts.
"""


def process_all_files(directory: str) -> dict:
    """
    Parse all files found in `directory` and return structured data.

    Args:
        directory: Absolute path to a folder of normalized text files.
                   The pipeline places primary configs in staging/configs/
                   and secondary device configs in staging/switches/.

    Returns:
        A dict mapping device/group names to their parsed data:
        {
            "device_A": {
                "hostname": "device_A",
                "records": [...],       # Your parsed records
                "metadata": {...},      # Any extra info
                ...
            },
            "device_B": { ... },
        }

    Notes:
        - Use os.listdir(directory) to discover files
        - Files are .txt (normalized by Stage 1)
        - Return empty dict {} if the directory is empty
        - Sets and bytes in the return value are auto-serialized to
          JSON-safe types by the pipeline
    """
    import os

    results = {}
    for fname in sorted(os.listdir(directory)):
        filepath = os.path.join(directory, fname)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, 'r', errors='replace') as f:
            lines = f.readlines()

        # ── YOUR PARSING LOGIC HERE ──
        # Example: extract key-value pairs
        device_name = fname.replace('.txt', '')
        records = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                records.append({'raw': line})

        results[device_name] = {
            'hostname': device_name,
            'records': records,
            'record_count': len(records),
        }

    return results


def generate_excel(
    data: dict,
    output_path: str,
    switch_dir: str = None,
    switch_devices: dict = None,
) -> None:
    """
    Generate a styled Excel workbook from the parsed data.

    Args:
        data:           The dict returned by process_all_files() for
                        primary devices.
        output_path:    Absolute path where the .xlsx file must be written.
        switch_dir:     Optional path to secondary device config directory.
        switch_devices: Optional dict of secondary device parsed data
                        (from process_all_files on staging/switches/).

    Notes:
        - Use openpyxl to create the workbook
        - The pipeline handles directory creation (os.makedirs)
        - Apply styling (fonts, fills, column widths) as needed
        - The output file is attached to the HTTP response by the pipeline
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Report'

    # ── Header styling ──
    header_font = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')

    # ── Write a summary sheet ──
    headers = ['Device', 'Records', 'Details']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    row = 2
    for device_name, device_data in data.items():
        records = device_data.get('records', [])
        ws.cell(row=row, column=1, value=device_name)
        ws.cell(row=row, column=2, value=len(records))
        ws.cell(row=row, column=3, value=str(device_data.get('metadata', '')))
        row += 1

    # ── Auto-size columns ──
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    wb.save(output_path)
