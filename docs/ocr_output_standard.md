# OCR Output Standard for Agreement Voting

This document defines the required output format for every full-book OCR model
run. Follow it exactly so the next phase can compare models page by page and run
agreement/voting without model-specific cleanup.

## Required Directory Layout

Every model must write one run directory:

```text
outputs/ocr_runs/<model_name>/<run_id>/
├── manifest.jsonl
├── pages_text/<book_id>/page_0001.txt
├── pages_text/<book_id>/page_0002.txt
├── pages_json/<book_id>/page_0001.json
├── pages_json/<book_id>/page_0002.json
├── books_text/<book_id>.txt
└── logs/<book_id>/
```

Use lowercase ASCII for `<model_name>`, for example `kandianguji`, `gjcool`,
`olmocr`, or `qwen_vl`. Use a stable run id that includes the model and purpose,
for example `kandianguji-full-001` or `gjcool-full-001`.

`<book_id>` must be the normalized PDF stem. The existing runner converts spaces
to underscores and removes filesystem-unsafe characters. For book 1, the id is:

```text
越南汉文燕行文献集成_第1册-1
```

## Required Files

### `pages_text/<book_id>/page_NNNN.txt`

One UTF-8 text file per PDF page. The file must contain only the OCR text for
that page.

Rules:

- Preserve the model output order, but the expected logical reading order for
  historical vertical Chinese pages is defined below.
- Do not manually correct OCR text.
- Do not add Markdown headings, page labels, comments, or confidence text.
- Use an empty file for a page that the model processed but returned no text.
- Use four-digit page numbers: `page_0001.txt`, `page_0418.txt`.

### Reading Order Rules

Most pages in this corpus are vertical classical Chinese text. Convert the page
image into plain text using this order:

1. Main vertical body text is read **top to bottom inside each column**.
2. Columns are ordered **right to left across the page**.
3. If a page has multiple main text blocks, process the rightmost/topmost block
   first, then continue right-to-left and top-to-bottom by block.
4. Marginal headers, running titles, folio/page numbers, seals, and captions
   should be kept if the model returns them. Put them after the main body text
   unless the model clearly integrates them into the main reading order.
5. Horizontal modern text, if present, is read left-to-right and top-to-bottom.
6. Do not insert spaces between Chinese characters. Keep punctuation only when
   the model outputs it.
7. Prefer one output line per detected vertical column or text block. Do not wrap
   long lines just to fit screen width.

The goal is a stable plain-text sequence for page-level agreement. We are not
doing diplomatic layout reconstruction in this phase.

Small example:

```text
二堂禀乞歩錢予知甚已於請故不之辞至期督撫各備車駕
應候各各叙别起程一途所歷督撫已預為舘席無一缺者
```

### Image-Backed Example

Reference image:

```text
artifacts/page_samples/page_320.pdf.png
```

This page has vertical main text columns. A contributor should read each column
from top to bottom, then move from the rightmost column to the leftmost column.
The marginal running title and printed page number are kept after the main body
if the model returns them.

Corresponding required page text path:

```text
outputs/ocr_runs/<model_name>/<run_id>/pages_text/越南汉文燕行文献集成_第1册-1/page_0320.txt
```

KanDianGuJi example output for that image:

```text
二堂禀乞歩餞子知其已片請故不之辞至期有
撫各備車駕應候各各叙别起程一途所歴督撫
已州預爲館席無一欽者清山秀水触目有情乙
使官僚均有函大星槎别概另叙使程手録不贅
至京之日屈指凡三箇月餘三月矣予至馆督撫
已先向政府要早陛見訖囬館禀曰使事今次先
生若有所要小生經己面奏並商諸政府矣高請
先生預備手章以便陛見辰陳請予颌之久早予
率乙部及官僚隨行人等先八政府面謁訂日陛
阮公基使程日錄
一八一
```

This is an OCR output example, not a corrected ground truth transcription.

### `pages_json/<book_id>/page_NNNN.json`

One UTF-8 JSON file per PDF page containing the raw model response or a
model-neutral wrapper around it. Keep all fields returned by the model when
possible.

Minimum wrapper when the raw model response is not JSON:

```json
{
  "model": "example_model",
  "raw_text": "二堂禀乞歩錢予知甚已於請故不之辞",
  "raw_response": null,
  "metadata": {
    "image_size": 800,
    "endpoint": "local-or-hosted-model-name"
  }
}
```

If the model returns bounding boxes, preserve them in `pages_json`; do not put
bounding-box data in `pages_text`.

Image-backed JSON example for page 320:

```json
{
  "data": [
    "二堂禀乞歩餞子知其已片請故不之辞至期有",
    "撫各備車駕應候各各叙别起程一途所歴督撫",
    "已州預爲館席無一欽者清山秀水触目有情乙",
    "使官僚均有函大星槎别概另叙使程手録不贅",
    "至京之日屈指凡三箇月餘三月矣予至馆督撫",
    "已先向政府要早陛見訖囬館禀曰使事今次先",
    "生若有所要小生經己面奏並商諸政府矣高請",
    "先生預備手章以便陛見辰陳請予颌之久早予",
    "率乙部及官僚隨行人等先八政府面謁訂日陛",
    "阮公基使程日錄",
    "一八一"
  ],
  "id": "example-response-id",
  "info": "",
  "message": "success"
}
```

