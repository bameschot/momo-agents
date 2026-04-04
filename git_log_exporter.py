#!/usr/bin/env python3
"""Git Log Exporter - Export Git commit metadata to JSONL format."""

import argparse
import json
import subprocess
import sys


def validate_repo(repo_path: str) -> bool:
    """Validate that the given path is a valid Git repository.

    Args:
        repo_path: Path to check for Git repository

    Returns:
        True if valid Git repository

    Raises:
        ValueError: If path is not a valid Git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            shell=False
        )

        if result.returncode != 0:
            raise ValueError(f"Error: '{repo_path}' is not a valid Git repository")

        return True
    except FileNotFoundError:
        raise ValueError(f"Error: '{repo_path}' does not exist or is not accessible")


def fetch_commits(repo_path: str, start_date: str) -> list:
    """Fetch commits from Git repository within the date range.

    Args:
        repo_path: Path to Git repository
        start_date: ISO8601 timestamp to filter commits from

    Returns:
        List of commit information as strings from git log

    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    try:
        result = subprocess.run(
            [
                "git", "log",
                "--format=%ad|%an|%s",
                "--date=iso-strict",
                f"--since={start_date}",
                "--", "."
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            shell=False
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                result.stderr
            )
    except FileNotFoundError:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "log"],
            stderr=f"Error: The repository path '{repo_path}' does not exist or is not accessible"
        )

    return result.stdout.strip().split('\n') if result.stdout.strip() else []


def process_commit(commit_line: str, max_message_length: int = 250) -> dict:
    """Process a single commit line into a commit record.

    Args:
        commit_line: Formatted git log output (timestamp|committer|message)
        max_message_length: Maximum length to truncate message

    Returns:
        Dictionary containing commit metadata
    """
    parts = commit_line.split('|', 2)

    if len(parts) < 3:
        return None

    timestamp, committer, message = parts

    # Truncate message if needed
    if len(message) > max_message_length:
        message = message[:max_message_length]

    return {
        "timestamp": timestamp,
        "committer": committer,
        "message": message
    }


def write_output(output_path: str, commits: list) -> None:
    """Write commits to JSONL output file.

    Args:
        output_path: Path to output file
        commits: List of commit records

    Raises:
        IOError: If unable to write to file
        OSError: If file system errors occur
    """
    try:
        # Open file with newline='' to prevent extra line endings on Windows
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            for commit in commits:
                if commit is not None:
                    # Serialize commit record to JSON
                    json_str = json.dumps(commit, ensure_ascii=False)
                    f.write(json_str + '\n')
    except TypeError as e:
        # Handles non-serializable objects in commit records
        print(f"Error: Failed to serialize commit record: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Error: Permission denied when writing to file: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        # Handles disk full, file not found, broken pipe, etc.
        if e.errno == 28:  # ENOSPC - no space left on device
            msg = f"Error: No space left on device: {e}"
        elif e.errno == 13:  # EACCES - permission denied
            msg = f"Error: Permission denied: {e}"
        elif e.errno == 15:  # EIO - input/output error (disk may be corrupted)
            msg = f"Error: I/O error on device: {e}"
        else:
            msg = f"Error: File system error while writing: {e}"
        print(msg, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch-all for any other unexpected errors during file writing
        print(f"Error: Unexpected error during output writing: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for the Git Log Exporter."""
    parser = argparse.ArgumentParser(
        description='Export Git commit metadata to JSONL format'
    )
    parser.add_argument(
        '--repo',
        help='Path to Git repository directory'
    )
    parser.add_argument(
        '--start-date',
        help='ISO8601 timestamp to filter commits from (inclusive)'
    )
    parser.add_argument(
        '--output',
        help='Path for output JSONL file'
    )

    args = parser.parse_args()

    # Check required arguments
    if not args.repo or not args.start_date or not args.output:
        parser.print_help()
        sys.exit(0)

    try:
        # Validate Git repository
        validate_repo(args.repo)

        # Fetch commits
        commit_lines = fetch_commits(args.repo, args.start_date)

        # Process commits
        commits = []
        for line in commit_lines:
            if line:
                commit = process_commit(line)
                if commit:
                    commits.append(commit)

        # Write output
        write_output(args.output, commits)

        print(f"Successfully exported {len(commits)} commits to {args.output}")
        sys.exit(0)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else "Unknown git error"
        print(f"Git command failed: {stderr_msg}", file=sys.stderr)
        sys.exit(1)
    except TypeError as e:
        # Handles non-serializable objects in commit records
        print(f"Error: JSON serialization error: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        # Handles file system errors including permission, disk full, etc.
        if e.errno == 28:  # ENOSPC - no space left on device
            msg = f"Error: No space left on device: {e}"
        elif e.errno == 13:  # EACCES - permission denied
            msg = f"Error: Permission denied: {e}"
        elif e.errno == 15:  # EIO - input/output error
            msg = f"Error: I/O error on device: {e}"
        else:
            msg = f"Error: File system error: {e}"
        print(msg, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
