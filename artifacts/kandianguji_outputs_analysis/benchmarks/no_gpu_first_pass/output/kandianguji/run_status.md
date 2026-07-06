# KanDianGuJi Run Status

Date: 2026-06-29

Status: blocked by API transport/network errors from this environment.

Credentials:

- `KANDIANGUJI_TOKEN` is set in `.env`
- `KANDIANGUJI_EMAIL` is set in `.env`

Input attempted:

```text
benchmarks/no_gpu_first_pass/input_images_gjcool_1800/page_044.png
```

The runner was updated after checking the official API documentation:

- Uses documented Form Data submission rather than JSON.
- Uses `curl --http1.1` because Python `requests` repeatedly hit SSL EOF errors.
- Sends minimal working fields: `token`, `email`, `image`, `version=v2`, `image_size=800`.
- Uses 800px grayscale benchmark inputs to reduce upload and processing size.

Runner:

```bash
KANDIANGUJI_PAGES=44 uv run --with requests \
  python benchmarks/no_gpu_first_pass/run_kandianguji_api.py
```

Observed failures:

```text
requests.exceptions.SSLError:
HTTPSConnectionPool(host='ocr.kandianguji.com', port=443):
Max retries exceeded with url: /ocr_api
Caused by SSLEOFError: UNEXPECTED_EOF_WHILE_READING
```

After switching to documented Form Data with `curl --http1.1`, one manual page `044` request succeeded once, but repeated scripted runs failed intermittently with:

```text
curl: (52) Empty reply from server
curl: (28) Operation timed out with 0 bytes received
```

Earlier full run attempt failed with:

```text
requests.exceptions.ConnectionError:
Connection reset by peer
```

Connectivity probes:

```text
curl -L --http1.1 -I https://ocr.kandianguji.com/ocr_api
-> HTTP/1.1 405 METHOD NOT ALLOWED after about 79 seconds

curl -L -I http://ocr.kandianguji.com/ocr_api
-> redirects to HTTPS, then fails with LibreSSL SSL_ERROR_SYSCALL
```

Interpretation:

The token/email are valid enough for `/get_token_status`, and the documented request format is now implemented. The remaining issue is unstable API transport or server processing from this machine/network. Try running from another network/VPN, or run the same command from the GPU/server environment.
