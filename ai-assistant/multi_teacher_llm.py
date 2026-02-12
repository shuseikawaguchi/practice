"""
Multi-Teacher LLM Module - マルチ教師学習システム
Purpose: 複数の LLM モデルから並行学習し、タスク別に最適なモデルを選択
        - 4つの専門教師モデル
        - タスク別重み付け（コード、ゲーム、分析、説明）
        - アンサンブル投票
        - 応答の統合・改善
        - 学習ログ記録
Usage: mtllm = MultiTeacherLLM(); mtllm.query(prompt, task='code')
Status: Perfect AI Phase 1 で導入、継続拡張中
"""

import asyncio
import logging
import json
from typing import Dict, List, Tuple, Any
from datetime import datetime
from pathlib import Path

from config import Config
from llm_manager import LLMManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class TeacherConfig:
    """Configuration for teacher models"""
    
    TEACHERS = {
        'llama2': {
            'base_url': 'http://localhost:11434',
            'model': 'llama2',
            'specialties': ['general', 'japanese', 'reasoning'],
            'weight': 0.4,
        },
        'mistral': {
            'base_url': 'http://localhost:11435',
            'model': 'mistral',
            'specialties': ['logic', 'math', 'analysis'],
            'weight': 0.2,
        },
        'neural-chat': {
            'base_url': 'http://localhost:11436',
            'model': 'neural-chat',
            'specialties': ['conversation', 'explanation', 'clarity'],
            'weight': 0.2,
        },
        'codegemma': {
            'base_url': 'http://localhost:11437',
            'model': 'codegemma',
            'specialties': ['programming', 'code-review', 'debugging'],
            'weight': 0.2,
        },
    }
    
    TASK_WEIGHTS = {
        'general': {'llama2': 0.4, 'mistral': 0.2, 'neural-chat': 0.2, 'codegemma': 0.2},
        'code': {'codegemma': 0.4, 'llama2': 0.3, 'mistral': 0.2, 'neural-chat': 0.1},
        'game_dev': {'codegemma': 0.4, 'mistral': 0.3, 'llama2': 0.2, 'neural-chat': 0.1},
        'analysis': {'mistral': 0.4, 'llama2': 0.3, 'neural-chat': 0.2, 'codegemma': 0.1},
        'explanation': {'neural-chat': 0.4, 'llama2': 0.3, 'mistral': 0.2, 'codegemma': 0.1},
    }

