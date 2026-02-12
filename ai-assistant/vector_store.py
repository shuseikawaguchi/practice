"""
Vector Store Module - 知識ベース・検索エンジン
Purpose: インジェストされたテキストを埋め込みベクトル化して保存、高速検索を提供
        - テキスト埋め込み（sentence-transformers）
        - ベクター登録（FAISS/TF-IDF）
        - セマンティック検索
        - メタデータ管理
        - インデックス永続化
Usage: vs = VectorStore(); vs.add(...); vs.query(...)
Status: ワーカー・訓練機で継続更新
"""
import os
import json
import pickle
import logging
from pathlib import Path

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

try:
    import faiss
    _has_faiss = True
except Exception:
    faiss = None
    _has_faiss = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors
except Exception:
    TfidfVectorizer = None
    NearestNeighbors = None

from config import Config

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, model_name: str = None):
        model_name = model_name or Config.EMBEDDING_MODEL
        self.index_path = Config.MODELS_DIR / 'vector_index.pkl'
        self.emb_path = Config.MODELS_DIR / 'embeddings.npy'
        self.meta_path = Config.MODELS_DIR / 'metadatas.pkl'
        Config.MODELS_DIR.mkdir(exist_ok=True)

        self.use_sentence_transformer = SentenceTransformer is not None
        if self.use_sentence_transformer:
            try:
                self.encoder = SentenceTransformer(model_name)
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer: {e}")
                self.encoder = None
                self.use_sentence_transformer = False
        else:
            self.encoder = None

        self.texts = []
        self.metadatas = []
        self.embeddings = None
        self.faiss_index = None
        self.tfidf = None
        self.nn = None

    def add(self, doc_id: str, text: str, metadata: dict = None):
        self.texts.append(text)
        self.metadatas.append({'id': doc_id, 'meta': metadata or {}})

    def build(self):
        if self.use_sentence_transformer and self.encoder is not None:
            logger.info('Building embeddings with sentence-transformers')
            self.embeddings = self.encoder.encode(self.texts, show_progress_bar=False)
            self.embeddings = np.array(self.embeddings).astype('float32')
            # try FAISS
            if _has_faiss:
                d = self.embeddings.shape[1]
                index = faiss.IndexFlatL2(d)
                index.add(self.embeddings)
                self.faiss_index = index
            else:
                # fallback to sklearn NN
                if NearestNeighbors is None:
                    raise RuntimeError('No NearestNeighbors available')
                self.nn = NearestNeighbors(n_neighbors=5, metric='cosine')
                self.nn.fit(self.embeddings)
        else:
            logger.info('Falling back to TF-IDF vectorizer')
            if TfidfVectorizer is None:
                raise RuntimeError('scikit-learn is required for TF-IDF fallback')
            self.tfidf = TfidfVectorizer(max_features=20000)
            X = self.tfidf.fit_transform(self.texts)
            self.embeddings = X
            self.nn = NearestNeighbors(n_neighbors=5, metric='cosine')
            self.nn.fit(X)

        # persist
        with open(self.meta_path, 'wb') as mf:
            pickle.dump(self.metadatas, mf)
        if isinstance(self.embeddings, np.ndarray):
            np.save(self.emb_path, self.embeddings)
        with open(self.index_path, 'wb') as f:
            pickle.dump({'has_faiss': _has_faiss and self.faiss_index is not None, 'use_st': self.use_sentence_transformer}, f)
        logger.info('Vector store build complete')

    def query(self, text: str, k: int = 5):
        if self.use_sentence_transformer and self.encoder is not None:
            q = self.encoder.encode([text]).astype('float32')
            if self.faiss_index is not None:
                D, I = self.faiss_index.search(q, k)
                indices = I[0].tolist()
            else:
                D, I = self.nn.kneighbors(q, n_neighbors=k)
                indices = I[0].tolist()
        else:
            if self.tfidf is None:
                raise RuntimeError('No index built')
            q = self.tfidf.transform([text])
            D, I = self.nn.kneighbors(q, n_neighbors=k)
            indices = I[0].tolist()

        results = []
        for idx in indices:
            meta = self.metadatas[idx]
            results.append({'id': meta['id'], 'meta': meta['meta'], 'text': self.texts[idx]})
        return results

    def save(self, path: Path = None):
        path = path or Config.MODELS_DIR
        with open(path / 'metadatas.pkl', 'wb') as mf:
            pickle.dump(self.metadatas, mf)
        if isinstance(self.embeddings, np.ndarray):
            np.save(path / 'embeddings.npy', self.embeddings)
        logger.info('Vector store saved')

    def load(self, path: Path = None):
        path = path or Config.MODELS_DIR
        with open(path / 'metadatas.pkl', 'rb') as mf:
            self.metadatas = pickle.load(mf)
        if (path / 'embeddings.npy').exists():
            self.embeddings = np.load(path / 'embeddings.npy')
        logger.info('Vector store loaded')
