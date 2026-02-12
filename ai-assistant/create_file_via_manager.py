"""
Example script: create a file using FileManager to demonstrate automatic placement.
"""
from config import Config
from src.utils.file_manager import write_component_file

if __name__ == '__main__':
    sample = {
        "title": "example proposal",
        "status": "PROPOSED",
        "description": "This is a test proposal created via FileManager."
    }
    p = write_component_file('patches', 'example_proposal.json', sample)
    print('Created:', p)
