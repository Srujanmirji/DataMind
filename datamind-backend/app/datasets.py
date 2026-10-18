import json

from app.config import Settings


def load_datasets(settings: Settings) -> dict[str, dict]:
    """Load trusted developer configuration only; dataset IDs never become paths."""
    datasets = {}
    for path in [settings.dataset_path, *settings.additional_dataset_paths]:
        dataset = json.loads(path.read_text())
        if dataset["id"] in datasets:
            raise ValueError("Duplicate dataset ID in configuration.")
        datasets[dataset["id"]] = dataset
    return datasets
