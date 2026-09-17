# Source Exploration Report

## Objective

This document qualifies candidate data sources for a multimodal fake news detection data acquisition pipeline. The project requires publications or posts that keep textual content and related images associated in the same record, while also preserving useful metadata for downstream analysis, model training, traceability, and monitoring.

The exploration focuses on sources that are accessible through APIs, public datasets, or RSS feeds. Some selected sources are not strictly multimodal, but they are kept as complementary sources because they provide valuable misinformation labels or climate-related claims that can support later enrichment and evaluation.

## Selection Criteria

Each source is evaluated against the following criteria from the project guidelines:

- Source name and access method.
- Data type: text, image, metadata, labels, or mixed content.
- Format: CSV, JSON, API response, HTML page, PDF, RSS/XML, dataset files, or other.
- Language.
- Label quality, especially true/false or misinformation labels when available.
- Extraction method: REST API, scraping, Selenium, Scrapy, download, Hugging Face Datasets, or RSS.
- Usage rights and reliability.
- Expected output format.
- Ability to preserve text-image association in the same output record.

## Target Raw Output Schemas

The exploration led to two raw schemas.

### RawArticle

`RawArticle` is used for multimodal article or post sources.

| Field | Purpose |
| --- | --- |
| `article_id` | Source identifier or stable URL. |
| `title` | Main textual title or post title. |
| `link` | Source article/post URL. |
| `description` | Summary, abstract, or RSS description when available. |
| `content` | Full or partial text content when available. |
| `image_url` | URL of the associated image. |
| `published_at` | Publication date or source timestamp. |
| `source_id` | Technical source identifier, domain, feed, or subreddit. |
| `source_name` | Human-readable source name. |
| `language` | Language reported by the source or inferred from source selection. |
| `country` | Country or source country when available. |
| `category` | Topic, tag, subreddit label, or source category. |
| `extracted_from` | Name of the extraction source. |
| `raw_payload` | Original payload for traceability and later remapping. |

### RawClaim

`RawClaim` is used for labelled claim datasets that are useful for misinformation context but not necessarily multimodal.

| Field | Purpose |
| --- | --- |
| `claim_id` | Claim or task identifier. |
| `claim` | Claim text, transcript excerpt, or reconstructed message content. |
| `label` | Misinformation, support/refute, clean, or claim label when available. |
| `evidence` | Evidence snippets or supporting records when available. |
| `source_name` | Dataset, media channel, or source name. |
| `language` | Language of the claim. |
| `country` | Country when available. |
| `extracted_from` | Name of the extraction source. |
| `raw_payload` | Original dataset row for traceability and audit. |

## Source 1: NewsData.io

### Source Name And Access Method

NewsData.io is a news aggregation API available through HTTPS requests. Access requires an API key provided through `NEWS_DATA_API_KEY`.

### Data Type

- Text: article title, description, and partial content depending on plan limits.
- Image: `image_url` field when the source article provides an image.
- Metadata: publication date, source name, source URL, source priority, country, category, language, keywords, creator, duplicate flag, and additional API metadata.
- Labels: no native fake/real labels in the basic news API response.
- Mixed content: yes, when `title` or `description` and `image_url` are both present.

### Format

The source returns JSON over a REST-style API. Records are returned in a `results` array.

### Language

Multilingual API. The current project configuration uses English with climate/environment queries, but the API can be configured for other two-letter language codes such as `fr`.

### Label Quality

NewsData.io does not provide reliable misinformation labels in the accessible article response. The source is therefore useful for collecting current multimodal news records, not for supervised fake/real training labels by itself.

Reliability indicators such as `source_name`, `source_id`, `source_url`, `source_priority`, category, and duplicate status can still support later quality checks or weak labelling strategies.

### Extraction Method

REST API extraction with `GET` requests to `https://newsdata.io/api/1/news`. Query parameters include API key, query string, language, category, country, and pagination token. The extraction can filter records to keep only entries with both text and image.

