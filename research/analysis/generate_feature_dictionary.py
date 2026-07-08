"""
Generates a Markdown feature dictionary from a Parquet dataset.

This script inspects a dataset to create documentation about the available
features, including their data types, null percentages, and basic statistics.
"""

import argparse

import pandas as pd


def generate_dictionary(input_path: str, output_path: str):
    """
    Loads a Parquet file and generates a Markdown feature dictionary.

    Args:
        input_path: Path to the input Parquet file.
        output_path: Path to save the output Markdown file.
    """
    print(f"Loading dataset from {input_path}...")
    try:
        df = pd.read_parquet(input_path)
    except Exception as e:
        print(f"Error loading Parquet file: {e}")
        return

    print("Generating feature dictionary...")
    feature_data = []
    for col in sorted(df.columns):
        dtype = str(df[col].dtype)
        null_percentage = df[col].isnull().mean() * 100
        stats = ""
        if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(
            df[col]
        ):
            mean = df[col].mean()
            std = df[col].std()
            min_val = df[col].min()
            max_val = df[col].max()
            stats = (
                f"Mean: {mean:.2f}, Std: {std:.2f},<br>"
                f"Min: {min_val:.2f}, Max: {max_val:.2f}"
            )
        else:
            unique_count = df[col].nunique()
            stats = f"Unique Values: {unique_count}"
            if 0 < unique_count <= 20:
                top_values = df[col].value_counts().nlargest(5).index.tolist()
                stats += f"<br>Top Values: {', '.join(map(str, top_values))}"
        feature_data.append(
            {
                "Feature": f"`{col}`",
                "Data Type": dtype,
                "Null %": f"{null_percentage:.2f}%",
                "Description / Stats": stats,
            }
        )

    md_content = "# Feature Dictionary\n\n"
    md_content += (
        f"Generated from `{input_path}`. Contains {len(df.columns)} features.\n\n"
    )
    md_content += "| Feature | Data Type | Null % | Description / Stats |\n"
    md_content += "|---|---|---|---|\n"
    for item in feature_data:
        md_content += (
            f"| {item['Feature']} "
            f"| {item['Data Type']} "
            f"| {item['Null %']} "
            f"| {item['Description / Stats']} |\n"
        )

    print(f"Saving feature dictionary to {output_path}...")
    with open(output_path, "w") as f:
        f.write(md_content)
    print("Done.")


def main():
    """Main function to parse arguments and run the script."""
    parser = argparse.ArgumentParser(
        description="Generate a Markdown feature dictionary from a Parquet dataset."
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Path to the input Parquet file."
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Path to save the output Markdown file."
    )
    args = parser.parse_args()
    generate_dictionary(args.input, args.output)


if __name__ == "__main__":
    main()
