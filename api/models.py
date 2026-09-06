from django.db import models


class AuditLog(models.Model):
    """One row every time someone searches, from the API or from the tests."""

    # what was asked and when
    created_at = models.DateTimeField(auto_now_add=True)
    question = models.TextField()
    source = models.CharField(max_length=10, default="api")  # "api" or "test"
    test_id = models.CharField(max_length=10, blank=True, default="")

    # what happened
    outcome = models.CharField(max_length=20)
    # what PolicyRetriever itself said - "supported" or "fallback"
    retriever_status = models.CharField(max_length=20, blank=True, default="")
    fallback_reason = models.CharField(max_length=50, blank=True, default="")
    top_score = models.FloatField(null=True, blank=True)
    num_results = models.IntegerField(default=0)
    time_taken_ms = models.IntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    # which model was used
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=30, blank=True, default="")

    # the retrieval settings that were used
    collection_name = models.CharField(max_length=100)
    chunks_indexed = models.IntegerField(null=True, blank=True)
    top_k = models.IntegerField()
    min_score = models.FloatField()
    ambiguous_gap = models.FloatField()

    # All of the above squashed into one short line. If two test runs have
    # the same summary you can compare their scores. If they don't, the
    # setup changed and the numbers don't mean the same thing.
    config_summary = models.CharField(max_length=200)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.created_at.strftime("%d/%m/%Y %H:%M") + " - " + self.question[:50]


class AuditChunk(models.Model):
    """One row for each piece of evidence that came back for a question."""

    audit = models.ForeignKey(AuditLog, related_name="chunks", on_delete=models.CASCADE)

    rank = models.IntegerField()
    chunk_id = models.CharField(max_length=50, blank=True, default="")
    document_id = models.CharField(max_length=20, blank=True, default="")
    policy_title = models.CharField(max_length=200)
    section = models.CharField(max_length=200, blank=True, default="")
    subsection = models.CharField(max_length=200, blank=True, default="")

    # links so a person can go and check the policy themselves
    source_url = models.CharField(max_length=500, blank=True, default="")
    status_details_url = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=30, blank=True, default="")
    effective_date = models.CharField(max_length=50, blank=True, default="")

    score = models.FloatField()
    text_snippet = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return str(self.rank) + ". " + self.chunk_id
