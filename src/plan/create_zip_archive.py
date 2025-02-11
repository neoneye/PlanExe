import zipfile
import os

def create_zip_archive(directory_to_zip: str) -> str:
    """
    Creates a zip archive of the given directory, excluding 'log.txt'.
    Returns the path to the zip file, or None if an error occurred.
    """
    zip_file_path = os.path.join(os.path.dirname(directory_to_zip), os.path.basename(directory_to_zip) + ".zip")
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(directory_to_zip):
                for file in files:
                    if file == "log.txt":
                        continue  # Skip the log file

                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, directory_to_zip))
        return zip_file_path
    except Exception as e:
        print(f"Error creating zip archive: {e}")
        return None

if __name__ == "__main__":
    dir_path = os.path.join(os.path.dirname(__file__), '..', 'expert', 'test_data')
    zip_path = create_zip_archive(dir_path)
    print(f"Zip archive created at: {zip_path}")