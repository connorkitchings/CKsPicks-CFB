# src/flows/example_flow.py

from prefect import flow, task

from src.utils.logging import DataLogger

# Initialize the logger for this flow
logger = DataLogger(logger_name="ExampleFlowLogger", log_to_file=False)


@task
def fetch_data():
    """A task to simulate fetching raw data."""
    logger.info("Fetching raw data...")
    raw_data = [{"id": 1, "value": 10}, {"id": 2, "value": 20}]
    logger.info("Successfully fetched %d records.", len(raw_data))
    return raw_data


@task
def process_data(data: list[dict]) -> list[dict]:
    """A task to simulate processing raw data."""
    logger.info("Processing raw data...")
    processed_data = [{"id": item["id"], "processed_value": item["value"] * 2} for item in data]
    logger.info("Successfully processed %d records.", len(processed_data))
    return processed_data


@task
def save_data(data: list[dict]):
    """A task to simulate saving processed data."""
    logger.info("Saving %d records...", len(data))
    # In a real scenario, this would write to a database, file, or data warehouse.
    logger.info("Data saved successfully.")


@flow(name="Example Data Processing Flow")
def example_data_flow():
    """An example data processing flow that fetches, processes, and saves data."""
    logger.info("Starting the example data processing flow.")

    raw_data = fetch_data()
    processed_data = process_data(raw_data)
    save_data(processed_data)

    logger.info("Example data processing flow finished successfully.")


if __name__ == "__main__":
    example_data_flow()
