#!/usr/bin/env python3
"""
mirror.py

Mirror a directory tree but only copy the last N files in each directory.

Behavior:
- For every directory in the source tree, create the same directory in
  the destination tree.
- Within each directory, find files (not subdirectories), sort them by
  the chosen key (name, mtime, ctime, size) and copy only the last N
  files to the corresponding destination directory (default: N = 1).
- If there are no files: destination directory is created but remains empty.
- If there are fewer than N files: all files are copied.
- If N is -1: all files are copied.

Usage:
  python mirror.py --help
  python mirror.py /path/to/src /path/to/dst -n 3 [--sort name|mtime|ctime|size] [--dry-run] [--verbose]

"""
import argparse
import os
import shutil
import sys
from typing import List, Tuple


def get_sorted_files(path: str, sort_key: str) -> List[str]:
    """Return list of filenames (not full paths) in directory `path` sorted by sort_key.

    sort_key: 'name'|'mtime'|'ctime'|'size'
    """
    try:
        entries = [e for e in os.scandir(path) if e.is_file()]
    except FileNotFoundError:
        return []

    if sort_key == 'name':
        entries.sort(key=lambda e: e.name)
    elif sort_key == 'mtime':
        entries.sort(key=lambda e: e.stat().st_mtime)
    elif sort_key == 'ctime':
        entries.sort(key=lambda e: e.stat().st_ctime)
    elif sort_key == 'size':
        entries.sort(key=lambda e: e.stat().st_size)
    else:
        entries.sort(key=lambda e: e.name)

    return [e.name for e in entries]


def mirror_last(src: str, dst: str, sort_key: str = 'name', dry_run: bool = False, verbose: bool = False, top_n: int = None, n: int = 1) -> Tuple[int, int]:
    """Mirror directory tree copying the last n files per directory, or all if n is -1."""
    if n != -1 and n < 1:
        raise ValueError("n must be a positive integer or -1 to copy all files")

    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    total_size = 0
    total_files = 0

    if not os.path.isdir(src):
        raise ValueError(f"Source '{src}' is not a directory")

    for root, dirs, files in os.walk(src):
        # If we're at the top-level of the source tree and a top-level limit
        # was provided, restrict traversal to the first `top_n` directories.
        # We sort `dirs` by name so the selection is deterministic.
        if top_n is not None and os.path.abspath(root) == src:
            dirs.sort()
            # modify dirs in-place to limit which subdirectories os.walk will traverse
            del dirs[top_n:]
        # Compute corresponding destination directory
        rel_dir = os.path.relpath(root, src)
        if rel_dir == '.':
            dest_dir = dst
        else:
            dest_dir = os.path.join(dst, rel_dir)

        if verbose:
            print(f"Processing directory: {root} -> {dest_dir}")

        # Ensure destination directory exists
        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
        else:
            if verbose:
                print(f"[dry-run] mkdir -p {dest_dir}")

        # Gather and sort files according to sort_key
        sorted_files = get_sorted_files(root, sort_key)

        if not sorted_files:
            if verbose:
                print(f"  no files to copy in {root}")
            continue

        to_copy = sorted_files if n == -1 else sorted_files[-n:]

        # Copy each file
        for fname in to_copy:
            src_path = os.path.join(root, fname)
            dst_path = os.path.join(dest_dir, fname)

            # Get file size
            try:
                file_size = os.path.getsize(src_path)
                total_size += file_size
                total_files += 1
                size_mb = file_size / (1024 * 1024)
                print(f"  {'[dry-run] ' if dry_run else ''}copy: {src_path} -> {dst_path} ({size_mb:.2f} MB)")
            except Exception as e:
                print(f"Warning: failed to get size of {src_path}: {e}", file=sys.stderr)
                file_size = 0

            if not dry_run:
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception as e:
                    # Don't crash the whole run for one file; report and continue
                    print(f"Warning: failed to copy {src_path} -> {dst_path}: {e}", file=sys.stderr)

    return total_size, total_files


def parse_args():
    p = argparse.ArgumentParser(description='Mirror a directory tree copying only the last N files in each directory')
    p.add_argument('src', help='Source directory')
    p.add_argument('dst', help='Destination directory')
    p.add_argument('-n', type=int, default=1, help='Number of files to copy per directory, or -1 for all files (default: 1)')
    p.add_argument('--sort', choices=['name', 'mtime', 'ctime', 'size'], default='name', help='Sort key to determine the last N files (default: name)')
    p.add_argument('--dry-run', action='store_true', help="Don't actually copy files; just show what would be done")
    p.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    p.add_argument('--top-level-limit', type=int, default=None, help='Only traverse the first N top-level subdirectories (sorted by name).')
    return p.parse_args()


def main():
    args = parse_args()
    try:
        total_size, total_files = mirror_last(args.src, args.dst, sort_key=args.sort, dry_run=args.dry_run, verbose=args.verbose, top_n=args.top_level_limit, n=args.n)
        total_mb = total_size / (1024 * 1024)
        total_gb = total_size / (1024 * 1024 * 1024)
        print(f"\n{'[dry-run] ' if args.dry_run else ''}Total: {total_files} files, {total_mb:.2f} MB ({total_gb:.2f} GB)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
