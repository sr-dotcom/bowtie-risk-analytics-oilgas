# Bowtie Risk Analytics

Streamlit application for analyzing oil and gas incidents using the Bowtie risk methodology.

## Overview
This project processes incident narratives to extract risk factors and visualize them using Bowtie diagrams. It aims to identify gaps in barrier coverage and calculate risk metrics.

## Setup
1.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run tests:
    ```bash
    pytest
    ```

## Structure
- `src/models`: Pydantic definitions for Incident and Bowtie elements.
- `src/analytics`: Core logic for gap analysis and risk calculation.
- `src/app`: Streamlit dashboard code.
- `data`: Directory for raw and processed datasets.

## Development
Check `docs/DEVLOG.md` for daily progress updates.
