import os

def concat_files_into_string(base_path: str, prefix: str="File: '", suffix: str="'\n", document_separator: str="\n\n") -> str:
    """
    Read the files, and concat their data into a single string
    """
    # Obtain files
    files = os.listdir(base_path)
    files = [f for f in files if not f.startswith('.')]
    files.sort()

    # Read the files, and concat their data into a single string
    documents = []
    for file in files:
        s = f"{prefix}{file}{suffix}"
        with open(os.path.join(base_path, file), 'r', encoding='utf-8') as f:
            s += f.read()
        documents.append(s)
    all_documents_string = document_separator.join(documents)
    return all_documents_string
