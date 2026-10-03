# S5-06 policy currency fixtures

`baseline.html` and `status.html` are captured public La Trobe Policy Library
responses for Assessment Policy (document 216). `source.json` records URLs,
capture time and SHA-256 hashes. Preserve their bytes, including line endings.
Policy content remains the intellectual property of La Trobe University.

The verification script replays these responses through the existing processor.
It creates a **synthetic test revision**, changing the feedback clause and
removing section 8 to reduce the chunk count. This is not an actual university
policy revision. Its original URL and Current metadata are deliberately retained
inside an isolated temporary test index to exercise production filtering.

Never copy the synthetic revision into `data/processed/corpus`, the production
chunk directory, or the application index. The fixture directory is outside all
default ingestion paths. No university website is modified.

For a new source capture, fetch both URLs in `source.json`, verify that both
remain on `policies.latrobe.edu.au`, record the capture time, and recompute the
SHA-256 of the exact UTF-8 response bytes. Review the revision anchors before
rerunning. A changed anchor fails the test rather than silently changing its scope.
