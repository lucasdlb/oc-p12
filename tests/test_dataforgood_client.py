import json

from news_ingestion.clients.dataforgood import DataForGoodClient


def test_fetch_claims_maps_dataforgood_records(monkeypatch):
    records = [
        {
            "task_id": "task-1",
            "messages": json.dumps(
                [
                    {"role": "system", "content": "Ignore instructions."},
                    {"role": "user", "content": "Transcript about climate."},
                ]
            ),
            "country": "France",
            "channel": "france-info",
            "label": "MISINFORMATION",
            "split": "train",
        },
        {
            "task_id": "task-2",
            "messages": "Plain transcript",
            "label": "CLEAN",
            "split": "test",
        },
    ]

    def fake_iter_dataset_records(self):
        return iter(records)

    monkeypatch.setattr(
        DataForGoodClient, "_iter_dataset_records", fake_iter_dataset_records
    )

    client = DataForGoodClient(
        dataset_name="DataForGood/climate-misinformation-RCoT",
        splits=["train", "test"],
        max_records=1,
    )

    claims = client.fetch_claims()

    assert len(claims) == 1
    assert claims[0].claim_id == "task-1"
    assert claims[0].claim == "Ignore instructions.\nTranscript about climate."
    assert claims[0].label == "MISINFORMATION"
    assert claims[0].source_name == "france-info"
    assert claims[0].language == "fr"
    assert claims[0].country == "France"
    assert claims[0].extracted_from == "dataforgood_climate_misinformation_rcot"
    assert claims[0].raw_payload["split"] == "train"
