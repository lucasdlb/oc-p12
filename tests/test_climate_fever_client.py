from news_ingestion.climate_fever_client import ClimateFeverClient


def test_fetch_claims_maps_climate_fever_records(monkeypatch):
    records = [
        {
            "claim_id": 12,
            "claim": "Climate change is real.",
            "claim_label": "SUPPORTS",
            "evidences": [{"evidence_label": "SUPPORTS", "article": "Evidence"}],
        },
        {
            "claim_id": 13,
            "claim": "No image needed.",
            "claim_label": "NOT_ENOUGH_INFO",
        },
    ]

    def fake_load_records(self):
        return iter(records)

    monkeypatch.setattr(ClimateFeverClient, "_load_records", fake_load_records)

    client = ClimateFeverClient(
        dataset_name="tdiggelm/climate_fever",
        split="test",
        max_records=1,
    )

    claims = client.fetch_claims()

    assert len(claims) == 1
    assert claims[0].claim_id == "12"
    assert claims[0].claim == "Climate change is real."
    assert claims[0].label == "SUPPORTS"
    assert claims[0].evidence == [{"evidence_label": "SUPPORTS", "article": "Evidence"}]
    assert claims[0].source_name == "Climate-FEVER"
    assert claims[0].language == "en"
    assert claims[0].extracted_from == "climate_fever"
    assert claims[0].raw_payload["claim_id"] == 12
