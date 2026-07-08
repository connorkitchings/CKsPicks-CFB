import os
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import typer
from rich.console import Console

# --- Setup ---
console = Console()
REPO_ROOT = Path(__file__).parent.parent.parent
DATA_ROOT = os.getenv("CFB_MODEL_DATA_ROOT")

if not DATA_ROOT:
    console.print(
        "[bold red]Error: CFB_MODEL_DATA_ROOT environment variable is not set.[/bold red]"
    )
    raise typer.Exit(code=1)

RAW_DATA_PATH = Path(DATA_ROOT) / "raw"


# --- Functions ---
def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    """Sorts strings with numbers in a natural, human-friendly order."""
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def main(
    overwrite: bool = typer.Option(
        False, "--overwrite", "-o", help="Overwrite existing Parquet files."
    ),
    delete_csv: bool = typer.Option(
        False,
        "--delete-csv",
        "-d",
        help="Delete the source CSV file after successful conversion.",
    ),
):
    """
    Converts all raw data from CSV to Parquet format.

    This command scans the `data/raw` directory for subdirectories like 'games',
    'plays', etc., and converts all found CSV files to Parquet.
    """
    console.print("[bold]Starting raw data conversion from CSV to Parquet[/bold]")
    console.print(f"Data root: [blue]{DATA_ROOT}[/blue]")

    # List of directories to process
    raw_subdirs = [d for d in RAW_DATA_PATH.iterdir() if d.is_dir()]

    if not raw_subdirs:
        console.print("[yellow]No subdirectories found in raw data path.[/yellow]")
        return

    for subdir in raw_subdirs:
        convert_directory(subdir, overwrite, delete_csv)

    console.print("\n[bold green]Conversion complete![/bold green]")
    if delete_csv:
        console.print("[bold]Original CSV files have been deleted.[/bold]")
    else:
        console.print(
            "Original CSV files remain. Re-run with --delete-csv to remove them."
        )


def convert_directory(path: Path, overwrite: bool, delete_csv: bool):
    """
    Recursively finds all .csv files in a directory and converts them to .parquet.
    """
    console.print(f"Scanning directory: [cyan]{path}[/cyan]...")

    csv_files = list(path.rglob("*.csv"))

    if not csv_files:
        console.print("No CSV files found.")
        return

    with typer.progressbar(csv_files, label="Converting files") as progress:
        for csv_path in progress:
            # Ignore macOS metadata files
            if csv_path.name.startswith("._"):
                continue

            parquet_path = csv_path.with_suffix(".parquet")

            if parquet_path.exists() and not overwrite:
                continue

            try:
                # Read CSV and convert to Arrow Table to infer schema
                df = pd.read_csv(csv_path, low_memory=False)
                inferred_table = pa.Table.from_pandas(df, preserve_index=False)

                # If a 'week' column exists, enforce a consistent type for it.
                if "week" in inferred_table.schema.names:
                    fields = list(inferred_table.schema)
                    week_index = inferred_table.schema.get_field_index("week")
                    fields[week_index] = pa.field("week", pa.int64())
                    corrected_schema = pa.schema(fields)

                    # Create the final table using the corrected schema
                    final_table = pa.Table.from_pandas(
                        df, schema=corrected_schema, preserve_index=False
                    )
                else:
                    final_table = inferred_table

                pq.write_table(final_table, parquet_path, compression="snappy")

                if delete_csv:
                    csv_path.unlink()

            except Exception as e:
                console.print(
                    f"\n[bold red]Error converting {csv_path}: {e}[/bold red]"
                )


if __name__ == "__main__":
    typer.run(main)
