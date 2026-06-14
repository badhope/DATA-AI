from data_vdb_vastbase.vastbase_vector import VastbaseVector, VastbaseVectorConfig

from core.rag.datasource.vdb.vector_integration_test_support import (
    AbstractVectorTest,
)


class VastbaseVectorTest(AbstractVectorTest):
    def __init__(self):
        super().__init__()
        self.vector = VastbaseVector(
            collection_name=self.collection_name,
            config=VastbaseVectorConfig(
                host="localhost",
                port=5434,
                user="data",
                password="DATAai123456",
                database="data",
                min_connection=1,
                max_connection=5,
            ),
        )


def test_vastbase_vector(setup_mock_redis):
    VastbaseVectorTest().run_all_tests()
