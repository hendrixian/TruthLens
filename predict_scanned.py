from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "FakeNews" / "best_model"
DEFAULT_INPUT = PROJECT_ROOT / "scanned"
ARTICLE_MARKER = "----- article_text -----"
NOISE_LINE_PATTERNS = (
    r"^ADVERTISEMENT$",
    r"^SKIP ADVERTISEMENT$",
    r"^Share full article$",
    r"^READ \d+ COMMENTS$",
    r"^Related Content$",
    r"^Listen",
    r"^Credit\.\.\.$",
    r"^See more of our coverage",
    r"^Add The New York Times on Google$",
)


def clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def parse_scanned_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    title = ""
    url = ""
    article_text = ""

    if ARTICLE_MARKER in raw:
        header, article_block = raw.split(ARTICLE_MARKER, 1)
        article_text = article_block.strip()

        for line in header.splitlines():
            lowered = line.lower()
            if lowered.startswith("title:"):
                title = line.split(":", 1)[1].strip()
            elif lowered.startswith("url:"):
                url = line.split(":", 1)[1].strip()
    else:
        article_text = raw.strip()

    return {
        "title": clean_text(title),
        "url": url,
        "article_text": article_text.strip(),
    }


def strip_boilerplate_lines(article_text: str) -> str:
    patterns = [re.compile(p, flags=re.IGNORECASE) for p in NOISE_LINE_PATTERNS]
    kept = []
    for line in article_text.splitlines():
        stripped = clean_text(line)
        if not stripped:
            continue
        if any(p.search(stripped) for p in patterns):
            continue
        kept.append(stripped)
    return "\n".join(kept)


def extract_article_core(title: str, article_text: str) -> str:
    cleaned = strip_boilerplate_lines(article_text)
    if not cleaned:
        return ""

    lines = [clean_text(line) for line in cleaned.splitlines() if clean_text(line)]
    if not lines:
        return ""

    title_norm = clean_text(title).lower()
    start_idx = 0
    if title_norm:
        for idx, line in enumerate(lines):
            if line.lower() == title_norm:
                start_idx = idx + 1 if idx + 1 < len(lines) else idx
                break

    core = lines[start_idx:] if start_idx < len(lines) else lines
    return "\n".join(core) if core else "\n".join(lines)


def build_model_input(title: str, article_text: str) -> str:
    title = clean_text(title)
    article_text = clean_text(extract_article_core(title, article_text))
    if title and article_text:
        return f"{title} [SEP] {article_text}"
    return title or article_text


def load_id2label(model_dir: Path) -> dict[int, str]:
    label_map_path = model_dir / "label_map.json"
    if label_map_path.exists():
        data = json.loads(label_map_path.read_text(encoding="utf-8"))
        id2label = data.get("id2label", {})
        return {int(k): str(v) for k, v in id2label.items()}

    config_path = model_dir / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    id2label = data.get("id2label", {})
    return {int(k): str(v) for k, v in id2label.items()}


def iter_input_files(input_path: Path, pattern: str) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    if input_path.is_dir():
        yield from sorted(input_path.glob(pattern))
        return
    raise FileNotFoundError(f"Input path not found: {input_path}")


def predict_text(
    text: str,
    model: AutoModelForSequenceClassification,
    tokenizer: AutoTokenizer,
    device: torch.device,
    id2label: dict[int, str],
    max_length: int,
    window_stride: int,
    max_windows: int,
) -> dict:
    # "window_stride" is treated as token step size.
    # HuggingFace tokenizer expects overlap stride, so convert step -> overlap.
    step = max(1, min(max_length, window_stride))
    overlap = max(0, max_length - step)

    encoded = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        stride=overlap,
        return_overflowing_tokens=True,
        return_tensors="pt",
    )
    window_count = encoded["input_ids"].shape[0]
    if window_count == 0:
        raise ValueError("No windows produced from input text")

    max_eval = window_count if max_windows <= 0 else min(window_count, max_windows)
    probs_per_window = []
    windows_evaluated = 0

    for idx in range(max_eval):
        chunk = {
            key: value[idx:idx + 1].to(device)
            for key, value in encoded.items()
            if key in {"input_ids", "attention_mask", "token_type_ids"}
        }

        with torch.no_grad():
            logits = model(**chunk).logits
            probs = torch.softmax(logits, dim=-1)[0]
        probs_per_window.append(probs)
        windows_evaluated += 1

    probs = torch.stack(probs_per_window).mean(dim=0)

    pred_id = int(torch.argmax(probs).item())
    pred_label = id2label.get(pred_id, str(pred_id))

    scores = {}
    for idx in range(probs.shape[0]):
        label = id2label.get(idx, str(idx))
        scores[label] = float(probs[idx].item())

    return {
        "label": pred_label,
        "confidence": scores.get(pred_label, 0.0),
        "scores": scores,
        "windows_evaluated": windows_evaluated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run fake news inference from scanned txt files."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="File or folder of scanned .txt files (default: scanned folder).",
    )
    parser.add_argument(
        "--model-dir",
        default=str(DEFAULT_MODEL_DIR),
        help="Folder containing model/tokenizer files.",
    )
    parser.add_argument(
        "--pattern",
        default="*.txt",
        help="Glob pattern when --input is a folder.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=256,
        help="Tokenizer max_length used during training (default: 256).",
    )
    parser.add_argument(
        "--window-stride",
        type=int,
        default=192,
        help="Token stride between inference windows (default: 192).",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=12,
        help="Maximum number of windows per document (default: 12).",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write all predictions as JSON.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    model_dir = Path(args.model_dir).resolve()
    if not model_dir.exists():
        raise FileNotFoundError(f"Model dir not found: {model_dir}")

    files = list(iter_input_files(input_path, args.pattern))
    if not files:
        print(f"No files matched in: {input_path}")
        return

    id2label = load_id2label(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    print(f"Loaded model from: {model_dir}")
    print(f"Using device: {device}")
    print(f"Scanning files: {len(files)}\n")

    rows = []
    for file_path in files:
        parsed = parse_scanned_file(file_path)
        model_text = build_model_input(parsed["title"], parsed["article_text"])
        if not model_text:
            print(f"SKIP {file_path.name}: no usable text")
            continue

        pred = predict_text(
            model_text,
            model=model,
            tokenizer=tokenizer,
            device=device,
            id2label=id2label,
            max_length=args.max_length,
            window_stride=args.window_stride,
            max_windows=args.max_windows,
        )

        result = {
            "file": str(file_path),
            "title": parsed["title"],
            "url": parsed["url"],
            "label": pred["label"],
            "confidence": pred["confidence"],
            "scores": pred["scores"],
            "windows_evaluated": pred["windows_evaluated"],
        }
        rows.append(result)

        print(
            f"{file_path.name}: {result['label']} "
            f"(confidence={result['confidence']:.4f})"
        )

    if args.output_json:
        out_path = Path(args.output_json).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nSaved predictions to: {out_path}")


if __name__ == "__main__":
    main()
