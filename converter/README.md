# How to Use the Converter

## Step by Step Instructions

1. Place your Jupyter notebooks (`.ipynb` files) in the `converter/notebooks/` directory.
2. Run the converter script:
   ```bash
   # Use defaults from config
    python converter/converter.py

    # Convert entire folder
    python converter/converter.py converter/raw

    # Convert specific files
    python converter/converter.py converter/raw/TCoil_Dataset_Generator_and_Training.ipynb

    # Mix of files and folders
    python converter/converter.py converter/raw file1.ipynb file2.ipynb
   ```
3. Converted Markdown files will be saved in `converter/output/markdown/` and Python files in `converter/output/python/` (configurable in `config/config.py`).