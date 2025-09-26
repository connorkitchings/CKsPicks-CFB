"""Example Prefect flow demonstrating logging and task orchestration."""

from prefect import flow, task

from cfb_model.utils.logging import DataLogger

# Initialize the logger for this flow
_log = DataLogger(__name__)


@task
def fetch_data():
    """A task to simulate fetching raw data."""
    _log.log_event("FETCH", {"message": "Fetching raw data..."})
    raw_data = [{"id": 1, "value": 10}, {"id": 2, "value": 20}]
    _log.log_event("FETCH", {"message": f"Fetched {len(raw_data)} records"})
    return raw_data


@task
def process_data(data: list[dict]) -> list[dict]:
    """A task to simulate processing raw data."""
    _log.log_event("PROCESS", {"message": "Processing raw data"})
    processed_data = [
        {"id": item["id"], "processed_value": item["value"] * 2} for item in data
    ]
    _log.log_event("PROCESS", {"message": f"Processed {len(processed_data)} records"})
    return processed_data


@task
def save_data(data: list[dict]):
    """A task to simulate saving processed data."""
    _log.log_event("SAVE", {"message": f"Saving {len(data)} records"})
    # In a real scenario, this would write to a database, file, or data warehouse.
    _log.log_event("SAVE", {"message": "Data saved successfully"})


@flow(name="Example Data Processing Flow")
def example_data_flow():
    """An example data processing flow that fetches, processes, and saves data."""
    _log.log_event("FLOW", {"message": "Starting example flow"})
    raw_data = fetch_data()
    processed_data = process_data(raw_data)
    save_data(processed_data)
    _log.log_event("FLOW", {"message": "Example flow finished"})


if __name__ == "__main__":
    example_data_flow()