### Usage Rights And Reliability

The API is official and more stable than scraping. It has quotas, plan limitations, and API key requirements. Full content and advanced AI fields may be restricted to paid plans. Usage must comply with NewsData.io terms and rate limits.

Reliability is good for structured metadata acquisition, but article completeness varies by source and subscription plan.

### Expected Output Format

JSON records using the shared `RawArticle` schema. The original API payload is preserved in `raw_payload` for auditability and future remapping.

### Multimodal Assessment

Selected as a primary multimodal source. It can provide title/description/content and an associated `image_url` in the same record.

### Decision

Keep as a primary automated source for recent climate-related multimodal news. Do not treat it as a labelled misinformation source unless external labelling or source reliability enrichment is added later.

## Source 2: GDELT 2.1 DOC API

### Source Name And Access Method

GDELT 2.1 DOC API is a public HTTP API accessible without an API key.

### Data Type

- Text: article title.
- Image: `socialimage` field when available.
- Metadata: URL, mobile URL, seen date, domain, language, and source country.
- Labels: no fake/real or misinformation labels.
- Mixed content: yes, when `title` and `socialimage` are both present.

### Format

The API returns JSON when requested with `format=json`. Article records are returned in an `articles` array.

### Language

Multilingual. The current configuration filters returned records by `English`, but the API can return content from many countries and languages.

### Label Quality

No misinformation labels are provided. GDELT is not a supervised fake news dataset. It is useful for broad, timely article discovery and source diversity.

### Extraction Method

REST-style `GET` request to `https://api.gdeltproject.org/api/v2/doc/doc`. Typical parameters include query, mode, format, maximum records, and sort order.

### Usage Rights And Reliability

GDELT is a public data platform with broad coverage and no API key requirement. It is generally reliable for article discovery, but it may return incomplete records, missing images, duplicated URLs, or articles only loosely related to the query. Filtering and validation are required downstream.

Usage must respect the public API service limits and should avoid excessive calls.

### Expected Output Format

JSON records using the shared `RawArticle` schema. The original GDELT record is preserved in `raw_payload`.

### Multimodal Assessment

Selected as a primary multimodal source when `title` and `socialimage` are present. It provides image URLs linked to the article URL in the same response item.

### Decision

Keep as a primary automated source because it is accessible, API-based, broad, and useful for collecting linked title-image news records. Add downstream relevance checks because query precision can vary.

## Source 3: RSS Feeds From News And Fact-Checking Websites

### Source Name And Access Method

RSS feeds are public XML feeds exposed by news publishers and fact-checking websites. The current candidate feeds include climate and fact-checking sources such as The Guardian climate feed, BBC Science and Environment, France 24 climate content, and PolitiFact fact checks.

### Data Type

- Text: entry title, summary, description, and feed metadata.
- Image: media tags, thumbnails, enclosures, or image links when exposed by the feed.
- Metadata: entry ID, article URL, publication date, feed title, tags, source domain, and feed URL.
- Labels: usually no structured fake/real label. Fact-checking feeds may contain rating information in article pages, but RSS entries do not always expose it consistently.
- Mixed content: yes, when an entry includes text fields and media/enclosure image URLs.

### Format

RSS or Atom XML parsed into Python dictionaries. Output is normalized to JSON.

### Language

Depends on the feed. The current set is mostly English, with potential French or multilingual sources depending on feed selection.

### Label Quality

RSS feeds from standard news sources have no misinformation labels. RSS feeds from fact-checking organizations may indicate fact-check context, but ratings are not guaranteed in the feed itself. If ratings are needed, a later extraction step may need to parse article pages or use a dedicated fact-checking API.

### Extraction Method

RSS parsing with `feedparser`. The extraction reads feed entries, maps text and metadata fields, extracts image URLs from `media_content`, `media_thumbnail`, `enclosures`, or `links`, and stores the feed URL with the original entry payload.

### Usage Rights And Reliability

