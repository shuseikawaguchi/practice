"""CLI: リポジトリを索引化してRAGに反映"""
from src.utils.repo_indexer import index_repository

if __name__ == "__main__":
    result = index_repository()
    print(result)
