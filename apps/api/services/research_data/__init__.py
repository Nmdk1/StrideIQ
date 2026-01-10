"""
Research Data Integration Module

Handles ingestion, processing, and analysis of external research datasets
to enhance our correlation engine and provide population-level baselines.

Key Datasets:
- Figshare Long-Distance Running (10M+ records, 36K+ athletes)
- NRCD Collegiate Running (15K+ race results)
- Sport DB 2.0 (Cardiorespiratory data)

Design Philosophy:
- Focus on recreational/amateur athletes, not elites
- Age-grade all performance data for fair comparison
- Build baselines for "people like you" comparisons
- Never prescribe based on what elites do
"""


