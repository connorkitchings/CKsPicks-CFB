"""Utilities for OpenLineage data lineage tracking."""

import os

from openlineage.client import OpenLineageClient
from openlineage.client.facet import DataSourceDatasetFacet
from openlineage.client.run import Job, Run, RunEvent, RunState

# For local file-based lineage, we set the OL_URL to a file path.
# In a production environment, this would be the URL to your OpenLineage collector (e.g., Marquez).
# Example: os.environ['OPENLINEAGE_URL'] = 'http://my-marquez-instance:5000'
if 'OPENLINEAGE_URL' not in os.environ:
    os.environ['OPENLINEAGE_URL'] = './lineage.log'

NAMESPACE = "vibe-coding-template"

def get_lineage_client() -> OpenLineageClient:
    """Initializes and returns an OpenLineage client."""
    return OpenLineageClient.from_environment()

def emit_lineage_event(
    client: OpenLineageClient,
    job_name: str,
    run_state: RunState,
    run_id: str,
    input_datasets: list = None,
    output_datasets: list = None
) -> None:
    """
    Constructs and emits an OpenLineage RunEvent.

    Args:
        client: The OpenLineage client.
        job_name: The name of the job or process.
        run_state: The state of the run (e.g., START, COMPLETE, FAIL).
        run_id: A unique identifier for the run.
        input_datasets: A list of input datasets.
        output_datasets: A list of output datasets.
    """
    run = Run(runId=run_id)
    job = Job(namespace=NAMESPACE, name=job_name)

    event = RunEvent(
        eventType=run_state,
        run=run,
        job=job,
        inputs=input_datasets or [],
        outputs=output_datasets or [],
        producer="https://github.com/OpenLineage/OpenLineage/tree/main/integration/python"
    )
    client.emit(event)
    print(f"Emitted OpenLineage event: {job_name} - {run_state}")

# Example usage:
if __name__ == '__main__':
    from uuid import uuid4

    from openlineage.client.dataset import Dataset, Source
    from openlineage.client.facet import DataSourceDatasetFacet

    client = get_lineage_client()
    run_id = str(uuid4())
    job_name = "demo_lineage_job"

    # Define input and output datasets
    inputs = [
        Dataset(
            source=Source(producer_url="file://"),
            name="/data/raw/my_data.csv",
            facets={"dataSource": DataSourceDatasetFacet(name="raw_data", uri="file://data/raw")}
        )
    ]
    outputs = [
        Dataset(
            source=Source(producer_url="file://"),
            name="/data/processed/my_processed_data.csv",
            facets={"dataSource": DataSourceDatasetFacet(name="processed_data", uri="file://data/processed")}
        )
    ]

    # Emit START event
    emit_lineage_event(client, job_name, RunState.START, run_id, input_datasets=inputs)

    # ... your data processing logic would go here ...

    # Emit COMPLETE event
    emit_lineage_event(
        client, job_name, RunState.COMPLETE, run_id, output_datasets=outputs
    )
