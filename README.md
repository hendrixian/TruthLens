# TruthLens

## Run The Extension
1. Open Chrome.
2. Go to `chrome://extensions`.
3. Turn on **Developer mode**.
4. Click **Load unpacked**.
5. Select the extension folder.

## After Code Changes
1. Reload the extension in `chrome://extensions`.
2. Refresh the webpage.

## Scan An Article
1. Start the local scan server:
   `python -B local_scan_server.py`
2. Click the TruthLens icon on the page.
3. Scanned files are saved in `scanned/` for testing.

## Fake News 
### Requirements
- Python environment with `torch` and `transformers`
- Trained model at `models/FakeNews/best_model`
- Local scan server running: `python -B local_scan_server.py`

### Instructions
1. Extension mode (single article): click the TruthLens icon on a page.
2. Batch mode (all scanned files):
   `python -B predict_scanned.py --input scanned`
3. Single file mode:
   `python -B predict_scanned.py --input scanned\\your_file.txt`


## Hate Speech