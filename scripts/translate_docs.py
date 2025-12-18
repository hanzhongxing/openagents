#!/usr/bin/env python3
"""
Documentation Translation Script

Translates MDX documentation files from English to other languages using GPT-5.
Tracks file hashes to avoid re-translating unchanged content.

Usage:
    python scripts/translate_docs.py --source docs/en --targets zh_CN,jp,kr
    python scripts/translate_docs.py --source docs/en --targets zh_CN --force
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from openai import OpenAI

# Language code to full name mapping
LANG_NAMES = {
    "zh_CN": "Simplified Chinese",
    "jp": "Japanese",
    "kr": "Korean",
}

HASH_FILE = ".translation-hashes.json"


def get_file_hash(content: str) -> str:
    """Generate MD5 hash of file content."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def load_hashes(hash_file: Path) -> dict:
    """Load existing translation hashes from file."""
    if hash_file.exists():
        with open(hash_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(hashes: dict, hash_file: Path) -> None:
    """Save translation hashes to file."""
    with open(hash_file, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)


def translate_content(client: OpenAI, content: str, target_lang: str) -> str:
    """
    Translate MDX content to target language using GPT-5.

    Preserves:
    - Code blocks (fenced and indented)
    - MDX component syntax
    - Inline code backticks
    - Image/asset paths
    - Frontmatter keys (translates values where appropriate)
    """
    lang_name = LANG_NAMES.get(target_lang, target_lang)

    system_prompt = f"""You are a professional technical documentation translator.
Translate the following MDX documentation from English to {lang_name}.

IMPORTANT RULES:
1. Preserve ALL code blocks exactly as-is (both fenced ``` and indented)
2. Preserve ALL inline code within backticks exactly as-is
3. Preserve ALL MDX component syntax (e.g., <Banner>, <Tabs>, <Tab>)
4. Preserve ALL image paths and URLs exactly as-is
5. Preserve ALL frontmatter keys in English, only translate the values if they are human-readable text
6. Preserve ALL HTML tags and attributes
7. Translate prose, headings, and descriptions naturally
8. Keep technical terms that are commonly used in English (e.g., API, SDK, CLI)
9. Maintain the same markdown formatting (headers, lists, bold, italic)

Output ONLY the translated content, no explanations."""

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content


def process_file(
    client: OpenAI,
    source_file: Path,
    source_dir: Path,
    target_lang: str,
    docs_root: Path,
    hashes: dict,
    force: bool,
) -> bool:
    """
    Process a single file for translation.

    Returns True if file was translated, False if skipped.
    """
    # Calculate relative path from source directory
    rel_path = source_file.relative_to(source_dir)

    # Construct target file path
    target_dir = docs_root / target_lang
    target_file = target_dir / rel_path

    # Read source content
    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Calculate hash
    content_hash = get_file_hash(content)
    hash_key = f"{target_lang}:{rel_path}"

    # Check if translation is needed
    if not force and hash_key in hashes and hashes[hash_key] == content_hash:
        print(f"  Skipping {rel_path} (unchanged)")
        return False

    print(f"  Translating {rel_path} to {LANG_NAMES.get(target_lang, target_lang)}...")

    # Translate content
    translated = translate_content(client, content, target_lang)

    # Ensure target directory exists
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Write translated content
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(translated)

    # Update hash
    hashes[hash_key] = content_hash

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Translate documentation files using GPT-5"
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Source documentation directory (e.g., docs/en)",
    )
    parser.add_argument(
        "--targets",
        type=str,
        required=True,
        help="Comma-separated target language codes (e.g., zh_CN,jp,kr)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-translation of all files",
    )

    args = parser.parse_args()

    # Parse arguments
    source_dir = Path(args.source)
    target_langs = [lang.strip() for lang in args.targets.split(",")]

    # Validate source directory
    if not source_dir.exists():
        print(f"Error: Source directory {source_dir} does not exist")
        sys.exit(1)

    # Get docs root directory (parent of source)
    docs_root = source_dir.parent

    # Initialize OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")

    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    # Load existing hashes
    hash_file = Path(HASH_FILE)
    hashes = load_hashes(hash_file)

    # Find all MDX files
    mdx_files = list(source_dir.rglob("*.mdx"))
    md_files = list(source_dir.rglob("*.md"))
    all_files = mdx_files + md_files

    if not all_files:
        print(f"No .mdx or .md files found in {source_dir}")
        sys.exit(0)

    print(f"Found {len(all_files)} documentation files")

    # Process each target language
    total_translated = 0
    for target_lang in target_langs:
        if target_lang not in LANG_NAMES:
            print(f"Warning: Unknown language code {target_lang}, using as-is")

        print(f"\nProcessing {LANG_NAMES.get(target_lang, target_lang)}...")

        for source_file in all_files:
            try:
                if process_file(
                    client,
                    source_file,
                    source_dir,
                    target_lang,
                    docs_root,
                    hashes,
                    args.force,
                ):
                    total_translated += 1
            except Exception as e:
                print(f"  Error translating {source_file}: {e}")
                continue

    # Save updated hashes
    save_hashes(hashes, hash_file)

    print(f"\nTranslation complete. {total_translated} files translated.")


if __name__ == "__main__":
    main()
