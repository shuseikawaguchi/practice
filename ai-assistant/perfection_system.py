#!/usr/bin/env python3
"""
Perfection System Module - 完璧な AI 統合エンジン
Purpose: マルチ教師、拡張スキル、知識クローラーを統合し、完璧な AI を実現
        - マルチ教師学習の統合
        - スキル進化の統合
        - 知識収集の統合
        - 統一インターフェース
        - システム状態表示
Usage: perf = PerfectionSystem(); perf.generate_with_all_systems(prompt)
       perf.show_system_status(); perf.start_learning_cycle()
Status: Perfect AI Phase 1・2・3・4 統合エンジン
"""

import asyncio
import logging
from pathlib import Path

from config import Config
from multi_teacher_llm import MultiTeacherLLM
from extended_skills import ExtendedSkillManager
from universal_crawler import UniversalCrawler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class PerfectionSystem:
    """Integrated system for AI perfection"""
    
    def __init__(self):
        self.multi_teacher = MultiTeacherLLM()
        self.skill_manager = ExtendedSkillManager()
        self.crawler = UniversalCrawler()
        self.status_file = Config.DATA_DIR / 'perfection_status.json'
    
    def show_system_status(self):
        """Display comprehensive system status"""
        print('\n' + '=' * 80)
        print('🚀 AI PERFECTION SYSTEM STATUS')
        print('=' * 80)
        
        # Teacher stats
        print('\n📚 Multi-Teacher Learning:')
        teacher_stats = self.multi_teacher.get_teacher_stats()
        print(f'  Available Teachers: {teacher_stats["available_teachers"]}')
        for name, info in teacher_stats.get('teachers', {}).items():
            specialties = ', '.join(info['specialties'][:2])
            print(f'    - {name}: {specialties}... (weight: {info["weight"]:.1%})')
        
        # Skill stats
        print('\n📖 Extended Skills:')
        skill_summary = self.skill_manager.get_skills_summary()
        total_skills = sum(s['total'] for s in skill_summary.values())
        print(f'  Total Skills: {total_skills}')
        for category, stats in skill_summary.items():
            print(f'    {category}: {stats["total"]} skills')
        
        # Crawl stats
        print('\n🌐 Knowledge Base:')
        crawl_stats = self.crawler.get_crawl_stats()
        print(f'  Total URLs Crawled: {crawl_stats["total_urls"]}')
        if crawl_stats['by_specialty']:
            for specialty, count in crawl_stats['by_specialty'].items():
                print(f'    {specialty}: {count} URLs')
        
        print('\n' + '=' * 80)
    
    async def start_learning_cycle(self, specialty: str = None, 
                                   intensity: str = 'normal'):
        """Start a learning cycle"""
        
        print('\n' + '=' * 80)
        print(f'🎓 Starting Learning Cycle ({intensity} intensity)')
        print('=' * 80)
        
        # Determine learning parameters
        max_pages = {
            'light': 10,
            'normal': 50,
            'intensive': 200,
        }.get(intensity, 50)
        
        # Knowledge crawling
        if specialty:
            logger.info(f'📚 Learning {specialty}...')
            await self.crawler.crawl_specialty(specialty, max_pages=max_pages)
        else:
            # Learn from all specialties
            specialties = list(self.crawler.KNOWLEDGE_SOURCES.keys())
            for spec in specialties[:3]:  # Start with first 3
                logger.info(f'📚 Learning {spec}...')
                await self.crawler.crawl_specialty(spec, max_pages=max_pages // 3)
                await asyncio.sleep(2)
        
        print('\n✅ Learning cycle complete')
    
    async def generate_with_all_systems(self, prompt: str, task_type: str = 'general'):
        """Generate response using all perfection systems"""
        
        print('\n' + '=' * 80)
        print(f'🎯 Generating Response: {task_type.upper()}')
        print('=' * 80)
        print(f'Prompt: {prompt[:100]}...\n')
        
        # Use multi-teacher ensemble
        logger.info('🎓 Consulting teacher ensemble...')
        response, metadata = await self.multi_teacher.generate_ensemble(
            prompt,
            task_type=task_type
        )
        
        # Update skills
        self.skill_manager.add_skill_experience(
            category='advanced',
            skill_name=task_type,
            success=True,
            points=15
        )
        
        print(f'\n✅ Response Generated:')
        print('-' * 80)
        print(response)
        print('-' * 80)
        print(f'\nMetadata:')
        print(f'  Best Teachers: {metadata.get("ranking", [])[:2]}')
        print(f'  Response Quality: {metadata.get("weighted_scores", {})}')
        
        return response, metadata

async def main():
    """Main entry point"""
    system = PerfectionSystem()
    
    # Show status
    system.show_system_status()
    
    # Start learning cycle
    print('\n🎯 Perfection System Ready!')
    print('\nTo use:')
    print('  1. Learn from specific domain:')
    print('     await system.start_learning_cycle("game_dev", intensity="intensive")')
    print('  2. Generate with ensemble:')
    print('     await system.generate_with_all_systems("prompt", task_type="code")')
    print('  3. Check skills:')
    print('     system.skill_manager.print_skills_report()')
    
    # Example: Light learning + generation
    # await system.start_learning_cycle('game_dev', intensity='light')
    # response, meta = await system.generate_with_all_systems(
    #     'How do I create a simple 2D platformer in Unity?',
    #     task_type='game_dev'
    # )

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--demo':
        asyncio.run(main())
    else:
        print('=' * 80)
        print('🚀 AI Perfection System')
        print('=' * 80)
        print('\nComponents Loaded:')
        print('  ✅ Multi-Teacher LLM (multi_teacher_llm.py)')
        print('  ✅ Extended Skills (extended_skills.py)')
        print('  ✅ Universal Crawler (universal_crawler.py)')
        print('\nUsage:')
        print('  python3 perfection_system.py --demo    # Run demo')
        print('  from perfection_system import PerfectionSystem')
        print('  system = PerfectionSystem()')
        print('  system.show_system_status()')
