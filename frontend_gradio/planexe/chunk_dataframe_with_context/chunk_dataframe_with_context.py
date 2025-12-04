import pandas as pd
from typing import Generator, Tuple

def chunk_dataframe_with_context(
    df: pd.DataFrame, 
    chunk_size: int = 10, 
    overlap: int = 3
) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
    """
    Chunk the DataFrame into overlapping segments. For each core chunk,
    include 'overlap' rows before and after as additional context.

    Yields:
        (core_df, extended_df):
            core_df     = The rows we actually want to process in this chunk
            extended_df = core_df + overlap context before and after
    """
    start = 0
    total_rows = len(df)

    while start < total_rows:
        # Determine the start/end for the core chunk
        core_start = start
        core_end = min(start + chunk_size, total_rows)

        # Determine the start/end for the extended chunk
        extended_start = max(0, core_start - overlap)
        extended_end = min(core_end + overlap, total_rows)

        core_df = df.iloc[core_start:core_end]
        extended_df = df.iloc[extended_start:extended_end]

        yield core_df, extended_df

        start += chunk_size

if __name__ == "__main__":
    df = pd.DataFrame({
        "Task ID": range(1, 26),
        "Description": [f"Task {i}" for i in range(1, 26)]
    })
    for i, (core_df, extended_df) in enumerate(chunk_dataframe_with_context(df, chunk_size=5, overlap=2)):
        print(f"CHUNK {i} - Core:\n{core_df}\n\nContext:\n{extended_df}\n{'-'*40}")
