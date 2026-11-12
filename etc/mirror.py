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
- With --list0: write source-relative, NUL-separated file paths to stdout
  without copying files or creating directories. No destination is required.
- With --regex: filter source-relative file paths after selecting the last N.
- With --dir-regex: enter only matching source-relative directory paths,
  skipping nonmatching subtrees. The source root is always visited.

"""
import argparse
from collections.abc import Iterator
import os
import re
import shutil
import sys
from textwrap import dedent
from typing import Optional


def get_sorted_files(path: str, sort_key: str) -> list[str]:
    """Return filenames (not full paths) in `path`, sorted by sort_key.

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


def selected_directories(
    src: str,
    sort_key: str,
    top_n: Optional[int],
    n: int,
    regex: Optional[str] = None,
    dir_regex: Optional[str] = None,
) -> Iterator[tuple[str, list[str]]]:
    """Yield directories and selected filenames, including empty directories."""
    if n != -1 and n < 1:
        raise ValueError("n must be a positive integer or -1 to copy all files")

    src = os.path.abspath(src)
    if not os.path.isdir(src):
        raise ValueError(f"Source '{src}' is not a directory")

    pattern = re.compile(regex) if regex is not None else None
    directory_pattern = re.compile(dir_regex) if dir_regex is not None else None

    for root, dirs, files in os.walk(src):
        # If we're at the top-level of the source tree and a top-level limit
        # was provided, restrict traversal to the first `top_n` directories.
        # We sort `dirs` by name so the selection is deterministic.
        if top_n is not None and os.path.abspath(root) == src:
            dirs.sort()
            # Modify dirs in-place to limit os.walk traversal.
            del dirs[top_n:]
        if directory_pattern is not None:
            dirs[:] = [
                d for d in dirs
                if directory_pattern.search(
                    os.path.relpath(os.path.join(root, d), src)
                )
            ]
        sorted_files = get_sorted_files(root, sort_key)
        selected = sorted_files if n == -1 else sorted_files[-n:]
        if pattern is not None:
            selected = [
                fname for fname in selected
                if pattern.search(os.path.relpath(os.path.join(root, fname), src))
            ]
        yield root, selected


def mirror_last(
    src: str,
    dst: str,
    sort_key: str = 'name',
    dry_run: bool = False,
    verbose: bool = False,
    top_n: int = None,
    n: int = 1,
    regex: Optional[str] = None,
    dir_regex: Optional[str] = None,
) -> tuple[int, int]:
    """Copy the last n files per directory, or all files if n is -1."""
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    total_size = 0
    total_files = 0

    for root, to_copy in selected_directories(
        src, sort_key, top_n, n, regex=regex, dir_regex=dir_regex
    ):
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

        if not to_copy:
            if verbose:
                print(f"  no files to copy in {root}")
            continue

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
                print(
                    f"  {'[dry-run] ' if dry_run else ''}copy: "
                    f"{src_path} -> {dst_path} ({size_mb:.2f} MB)"
                )
            except Exception as e:
                print(
                    f"Warning: failed to get size of {src_path}: {e}",
                    file=sys.stderr,
                )
                file_size = 0

            if not dry_run:
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception as e:
                    # Don't crash the whole run for one file; report and continue
                    print(
                        f"Warning: failed to copy {src_path} -> {dst_path}: {e}",
                        file=sys.stderr,
                    )

    return total_size, total_files



def parse_args():
    description = """
    List or mirror a directory tree keeping only the last N files
    in each directory.

    examples:
      python mirror.py --help
      Copy files:
        python mirror.py /path/to/src /path/to/dst -n 3 \\
          [--sort name|mtime|ctime|size] [--dry-run] [--verbose]

      Filter the last N files by source-relative path:
        python mirror.py /path/to/src /path/to/dst -n 3 --regex '^[A-Z][0-9]'

      Skip directory trees whose source-relative paths do not match:
        python mirror.py /path/to/src /path/to/dst -n 3 \\
          --dir-regex '^[A-Z][0-9]'
        The source root is always visited; every ancestor directory must match.

      List files and archive them:
        python mirror.py /path/to/src -n 3 --list0 > files.list
        tar -czf /tmp/selected.tar.gz -C /path/to/src --null -T files.list
    """
    p = argparse.ArgumentParser(
        description=dedent(description),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument('src', help='Source directory')
    p.add_argument(
        'dst', nargs='?',
        help='Destination directory (required unless --list0 is used)',
    )
    p.add_argument(
        '--list0', action='store_true',
        help='List source-relative, NUL-separated file paths without copying',
    )
    p.add_argument(
        '-n', type=int, default=1,
        help=(
            'Number of files to copy per directory, or -1 for all files '
            '(default: 1)'
        ),
    )
    p.add_argument(
        '--sort', choices=['name', 'mtime', 'ctime', 'size'], default='name',
        help='Sort key to determine the last N files (default: name)',
    )
    p.add_argument(
        '--regex',
        help=(
            'Regex to search source-relative file paths after selecting '
            'the last N files'
        ),
    )
    p.add_argument(
        '--dir-regex',
        help=(
            'Regex to search source-relative directory paths before entering '
            'them; nonmatching subtrees are skipped, but the source root '
            'is always visited'
        ),
    )
    p.add_argument(
        '--dry-run', action='store_true',
        help="Don't actually copy files; just show what would be done",
    )
    p.add_argument('--verbose', '-v', action='store_true',
                   help='Verbose output')
    p.add_argument(
        '--top-level-limit', type=int, default=None,
        help=(
            'Only traverse the first N top-level subdirectories '
            '(sorted by name).'
        ),
    )
    args = p.parse_args()
    if not args.list0 and args.dst is None:
        p.error('dst is required unless --list0 is used')
    if args.list0 and args.dst is not None:
        p.error('dst cannot be used with --list0')
    return args


def main():
    args = parse_args()
    try:
        if args.list0:
            src = os.path.abspath(args.src)
            for root, filenames in selected_directories(
                src, args.sort, args.top_level_limit, args.n,
                regex=args.regex, dir_regex=args.dir_regex,
            ):
                if args.verbose:
                    print(f"Listing directory: {root}", file=sys.stderr)
                for fname in filenames:
                    path = os.path.relpath(os.path.join(root, fname), src)
                    sys.stdout.buffer.write(os.fsencode(path) + b'\0')
            sys.stdout.buffer.flush()
            return
        total_size, total_files = mirror_last(
            args.src, args.dst, sort_key=args.sort,
            dry_run=args.dry_run, verbose=args.verbose,
            top_n=args.top_level_limit, n=args.n,
            regex=args.regex, dir_regex=args.dir_regex,
        )
        total_mb = total_size / (1024 * 1024)
        total_gb = total_size / (1024 * 1024 * 1024)
        print(
            f"\n{'[dry-run] ' if args.dry_run else ''}Total: "
            f"{total_files} files, {total_mb:.2f} MB ({total_gb:.2f} GB)"
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
