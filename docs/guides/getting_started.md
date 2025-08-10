# Getting Started

This guide provides instructions for setting up your local development environment to work on the
**cfb_model** project.

## Prerequisites

- **Python 3.12+**: Ensure you have a compatible Python version installed.
- **Git**: For version control.
- **`uv`**: The project's package manager. If you don't have it, install it with `pip install uv`.
- **CollegeFootballData.com API Key**: You will need an API key to access the data source.

## 1. Clone the Repository

Clone this repository to your local machine:

```bash
git clone https://github.com/connorkitchings/cfb_model.git
cd cfb_model
```

## 2. Set Up Environment Variables

Create a `.env` file in the root of the project directory. This file is ignored by Git and will hold
your secret credentials. Add the following keys to it:

```bash
# .env
CFBD_API_KEY="your_api_key_here"
```

Replace the placeholder values with your actual credentials.

## 3. Set Up the Virtual Environment

This project uses `uv` for package and environment management. Create and activate a virtual environment:

```bash
# Create a virtual environment named .venv
uv venv

# Activate the environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

## 4. Install Dependencies

Install all required project dependencies using `uv`:

```bash
uv sync
```

## 5. Code Quality

Run formatting and lint checks before committing changes:

```bash
uv run ruff format .
uv run ruff check .
```

## 6. Run the Tests

Verify that the setup is correct by running the initial test suite:

```bash
uv run pytest
```

## 7. View the Documentation

To serve the documentation site locally, run the following command:

```bash
mkdocs serve
```

Then, open your browser to `http://127.0.0.1:8000` to view the documentation.

You are now ready to start developing!