class MultiTeacherLLM:
    """
    Multi-teacher learning system
    Queries multiple models in parallel and intelligently combines responses
    """
    
    def __init__(self):
        self.teachers: Dict[str, LLMManager] = {}
        self.config = TeacherConfig()
        self.response_cache = {}
        self.ensemble_log = Config.DATA_DIR / 'ensemble_log.jsonl'
        self.ensemble_log.parent.mkdir(exist_ok=True)
        
        # Initialize teachers
        self._init_teachers()
    
    def _init_teachers(self):
        """Initialize connections to all teacher models"""
        for name, config in self.config.TEACHERS.items():
            try:
                # Create LLMManager for each teacher
                teacher = LLMManager(model_name=config['model'])
                teacher.base_url = config['base_url']
                self.teachers[name] = teacher
                logger.info(f'✅ Teacher "{name}" initialized')
            except Exception as e:
                logger.warning(f'⚠️  Teacher "{name}" not available: {e}')
    
    async def query_teacher(self, teacher_name: str, prompt: str, **kwargs) -> str:
        """Query a single teacher model"""
        if teacher_name not in self.teachers:
            logger.warning(f'Teacher {teacher_name} not available')
            return ''
        
        teacher = self.teachers[teacher_name]
        try:
            response = teacher.generate(prompt, **kwargs)
            return response
        except Exception as e:
            logger.error(f'Error querying {teacher_name}: {e}')
            return ''
    
    async def query_all_teachers(self, prompt: str, task_type: str = 'general', 
                                 **kwargs) -> Dict[str, str]:
        """Query all available teachers in parallel"""
        available_teachers = list(self.teachers.keys())
        
        # Create tasks for parallel execution
        tasks = [
            self.query_teacher(name, prompt, **kwargs)
            for name in available_teachers
        ]
        
        # Execute in parallel
        responses = await asyncio.gather(*tasks)
        
        # Combine into dict
        result = {
            name: response
            for name, response in zip(available_teachers, responses)
        }
        
        logger.info(f'Received responses from {len([r for r in result.values() if r])} teachers')
        return result
    
    def _calculate_weights(self, task_type: str) -> Dict[str, float]:
        """Get weights for task-specific ensemble"""
        task_weights = self.config.TASK_WEIGHTS.get(task_type)
        if task_weights is None:
            task_weights = self.config.TASK_WEIGHTS['general']
        return task_weights
    
    def score_response(self, response: str, reference: str = None) -> float:
        """Score a response (1.0 = perfect, 0.0 = terrible)"""
        if not response or len(response) < 10:
            return 0.0
        
        # Simple heuristics (can be enhanced)
        score = 0.5  # baseline
        
        # Length bonus
        if len(response) > 100:
            score += 0.2
        elif len(response) > 50:
            score += 0.1
        
        # Coherence (simple check)
        if response.count('.') > 2:
            score += 0.15
        
        if reference and response.lower() in reference.lower():
            score += 0.15
        
        return min(score, 1.0)
    
    def merge_responses(self, responses: Dict[str, str], weights: Dict[str, float],
                       task_type: str = 'general') -> Tuple[str, Dict]:
        """Intelligently merge multiple responses"""
        
        # Score each response
        scores = {
            name: self.score_response(response)
            for name, response in responses.items()
            if response
        }
        
        if not scores:
            return 'No valid response from teachers', {'error': 'All teachers failed'}
        
        # Weight by teacher specialty + response quality
        weighted_scores = {}
        for name, score in scores.items():
            teacher_weight = weights.get(name, 0.1)
            weighted_scores[name] = score * teacher_weight
        
        # Sort by score
        ranked = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)
        logger.info(f'Teacher ranking: {[f"{n}:{s:.2f}" for n, s in ranked[:3]]}')
        
        # Merge strategy: weighted voting
        merged = self._merge_by_voting(responses, weighted_scores)
        
        return merged, {
            'scores': scores,
            'weighted_scores': weighted_scores,
            'ranking': ranked,
        }
    
    def _merge_by_voting(self, responses: Dict[str, str], 
                        weighted_scores: Dict[str, float]) -> str:
        """Merge responses by weighted voting"""
        
        # Get top 2-3 responses
        best_responses = sorted(
            [(name, responses[name]) for name in weighted_scores if responses.get(name)],
            key=lambda x: weighted_scores[x[0]],
            reverse=True
        )[:3]
        
        if not best_responses:
            return ''
        
        # If there's a clear winner (2x better than second), use it
        if len(best_responses) > 1:
            score_diff = weighted_scores.get(best_responses[0][0], 0) - \
                        weighted_scores.get(best_responses[1][0], 0)
            if score_diff > 0.3:
                logger.info(f'Using best teacher: {best_responses[0][0]}')
                return best_responses[0][1]
        
        # Otherwise, combine best responses
        logger.info(f'Combining {len(best_responses)} best responses')
        combined = self._synthesize_responses(best_responses)
        return combined
    
    def _synthesize_responses(self, best_responses: List[Tuple[str, str]]) -> str:
        """Synthesize multiple good responses into one"""
        
        if len(best_responses) == 1:
            return best_responses[0][1]
        
        # Simple synthesis: take introduction from best, details from others
        main_response = best_responses[0][1]
        
        # Extract key points from other responses
        additional_points = []
        for name, response in best_responses[1:]:
            sentences = response.split('.')
            if sentences:
                # Add first substantive sentence
                for s in sentences:
                    if len(s.strip()) > 20:
                        additional_points.append(s.strip())
                        break
        
        # Combine
        if additional_points:
            combined = main_response + ' ' + ' '.join(additional_points[:2])
            return combined
        
        return main_response
    
    async def generate_ensemble(self, prompt: str, task_type: str = 'general',
                               temperature: float = 0.7) -> Tuple[str, Dict]:
        """
        Generate response from ensemble of teachers
        Returns: (merged_response, metadata)
        """
        logger.info(f'Starting ensemble generation for task: {task_type}')
        
        # Get weights for this task
        weights = self._calculate_weights(task_type)
        
        # Query all teachers
        responses = await self.query_all_teachers(
            prompt,
            task_type=task_type,
            temperature=temperature
        )
        
        # Merge responses
        merged, metadata = self.merge_responses(responses, weights, task_type)
        
        # Log
        self._log_ensemble(prompt, responses, merged, metadata, task_type)
        
        return merged, metadata
    
    def _log_ensemble(self, prompt: str, responses: Dict[str, str], 
                     merged: str, metadata: Dict, task_type: str):
        """Log ensemble operation for analysis"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'task_type': task_type,
            'prompt': prompt[:200],  # truncate
            'responses_count': len([r for r in responses.values() if r]),
            'merged_length': len(merged),
            'metadata': metadata,
        }
        
        with open(self.ensemble_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def get_teacher_stats(self) -> Dict[str, Any]:
        """Get statistics about teacher performance"""
        stats = {
            'available_teachers': len(self.teachers),
            'teachers': {
                name: {
                    'specialties': self.config.TEACHERS[name]['specialties'],
                    'weight': self.config.TEACHERS[name]['weight'],
                }
                for name in self.teachers.keys()
            },
        }
        
        # Read ensemble log
        if self.ensemble_log.exists():
            logs = []
            with open(self.ensemble_log, 'r', encoding='utf-8') as f:
                for line in f:
                    logs.append(json.loads(line))
            
            if logs:
                stats['total_ensembles'] = len(logs)
                stats['avg_responses_per_ensemble'] = sum(
                    l['responses_count'] for l in logs
                ) / len(logs)
        
        return stats

async def main():
    """Test multi-teacher system"""
    print('=' * 70)
    print('🎓 Multi-Teacher LLM System')
    print('=' * 70)
    
    multi_teacher = MultiTeacherLLM()
    
    # Show available teachers
    stats = multi_teacher.get_teacher_stats()
    print(f'\n📊 Available teachers: {stats["available_teachers"]}')
    for name, info in stats.get('teachers', {}).items():
        print(f'  - {name}: {info["specialties"]}')
    
    # Test ensemble with different task types
    test_cases = [
        ('Write a simple Python function to check if a number is prime',
         'code'),
        ('Explain how neural networks work',
         'explanation'),
        ('Design a game mechanic for a 2D platformer',
         'game_dev'),
    ]
    
    for prompt, task_type in test_cases:
        print(f'\n📝 Task: {task_type}')
        print(f'   Prompt: {prompt[:50]}...')
        
        merged, metadata = await multi_teacher.generate_ensemble(
            prompt,
            task_type=task_type
        )
        
        print(f'   ✅ Response: {merged[:100]}...')
        print(f'   Ranking: {metadata.get("ranking", [])[:2]}')

if __name__ == '__main__':
    # Note: requires multiple Ollama instances
    # asyncio.run(main())
    print('Multi-Teacher LLM system loaded')
    print('To use: await multi_teacher.generate_ensemble(prompt, task_type="code")')
