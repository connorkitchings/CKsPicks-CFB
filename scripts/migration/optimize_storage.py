#!/usr/bin/env python3
"""Script to optimize R2Storage with caching and parallel downloads."""

import re

# Read the file
with open("src/cks_picks_cfb/data/storage.py", "r") as f:
    content = f.read()

# Find the R2Storage class and replace its read_index method
# We'll add the new methods after _get_entity_partition_prefix

# The pattern to find the R2Storage._get_entity_partition_prefix and read_index
r2_pattern = r'(class R2Storage.*?def _get_entity_partition_prefix\(self, entity: str, partition: Partition\) -> str:\s*"""Get S3 prefix for entity partition\."""\s*return f"\{entity\}/\{partition\.path_suffix\(\)\}")'

# New methods to add
new_methods = '''

    def _get_cache_path(self, file_key: str) -> Path:
        """Get local cache path for an S3 file key."""
        safe_name = file_key.replace("/", "__")
        return self.cache_dir / safe_name

    def _download_file(self, file_key: str, use_cache: bool = True) -> bytes:
        """Download a file from R2 with caching support."""
        cache_path = self._get_cache_path(file_key)
        if use_cache and cache_path.exists():
            self._cache_hits += 1
            return cache_path.read_bytes()
        obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
        data = obj["Body"].read()
        if use_cache:
            cache_path.write_bytes(data)
            self._cache_misses += 1
        return data

    def _download_files_parallel(self, file_keys: list[str], use_cache: bool = True) -> dict[str, bytes]:
        """Download multiple files in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results: dict[str, bytes] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_key = {executor.submit(self._download_file, key, use_cache): key for key in file_keys}
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    print(f"Error downloading {key}: {e}")
        return results
'''

# Check if methods already exist
if "_get_cache_path" in content:
    print("Methods already exist, skipping...")
