"""
Research Data Download Script

Downloads and processes external research datasets for training the platform.

Datasets:
1. Figshare Long-Distance Running (10M+ records)
   - https://figshare.com/articles/dataset/A_public_dataset_on_long-distance_running_training_in_2019_and_2020/16620238

2. NRCD Collegiate Running
   - https://arxiv.org/abs/2509.10600

Usage:
    python scripts/download_research_data.py --dataset figshare
    python scripts/download_research_data.py --dataset nrcd
    python scripts/download_research_data.py --all

Notes:
- Downloads are large (1-5GB) - ensure sufficient disk space
- Processing takes time - recommend running overnight for full dataset
- Outputs processed baselines to apps/api/services/research_data/baselines/
"""

import argparse
import os
import sys
import requests
import zipfile
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the api directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'apps' / 'api'))

# Data directory
DATA_DIR = Path(__file__).parent.parent / 'data' / 'research'
BASELINES_DIR = Path(__file__).parent.parent / 'apps' / 'api' / 'services' / 'research_data' / 'baselines'


# Dataset URLs and metadata
DATASETS = {
    'figshare': {
        'name': 'Figshare Long-Distance Running Training',
        'description': '10M+ training records from 36K+ athletes (2019-2020)',
        'url': 'https://figshare.com/ndownloader/files/30850785',  # Direct download link
        'filename': 'running_training_2019_2020.csv',
        'size_gb': 2.5,
        'citation': 'A public dataset on long-distance running training in 2019 and 2020. Figshare. 2021.',
    },
    'nrcd': {
        'name': 'National Running Club Database',
        'description': '15K+ race results from collegiate runners (2023-2024)',
        'url': 'https://github.com/your-repo/nrcd-data',  # Placeholder - need actual source
        'filename': 'nrcd_race_results.csv',
        'size_gb': 0.1,
        'citation': 'National Running Club Database. arXiv:2509.10600. 2025.',
    },
    'sport_db': {
        'name': 'Sport DB 2.0',
        'description': '168 cardiorespiratory datasets from athletes',
        'url': 'https://data.mendeley.com/datasets/kzkjkt7mx2/1',  # Need actual download link
        'filename': 'sport_db_2.zip',
        'size_gb': 0.5,
        'citation': 'Sport DB 2.0. Mendeley Data. 2023.',
    }
}


def ensure_dirs():
    """Ensure data directories exist"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Baselines directory: {BASELINES_DIR}")


def download_file(url: str, destination: Path, description: str = "file"):
    """Download a file with progress indication"""
    logger.info(f"Downloading {description}...")
    logger.info(f"URL: {url}")
    logger.info(f"Destination: {destination}")
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(f"\rProgress: {pct:.1f}%", end='', flush=True)
        
        print()  # New line after progress
        logger.info(f"Download complete: {destination}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
        return False


def process_figshare_data(data_path: Path, sample_size: int = None):
    """
    Process the Figshare running dataset.
    
    Args:
        data_path: Path to the downloaded CSV
        sample_size: If set, only process this many records (for testing)
    """
    from services.research_data.figshare_processor import FigshareDataProcessor
    
    logger.info(f"Processing Figshare data from {data_path}")
    
    processor = FigshareDataProcessor(str(data_path))
    
    # Load data
    count = processor.load_data(limit=sample_size)
    logger.info(f"Loaded {count} records")
    
    if count == 0:
        logger.warning("No data loaded - check file format")
        return
    
    # Build baselines
    logger.info("Building population baselines...")
    baselines = processor.build_population_baselines()
    
    logger.info(f"Built {len(baselines)} cohort baselines:")
    for name, baseline in baselines.items():
        logger.info(f"  {name}: {baseline.sample_size} athletes, "
                   f"avg {baseline.avg_weekly_km:.1f} km/week")
    
    # Export baselines
    output_path = BASELINES_DIR / 'figshare_baselines.json'
    processor.export_baselines_json(str(output_path))
    logger.info(f"Exported baselines to {output_path}")


def download_and_process(dataset_key: str, sample_only: bool = False):
    """Download and process a single dataset"""
    if dataset_key not in DATASETS:
        logger.error(f"Unknown dataset: {dataset_key}")
        logger.info(f"Available datasets: {list(DATASETS.keys())}")
        return False
    
    dataset = DATASETS[dataset_key]
    logger.info(f"\n{'='*60}")
    logger.info(f"Dataset: {dataset['name']}")
    logger.info(f"Description: {dataset['description']}")
    logger.info(f"Estimated size: {dataset['size_gb']} GB")
    logger.info(f"{'='*60}\n")
    
    # Check if already downloaded
    destination = DATA_DIR / dataset['filename']
    
    if destination.exists():
        logger.info(f"File already exists: {destination}")
        response = input("Re-download? (y/n): ").strip().lower()
        if response != 'y':
            logger.info("Using existing file")
        else:
            download_file(dataset['url'], destination, dataset['name'])
    else:
        success = download_file(dataset['url'], destination, dataset['name'])
        if not success:
            return False
    
    # Handle zip files
    if destination.suffix == '.zip':
        logger.info("Extracting zip file...")
        with zipfile.ZipFile(destination, 'r') as zf:
            zf.extractall(DATA_DIR)
        logger.info("Extraction complete")
    
    # Process based on dataset type
    if dataset_key == 'figshare':
        sample_size = 100000 if sample_only else None  # 100K for testing
        process_figshare_data(destination, sample_size)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Download and process research datasets for training analytics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/download_research_data.py --dataset figshare
    python scripts/download_research_data.py --dataset figshare --sample
    python scripts/download_research_data.py --all
    python scripts/download_research_data.py --list
        """
    )
    
    parser.add_argument(
        '--dataset', 
        choices=list(DATASETS.keys()),
        help='Specific dataset to download'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all available datasets'
    )
    parser.add_argument(
        '--sample',
        action='store_true',
        help='Only process a sample (for testing)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available datasets'
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Research Datasets:\n")
        for key, dataset in DATASETS.items():
            print(f"  {key}:")
            print(f"    Name: {dataset['name']}")
            print(f"    Description: {dataset['description']}")
            print(f"    Size: ~{dataset['size_gb']} GB")
            print(f"    Citation: {dataset['citation']}")
            print()
        return
    
    ensure_dirs()
    
    if args.all:
        for key in DATASETS.keys():
            download_and_process(key, sample_only=args.sample)
    elif args.dataset:
        download_and_process(args.dataset, sample_only=args.sample)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()