RSS is designed for syndication and is less fragile than scraping HTML pages. It avoids brittle selectors and manual browsing. However, feed completeness and image availability vary by publisher. Usage must respect each publisher's terms, robots policies when following links, and copyright constraints on article content and images.

### Expected Output Format

JSON records using the shared `RawArticle` schema. The original parsed feed entry is preserved in `raw_payload` together with `feed_url`.

### Multimodal Assessment

Selected as a primary or secondary multimodal source. RSS feeds can provide linked text and image information in the same entry, but not all feeds or entries include images. Records without images should be filtered or flagged depending on the downstream use case.

### Decision

Keep as a flexible automated source for recent articles and fact-checking leads. Prefer RSS over scraping when available. Use it as a multimodal source only for entries where image extraction succeeds.

## Source 4: Fakeddit

### Source Name And Access Method

Fakeddit is a public multimodal fake news dataset based on Reddit posts. It is typically accessed by downloading dataset files from the project distribution or dataset hosting platforms, then reading local TSV files.

### Data Type

- Text: Reddit post titles and cleaned titles.
- Image: image URLs or processed image URL fields.
- Metadata: post ID, author, subreddit, domain, creation timestamp, score, number of comments, upvote ratio, linked submission ID, and source file name.
- Labels: multiple classification granularities, including binary labels and multi-class labels.
- Mixed content: yes, the multimodal subset is specifically designed to link text posts and image URLs.

### Format

TSV files such as `multimodal_train.tsv`, `multimodal_validate.tsv`, and `multimodal_test.tsv`.

### Language

Mostly English, because the source is Reddit-based and the dataset distribution is primarily English.

### Label Quality

Fakeddit provides structured labels at different granularities, including binary and multi-way labels. It is one of the strongest candidate sources for supervised fake news or misleading-content experiments because labels are available directly with each post.

The label definitions must be documented carefully before model training, because numeric labels need to be mapped to semantic classes. Dataset labels should not be treated as perfect ground truth without reviewing the original annotation methodology.

### Extraction Method

Dataset download followed by local TSV parsing. No scraping is required. The extraction reads rows from the configured files, maps text, image URL, subreddit, and labels to the shared article schema, and filters non-multimodal rows when required.

### Usage Rights And Reliability

The dataset is public research data, but usage must follow the dataset license and citation requirements. Some image URLs may become unavailable over time because they point to external Reddit or image-hosting resources. The dataset is stable as tabular data, but linked media availability should be validated.

### Expected Output Format

JSON records using the shared `RawArticle` schema. Labels are initially preserved in `category` and the full TSV row is preserved in `raw_payload`.

### Multimodal Assessment

Selected as a primary multimodal and labelled source. It directly satisfies the requirement to associate text, image, metadata, and fake/news-style labels in the same record.

### Decision

Keep as the strongest supervised multimodal source. It should be used for labelled examples, while live news APIs and RSS feeds provide fresher but mostly unlabelled records.

## Source 5: Climate-FEVER

### Source Name And Access Method

Climate-FEVER is a climate claim verification dataset available through Hugging Face Datasets, currently referenced as `tdiggelm/climate_fever`.

### Data Type

- Text: climate-related claims and evidence snippets.
- Image: none in the dataset records used by this project.
- Metadata: claim IDs, evidence IDs, evidence article titles, entropy, votes, and dataset split.
- Labels: claim/evidence support information depending on fields available in the dataset version.
- Mixed content: no, this source is text-only for the current project use case.

### Format

Hugging Face Dataset records loaded into Python dictionaries, then exported to JSON.

### Language

English.

### Label Quality

The dataset is useful for climate misinformation and claim-verification context. It provides evidence-level labels or votes such as support, refute, or not enough information depending on the record. This makes it valuable for reasoning about claims, but it is not a multimodal fake news article dataset.

### Extraction Method

Dataset loading through the Hugging Face `datasets` package. Access may optionally use `HF_TOKEN` depending on environment and dataset access requirements.

