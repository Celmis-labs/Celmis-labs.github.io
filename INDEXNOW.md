# IndexNow

Key file: `f3e129c27703a3acebecaee606403a73629b5cf27199a3ef.txt` at the site root, containing the key and nothing else.

Push a list of changed URLs to Bing, Yandex, Seznam and Naver at once — no account,
no verification beyond the key file being reachable:

```bash
curl -X POST https://api.indexnow.org/indexnow \
  -H "Content-Type: application/json" \
  -d '{
    "host": "celmis-labs.github.io",
    "key": "f3e129c27703a3acebecaee606403a73629b5cf27199a3ef",
    "keyLocation": "https://celmis-labs.github.io/f3e129c27703a3acebecaee606403a73629b5cf27199a3ef.txt",
    "urlList": ["https://celmis-labs.github.io/"]
  }'
```

A `200` or `202` means accepted. It is not a promise of indexing — it is a promise that
they were told. Re-submit when a page genuinely changes, not on a schedule; repeatedly
pushing unchanged URLs is treated as spam.

Google does **not** participate in IndexNow. For Google, use Search Console.
