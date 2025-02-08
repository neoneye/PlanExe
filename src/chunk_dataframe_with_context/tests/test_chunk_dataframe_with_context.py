import unittest
import pandas as pd
from ..chunk_dataframe_with_context import chunk_dataframe_with_context

class TestChunkDataFrameWithContext(unittest.TestCase):
    def test_empty(self):
        # Arrange
        df = pd.DataFrame()
        df["Task ID"] = []
        df["Description"] = []

        # Act
        chunk_size = 5
        overlap = 2
        results = list(chunk_dataframe_with_context(df, chunk_size=chunk_size, overlap=overlap))

        # Assert
        # The number of chunks expected = ceil(0 / 5) = 0
        self.assertEqual(len(results), 0)

    def test_one_chunk_no_overlap(self):
        # Arrange
        df = pd.DataFrame({
            "Task ID": range(1, 4),
            "Description": [f"Task {i}" for i in range(1, 4)]
        })

        # Act
        chunk_size = 5
        overlap = 2
        results = list(chunk_dataframe_with_context(df, chunk_size=chunk_size, overlap=overlap))

        # Assert
        # The number of chunks expected = ceil(3 / 5) = 1
        self.assertEqual(len(results), 1)

        # Check the only chunk
        first_core, first_extended = results[0]
        self.assertEqual(first_core.iloc[0]["Task ID"], 1)
        self.assertEqual(first_core.iloc[-1]["Task ID"], 3)
        self.assertEqual(first_extended.iloc[0]["Task ID"], 1)
        self.assertEqual(first_extended.iloc[-1]["Task ID"], 3)

    def test_multiple_chunks(self):
        # Arrange
        # Create a sample DataFrame of 25 rows
        df = pd.DataFrame({
            "Task ID": range(1, 26),
            "Description": [f"Task {i}" for i in range(1, 26)]
        })

        # Act
        chunk_size = 5
        overlap = 2
        results = list(chunk_dataframe_with_context(df, chunk_size=chunk_size, overlap=overlap))

        # Assert
        # The number of chunks expected = ceil(25 / 5) = 5
        self.assertEqual(len(results), 5)

        # Check each chunk
        for i, (core_df, extended_df) in enumerate(results):
            # 1) core_df should have at most 5 rows (the chunk_size)
            self.assertTrue(len(core_df) <= chunk_size)

            # 2) extended_df should be larger or equal to core_df (due to overlap)
            self.assertTrue(len(extended_df) >= len(core_df))

            # 3) Check that extended_df contains core_df's indices
            #    (i.e., the extended rows are a superset of the core rows)
            core_indices = core_df.index.tolist()
            extended_indices = extended_df.index.tolist()

            for idx in core_indices:
                self.assertIn(idx, extended_indices)

        # First chunk
        first_core, first_extended = results[0]
        self.assertEqual(first_core.iloc[0]["Task ID"], 1)
        self.assertEqual(first_core.iloc[-1]["Task ID"], 5)
        self.assertEqual(first_extended.iloc[0]["Task ID"], 1)
        self.assertEqual(first_extended.iloc[-1]["Task ID"], 7)

        # Last chunk
        last_core, last_extended = results[-1]
        self.assertEqual(last_core.iloc[0]["Task ID"], 21)
        self.assertEqual(last_core.iloc[-1]["Task ID"], 25)
        self.assertEqual(last_extended.iloc[0]["Task ID"], 19)
        self.assertEqual(last_extended.iloc[-1]["Task ID"], 25)
