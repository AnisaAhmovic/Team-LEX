from unittest import TestCase
from unittest.mock import MagicMock, patch

from ingestion import embedder
from ingestion.embedding_config import get_config
from retrieval.policy_retriever import PolicyRetriever


class EmbeddingDeviceTests(TestCase):
    def test_index_and_query_helpers_share_explicit_cpu_model(self):
        module = MagicMock()
        factory = module.SentenceTransformer
        with patch.object(embedder, '_model', None), patch.dict('sys.modules', {'sentence_transformers': module}):
            factory.return_value.encode.return_value.tolist.return_value = [[1.0, 0.0]]
            self.assertEqual(embedder.embed_texts(['policy passage']), [[1.0, 0.0]])
            self.assertEqual(embedder.embed_text('question'), [1.0, 0.0])
            factory.assert_called_once_with('BAAI/bge-m3', device='cpu')
            self.assertEqual(factory.return_value.encode.call_count, 2)
            self.assertEqual(get_config()['embedding_device'], 'cpu')
            self.assertEqual(PolicyRetriever().audit_config()['embedding_device'], 'cpu')
