"""
Skills Manager - Manages AI capabilities and tools
"""
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class Skill:
    name: str
    description: str
    capability: str
    is_learned: bool = False
    accuracy: float = 0.0
    usage_count: int = 0

class SkillManager:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.memory_file = Config.MEMORY_FILE
        self._initialize_default_skills()
        self._load_memory()
    
    def _initialize_default_skills(self):
        """Initialize default skills"""
        default_skills = [
            Skill(
                name="code_generation",
                description="Python/JavaScriptなどのプログラムコードを生成",
                capability="program_generation",
                is_learned=False,
                accuracy=0.0
            ),
            Skill(
                name="ui_generation",
                description="HTMLとCSSでUIを作成",
                capability="ui_design",
                is_learned=False,
                accuracy=0.0
            ),
            Skill(
                name="model_3d_generation",
                description="Three.jsで3Dモデルを作成",
                capability="3d_modeling",
                is_learned=False,
                accuracy=0.0
            ),
            Skill(
                name="japanese_understanding",
                description="日本語のニュアンスを理解する",
                capability="nlp_ja",
                is_learned=False,
                accuracy=0.0
            ),
            Skill(
                name="text_generation",
                description="自然な文章を生成",
                capability="text_generation",
                is_learned=False,
                accuracy=0.0
            )
        ]
        
        for skill in default_skills:
            self.skills[skill.name] = skill
    
    def learn_skill(self, skill_name: str, accuracy: float) -> bool:
        """
        Mark a skill as learned with accuracy score
        """
        if skill_name not in self.skills:
            logger.warning(f"Skill '{skill_name}' not found")
            return False
        
        skill = self.skills[skill_name]
        skill.is_learned = True
        skill.accuracy = min(accuracy, 1.0)  # Cap at 1.0
        skill.usage_count += 1
        
        self._save_memory()
        logger.info(f"Skill '{skill_name}' learned with accuracy {accuracy:.2f}")
        return True
    
    def improve_skill(self, skill_name: str, improvement: float) -> bool:
        """
        Improve skill accuracy through learning
        """
        if skill_name not in self.skills:
            return False
        
        skill = self.skills[skill_name]
        new_accuracy = min(skill.accuracy + improvement, 1.0)
        skill.accuracy = new_accuracy
        skill.usage_count += 1
        
        self._save_memory()
        logger.info(f"Skill '{skill_name}' improved to accuracy {new_accuracy:.2f}")
        return True
    
    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get skill by name"""
        return self.skills.get(skill_name)
    
    def get_all_skills(self) -> Dict[str, Skill]:
        """Get all skills"""
        return self.skills
    
    def get_learned_skills(self) -> List[Skill]:
        """Get all learned skills"""
        return [skill for skill in self.skills.values() if skill.is_learned]
    
    def _save_memory(self):
        """Save skill memory to file"""
        try:
            memory = {
                "conversations": [],  # Will be updated by learning system
                "learned_skills": [asdict(skill) for skill in self.get_learned_skills()]
            }
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def _load_memory(self):
        """Load skill memory from file"""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    memory = json.load(f)
                    
                    # Update skills with learned status
                    for skill_data in memory.get("learned_skills", []):
                        skill_name = skill_data.get("name")
                        if skill_name in self.skills:
                            skill = self.skills[skill_name]
                            skill.is_learned = skill_data.get("is_learned", False)
                            skill.accuracy = skill_data.get("accuracy", 0.0)
                            skill.usage_count = skill_data.get("usage_count", 0)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
    
    def get_status(self) -> Dict:
        """Get current skill status"""
        total_skills = len(self.skills)
        learned_skills = len(self.get_learned_skills())
        avg_accuracy = sum(s.accuracy for s in self.skills.values()) / total_skills if total_skills > 0 else 0
        
        return {
            "total_skills": total_skills,
            "learned_skills": learned_skills,
            "average_accuracy": avg_accuracy,
            "skills": {name: asdict(skill) for name, skill in self.skills.items()}
        }