else:
    # Find the location after R2Storage._get_entity_partition_prefix
    # We need to be more specific - find R2Storage class specifically

    # Split by class definition
    parts = content.split("class R2Storage")
    if len(parts) != 2:
        print(f"Error: Found {len(parts) - 1} R2Storage classes, expected 1")
        exit(1)

    before_r2 = parts[0]
    r2_and_after = parts[1]

    # Find _get_entity_partition_prefix in R2Storage
    method_pattern = r'(def _get_entity_partition_prefix\(self, entity: str, partition: Partition\) -> str:\s*"""Get S3 prefix for entity partition\."""\s*return f"\{entity\}/\{partition\.path_suffix\(\)\}")'

    match = re.search(method_pattern, r2_and_after)
    if not match:
        print("Could not find _get_entity_partition_prefix in R2Storage")
        exit(1)

    # Insert new methods after _get_entity_partition_prefix
    insert_pos = match.end()
    new_r2 = r2_and_after[:insert_pos] + new_methods + r2_and_after[insert_pos:]

    # Now replace the read_index method in R2Storage
    old_read_index = '''    def read_index(
        self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Read records by entity and partition filters."""
        import io

        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        prefix = self._get_entity_partition_prefix(entity, partition)

        # List all files under this prefix
        files = self.list_files(prefix)

        if not files:
            return []

        # Look for parquet files first
        parquet_files = [f for f in files if f.endswith(".parquet")]

        if parquet_files:
            rows: list[dict[str, Any]] = []
            for file_key in parquet_files:
                try:
                    obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
                    buffer = io.BytesIO(obj["Body"].read())
                    table = pq.read_table(buffer, columns=columns)
                    rows.extend(table.to_pylist())
                except Exception as e:
                    print(f"Skipping unreadable file: {file_key} -> {e}")
                    continue
            return rows

        # Fall back to CSV files
        csv_files = [f for f in files if f.endswith("data.csv")]

        if csv_files:
            frames: list[pd.DataFrame] = []
            for file_key in csv_files:
                try:
                    obj = self.s3_client.get_object(Bucket=self.bucket, Key=file_key)
                    df = pd.read_csv(obj["Body"])
                    if columns:
                        df = df[columns]
                    frames.append(df)  # type: ignore[arg-type]
                except Exception as e:
                    print(f"Skipping unreadable CSV: {file_key} -> {e}")
                    continue
            if not frames:
                return []
            df_all = pd.concat(frames, ignore_index=True)
            return df_all.to_dict(orient="records")

        return []'''

    new_read_index = '''    def read_index(self, entity: str, filters: Mapping[str, Any], columns: list[str] | None = None, *, use_cache: bool = True, parallel: bool = True) -> list[dict[str, Any]]:
        """Read records by entity and partition filters with caching and parallel downloads."""
        import io
        partition_values = {k: str(v) for k, v in filters.items() if v is not None}
        partition = Partition(partition_values)
        prefix = self._get_entity_partition_prefix(entity, partition)
        files = self.list_files(prefix)
        if not files:
            return []
        parquet_files = [f for f in files if f.endswith(".parquet")]
        if parquet_files:
            rows: list[dict[str, Any]] = []
            if parallel and len(parquet_files) > 1:
                file_contents = self._download_files_parallel(parquet_files, use_cache=use_cache)
                for file_key, data in file_contents.items():
                    try:
                        buffer = io.BytesIO(data)
                        table = pq.read_table(buffer, columns=columns)
                        rows.extend(table.to_pylist())
                    except Exception as e:
                        print(f"Skipping unreadable file: {file_key} -> {e}")
            else:
                for file_key in parquet_files:
                    try:
                        data = self._download_file(file_key, use_cache=use_cache)
                        buffer = io.BytesIO(data)
                        table = pq.read_table(buffer, columns=columns)
                        rows.extend(table.to_pylist())
                    except Exception as e:
                        print(f"Skipping unreadable file: {file_key} -> {e}")
            return rows
        csv_files = [f for f in files if f.endswith("data.csv")]
        if csv_files:
            frames: list[pd.DataFrame] = []
            if parallel and len(csv_files) > 1:
                file_contents = self._download_files_parallel(csv_files, use_cache=use_cache)
                for file_key, data in file_contents.items():
                    try:
                        df = pd.read_csv(io.BytesIO(data))
                        if columns:
                            df = df[columns]
                        frames.append(df)
                    except Exception as e:
                        print(f"Skipping unreadable CSV: {file_key} -> {e}")
            else:
                for file_key in csv_files:
                    try:
                        data = self._download_file(file_key, use_cache=use_cache)
                        df = pd.read_csv(io.BytesIO(data))
                        if columns:
                            df = df[columns]
                        frames.append(df)
                    except Exception as e:
                        print(f"Skipping unreadable CSV: {file_key} -> {e}")
            if not frames:
                return []
            df_all = pd.concat(frames, ignore_index=True)
            return df_all.to_dict(orient="records")
        return []'''

    # Replace read_index in R2Storage portion only
    if old_read_index in new_r2:
        new_r2 = new_r2.replace(old_read_index, new_read_index, 1)
        print("Replaced read_index method")
    else:
        print("Warning: Could not find exact read_index match, may need manual fix")

    # Reconstruct the file
    new_content = before_r2 + "class R2Storage" + new_r2

    # Write back
    with open("src/cks_picks_cfb/data/storage.py", "w") as f:
        f.write(new_content)

    print("Successfully updated R2Storage with caching and parallel downloads!")

# Now let's also update the redundant reads in v2_recency.py
print("\nChecking v2_recency.py for redundant reads...")

with open("src/cks_picks_cfb/features/v2_recency.py", "r") as f:
    v2_content = f.read()

# Check if games is loaded twice
if v2_content.count('read_entity("games"') >= 2:
    print("Found multiple games reads in v2_recency.py - this will be fixed in Phase 2")
else:
    print("Games reads look OK")

print("\nDone!")