### `manifest.jsonl`

JSON Lines file with one row per page attempt. On resume, skipped rows are
allowed, but the latest non-skipped row for each page is the row used for voting
readiness.

Required fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `model` | string | yes | Stable model name matching `<model_name>`. |
| `run_id` | string | yes | Run directory id. |
| `book_id` | string | yes | Normalized book id. |
| `source_pdf` | string | yes | Source PDF path relative to repo when possible. |
| `page_number` | integer | yes | One-based PDF page number. |
| `status` | string | yes | One of `ok`, `blank`, `error`, `skipped`. |
| `text_path` | string or null | yes | Path to the page text file. |
| `json_path` | string or null | yes | Path to the page JSON file. |
| `char_count` | integer | yes | Number of Python/Unicode characters in page text. |
| `wall_time_seconds` | number | yes | End-to-end page OCR time. Use `0.0` for skipped pages. |
| `error` | string or null | yes | Error log path or message for failed pages. |

Recommended optional fields:

| Field | Type | Meaning |
|---|---|---|
| `image_size` | integer | Long-side image size sent to OCR. |
| `temperature` | number | Generation temperature, if applicable. |
| `prompt_name` | string | Prompt or template identifier, if applicable. |
| `hardware` | string | GPU/CPU/server label, if known. |
| `api_attempts` | integer | Number of attempts used for the page. |

Example rows:

```jsonl
{"model":"kandianguji","run_id":"kandianguji-full-001","book_id":"越南汉文燕行文献集成_第1册-1","source_pdf":"books/越南汉文燕行文献集成 第1册-1.pdf","page_number":1,"status":"ok","text_path":"outputs/ocr_runs/kandianguji/kandianguji-full-001/pages_text/越南汉文燕行文献集成_第1册-1/page_0001.txt","json_path":"outputs/ocr_runs/kandianguji/kandianguji-full-001/pages_json/越南汉文燕行文献集成_第1册-1/page_0001.json","char_count":154,"wall_time_seconds":25.751,"error":null}
{"model":"kandianguji","run_id":"kandianguji-full-001","book_id":"越南汉文燕行文献集成_第1册-1","source_pdf":"books/越南汉文燕行文献集成 第1册-1.pdf","page_number":2,"status":"blank","text_path":"outputs/ocr_runs/kandianguji/kandianguji-full-001/pages_text/越南汉文燕行文献集成_第1册-1/page_0002.txt","json_path":"outputs/ocr_runs/kandianguji/kandianguji-full-001/pages_json/越南汉文燕行文献集成_第1册-1/page_0002.json","char_count":0,"wall_time_seconds":8.214,"error":null}
{"model":"example_model","run_id":"example-full-001","book_id":"越南汉文燕行文献集成_第1册-1","source_pdf":"books/越南汉文燕行文献集成 第1册-1.pdf","page_number":3,"status":"error","text_path":null,"json_path":null,"char_count":0,"wall_time_seconds":240.0,"error":"outputs/ocr_runs/example_model/example-full-001/logs/越南汉文燕行文献集成_第1册-1/page_0003.error.txt"}
```

### `books_text/<book_id>.txt`

Combined text for easy reading. It must be generated from `pages_text` without
manual edits.

Required format:

```text
=== page_0001 ===
<text from pages_text/<book_id>/page_0001.txt>

=== page_0002 ===
<text from pages_text/<book_id>/page_0002.txt>
```

## Status Rules

- `ok`: model returned non-empty OCR text and both text/json files were written.
- `blank`: model completed but returned empty text; write an empty text file and
  a raw JSON file.
- `error`: page failed after retries; write an error log if possible.
- `skipped`: resume mode found an existing complete text output and did not call
  the model.

For agreement voting, a book is ready only when every page has a latest
non-skipped row with status `ok` or `blank`. Any `error` page must be retried or
explicitly accepted as missing before voting.

## Contributor Checklist

Before handing off a model run, verify:

```text
[ ] The run has one `pages_text` file for every PDF page.
[ ] The run has one `pages_json` file for every processed page.
[ ] `manifest.jsonl` has required fields on every row.
[ ] Latest non-skipped rows cover every page from 1 to the PDF page count.
[ ] There are no latest `error` rows unless the team agrees to treat them as missing.
[ ] `books_text/<book_id>.txt` contains one `=== page_NNNN ===` section per page.
[ ] No API tokens or secrets appear in JSON, logs, README, or committed files.
```

## Current Completed Reference Run

Book 1 has a completed KanDianGuJi run in this format:

```text
outputs/ocr_runs/kandianguji/kandianguji-full-001/
```

Verified state:

```text
418 / 418 pages covered
409 ok pages
9 blank pages
0 error pages
418 page text files
418 raw JSON files
418 combined book-text sections
```

Other model owners should use this run as the concrete reference for naming,
paths, and manifest shape.