### Usage Rights And Reliability

Hugging Face provides stable dataset access when the dataset is available and compatible with the installed `datasets` version. Usage must respect the dataset card, license, and citation requirements. The dataset is reliable for claim-verification experiments but does not provide live news coverage or image data.

### Expected Output Format

JSON records using the shared `RawClaim` schema. Original rows are preserved in `raw_payload`.

### Multimodal Assessment

Not selected as a primary multimodal source. It does not provide image URLs or image files associated with the claims.

### Decision

Keep as a complementary labelled text source. It can support climate-specific claim analysis, label interpretation, and future transformation/evaluation tasks, but it does not satisfy the multimodal requirement alone.

## Source 6: DataForGood Climate Misinformation RCoT

### Source Name And Access Method

DataForGood climate misinformation RCoT is a Hugging Face dataset referenced as `DataForGood/climate-misinformation-RCoT`.

### Data Type

- Text: TV transcript messages, prompts, and climate-related claim analysis content.
- Image: none in the records used by this project.
- Metadata: task ID, country, media channel, split, token/cache metadata, and raw message structure.
- Labels: labels such as `MISINFORMATION` and `CLEAN`.
- Mixed content: no, this source is text-only for the current project use case.

### Format

Hugging Face Dataset records loaded into Python dictionaries. Some fields, such as `messages`, may contain JSON-encoded strings that need parsing.

### Language

French in the currently observed records, with country and channel metadata such as France-based TV or news channels.

### Label Quality

The dataset contains explicit climate misinformation labels, which makes it valuable for supervised text classification or evaluation of climate misinformation detection. However, the source is transcript-oriented and does not include images linked to the text.

The prompt and instruction text included in the message records should be handled carefully during transformation so that training data does not accidentally include system instructions as claim content unless intentionally retained for audit.

### Extraction Method

Dataset loading through the Hugging Face `datasets` package, followed by message parsing and normalization into `RawClaim` records.

### Usage Rights And Reliability

Dataset accessibility depends on Hugging Face availability and the dataset's access rules. Usage must respect the dataset card, license, and citation requirements. The source is reliable for labelled text records but not for multimodal acquisition.

### Expected Output Format

JSON records using the shared `RawClaim` schema. The original dataset row is preserved in `raw_payload` for auditability.

### Multimodal Assessment

Not selected as a primary multimodal source. It does not contain associated images.

### Decision

Keep as a complementary labelled text source because it provides climate misinformation labels and French-language coverage. It should be combined with multimodal sources rather than used as proof of multimodal extraction.

## Comparative Summary

| Source | Access | Main Format | Text | Image | Labels | Language | Multimodal Status | Role In Project |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NewsData.io | REST API with API key | JSON | Yes | Yes, when `image_url` is present | No fake/real labels | Multilingual, configured EN | Multimodal when image exists | Primary live news source |
| GDELT 2.1 DOC API | Public REST API | JSON | Title | Yes, when `socialimage` is present | No fake/real labels | Multilingual, configured EN | Multimodal when image exists | Primary broad news discovery source |
| RSS feeds | Public RSS/Atom feeds | XML parsed to dict/JSON | Yes | Sometimes via media/enclosures | Usually no structured labels | Depends on feed | Multimodal when feed image exists | Flexible current-news and fact-checking source |
| Fakeddit | Downloaded public dataset | TSV | Yes | Yes in multimodal subset | Yes | Mostly EN | Multimodal | Primary labelled multimodal dataset |
| Climate-FEVER | Hugging Face Dataset | Dataset/JSON | Yes | No | Yes, claim/evidence labels | EN | Not multimodal | Complementary labelled claim source |
| DataForGood climate misinformation RCoT | Hugging Face Dataset | Dataset/JSON | Yes | No | Yes, misinformation labels | FR | Not multimodal | Complementary labelled text source |

## Final Source Qualification Decision

The sources selected for the Step 2 automated extraction work are divided into two groups.

### Primary Multimodal Sources

