import os
import json
import hashlib

METADATA_FILE = "vector_store/index_metadata.json"


def get_pdf_state(pdf_directory):

    pdfs = []

    for filename in sorted(os.listdir(pdf_directory)):

        if filename.endswith(".pdf"):

            path = os.path.join(pdf_directory, filename)

            stat = os.stat(path)

            pdfs.append({
                "file": filename,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })

    text = json.dumps(pdfs, sort_keys=True)

    return hashlib.md5(text.encode()).hexdigest()


def metadata_exists():

    return os.path.exists(METADATA_FILE)


def load_metadata():

    if not metadata_exists():
        return None

    with open(METADATA_FILE) as f:
        return json.load(f)


def save_metadata(state):

    os.makedirs("vector_store", exist_ok=True)

    with open(METADATA_FILE, "w") as f:

        json.dump(
            {
                "pdf_state": state
            },
            f,
            indent=2,
        )