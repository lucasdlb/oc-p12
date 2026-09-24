from news_ingestion.clients.fakeddit import FakedditClient


def test_load_articles_reads_fakeddit_tsv_and_filters_multimodal(tmp_path):
    dataset_dir = tmp_path / "Fakeddit"
    dataset_dir.mkdir()
    tsv_path = dataset_dir / "sample.tsv"
    tsv_path.write_text(
        "id\ttitle\timage_url\tsubreddit\t2_way_label\turl\n"
        "post-1\tA multimodal fake post\thttps://example.com/image.jpg\tnews\tfake\thttps://reddit.example/post-1\n"
        "post-2\tA text-only post\t\tnews\treal\thttps://reddit.example/post-2\n",
        encoding="utf-8",
    )

    client = FakedditClient(
        dataset_dir=dataset_dir,
        files=["sample.tsv"],
        max_records=10,
        only_multimodal=True,
        validate_image_urls=False,
    )

    articles = client.load_articles()

    assert len(articles) == 1
    assert articles[0].article_id == "post-1"
    assert articles[0].title == "A multimodal fake post"
    assert articles[0].content is None
    assert articles[0].image_url == "https://example.com/image.jpg"
    assert articles[0].source_name == "news"
    assert articles[0].category == ["fake"]
    assert articles[0].extracted_from == "fakeddit"
    assert articles[0].raw_payload["file_name"] == "sample.tsv"


def test_load_articles_raises_for_missing_fakeddit_file(tmp_path):
    client = FakedditClient(
        dataset_dir=tmp_path / "Fakeddit",
        files=["missing.tsv"],
        max_records=10,
        only_multimodal=True,
        validate_image_urls=False,
    )

    try:
        client.load_articles()
    except FileNotFoundError as exc:
        assert "missing.tsv" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_load_articles_validates_files_before_applying_record_limit(tmp_path):
    dataset_dir = tmp_path / "Fakeddit"
    dataset_dir.mkdir()
    (dataset_dir / "first.tsv").write_text(
        "id\ttitle\timage_url\npost-1\tTitle\thttps://example.com/image.jpg\n",
        encoding="utf-8",
    )
    client = FakedditClient(
        dataset_dir=dataset_dir,
        files=["first.tsv", "missing.tsv"],
        max_records=1,
        only_multimodal=True,
        validate_image_urls=False,
    )

    try:
        client.load_articles()
    except FileNotFoundError as exc:
        assert "missing.tsv" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