- Fakeddit: selected because it provides text, images, metadata, and labels in the same dataset records.
- NewsData.io: selected because it provides recent news articles with text fields and image URLs through a stable API.
- GDELT 2.1 DOC API: selected because it provides broad international article discovery with linked title and social image records.
- RSS feeds: selected because they provide a low-friction, legally safer alternative to scraping and can expose title, summary, metadata, and images in the same feed entry.

### Complementary Labelled Text Sources

- Climate-FEVER: kept for English climate claim verification labels and evidence context, but not used as a standalone multimodal source.
- DataForGood climate misinformation RCoT: kept for French climate misinformation labels and transcript-based examples, but not used as a standalone multimodal source.

## Risks And Vigilance Points

- Do not confuse controversial opinions with misinformation. Only false or misleading claims with evidence or labels should be treated as misinformation.
- Do not treat NewsData.io, GDELT, or generic RSS articles as fake news labels without additional verification.
- Verify that each multimodal output record keeps text and image URL linked in the same JSON object.
- Validate image availability later because external URLs may expire, redirect, block hotlinking, or return non-image content.
- Respect API limits, dataset licenses, publisher rights, and dataset citation requirements.
- Avoid fragile scraping when API, RSS, or public dataset access is available.
- Preserve `raw_payload` for traceability, debugging, and future schema evolution.

## Operational Source Limitations

Live and dataset sources do not fail in the same way. The pipeline must treat source failures as source-level events rather than immediately assuming the full ETL run is unusable.

### NewsData.io

- Requires `NEWS_DATA_API_KEY`.
- API quotas and rate limits depend on the subscription plan.
- Full content, advanced fields, and historical access can be restricted by plan.
- Temporary HTTP failures, quota errors, DNS failures, or API-side errors can happen independently of the rest of the pipeline.
- Logs must never expose the API key or full URLs containing the `apikey` query parameter.

### GDELT 2.1 DOC API

- Public API access should remain moderate and respectful of service limits.
- Query precision varies; broad climate queries may return noisy but relevant-adjacent records.
- Image coverage depends on whether `socialimage` is present in the returned article metadata.
- Temporary HTTP or JSON response failures should not block RSS or other sources from being processed.

### RSS Feeds

- Feed availability, structure, and image metadata vary by publisher.
- Individual feeds can be malformed, temporarily unavailable, or omit images.
- RSS parsing failures are handled per feed inside the RSS extractor where possible.
- Publisher terms, copyright constraints, and robots policies still apply when following article links.

### Hugging Face Datasets

- Climate-FEVER and DataForGood availability depends on Hugging Face service availability, dataset access rules, and optional token configuration.
- These sources provide useful labelled text records but are not standalone multimodal sources.
- Dataset schema changes upstream can require mapper updates.

### Fakeddit

- The tabular dataset is stable, but image URLs point to external hosts and may decay over time.
- Local TSV files must be downloaded before extraction.
- Image validation may reject records whose linked media is no longer reachable.

## Source Failure Policy

The live Airflow extraction tolerates partial source failures. NewsData.io, GDELT, and RSS are attempted independently; the live extraction succeeds when at least one live source writes raw output for the run. Failed source names, error details, output paths, record counts, and durations are emitted in structured logs.

If every live source fails, the task fails and downstream transform/load tasks are not executed. This prevents loading an empty run while still allowing successful source output to be transformed when another source is temporarily unavailable.

Single-source scripts remain strict: when a script targets one source, that source must succeed.

## Step 1 Conclusion

The exploration identifies more than the required minimum of three relevant sources. Four sources can support multimodal extraction directly: Fakeddit, NewsData.io, GDELT, and RSS feeds. Two additional text-only sources, Climate-FEVER and DataForGood climate misinformation RCoT, are kept because they provide valuable misinformation labels and climate-specific context. This combination balances multimodal acquisition, source diversity, current news coverage, and labelled misinformation examples for later transformation and evaluation steps.
