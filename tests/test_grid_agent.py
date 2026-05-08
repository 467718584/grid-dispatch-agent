"""
Grid Agent 测试套件
"""
import pytest
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grid_agent import GridAgent, BaseSkill


# ============ 测试用Skill ============

class MockSkill(BaseSkill):
    """测试用Mock Skill"""
    
    def __init__(self, name: str = "mock"):
        self._name = name
        self.execute_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return f"Mock Skill: {self._name}"
    
    async def execute(self, params, context):
        self.execute_count += 1
        return {
            "skill": self._name,
            "count": self.execute_count,
            "input": params
        }


class MockFailSkill(BaseSkill):
    """测试用失败 Skill"""
    
    @property
    def name(self) -> str:
        return "fail"
    
    @property
    def description(self) -> str:
        return "Always fails"
    
    async def execute(self, params, context):
        raise RuntimeError("Intentional failure")


# ============ 测试用例 ============

class TestGridAgent:
    """GridAgent核心功能测试"""
    
    @pytest.fixture
    def agent(self):
        """创建测试Agent"""
        return GridAgent(llm_url="http://localhost:8000/v1")
    
    def test_agent_creation(self, agent):
        """测试Agent创建"""
        assert agent is not None
        assert agent.id is not None
        assert len(agent.id) == 8
    
    def test_skill_registration(self, agent):
        """测试Skill注册"""
        skill = MockSkill("test_skill")
        agent.register_skill(skill)
        
        assert agent.has_skill("test_skill")
        assert not agent.has_skill("nonexistent")
    
    def test_skill_unregistration(self, agent):
        """测试Skill注销"""
        skill = MockSkill("test_skill")
        agent.register_skill(skill)
        agent.unregister_skill("test_skill")
        
        assert not agent.has_skill("test_skill")
    
    def test_skill_list(self, agent):
        """测试Skill列表"""
        agent.register_skill(MockSkill("skill1"))
        agent.register_skill(MockSkill("skill2"))
        
        skills = agent.list_skills()
        assert len(skills) >= 2
        skill_names = [s["name"] for s in skills]
        assert "skill1" in skill_names
        assert "skill2" in skill_names
    
    def test_flow_setting(self, agent):
        """测试流程设置"""
        flow = ["skill1", "skill2", "skill3"]
        agent.set_flow(flow)
        
        assert agent.flow_engine._default_flow == flow
    
    @pytest.mark.asyncio
    async def test_execute_with_flow(self, agent):
        """测试带流程执行"""
        agent.register_skill(MockSkill("step1"))
        agent.register_skill(MockSkill("step2"))
        agent.set_flow(["step1", "step2"])
        
        result = await agent.execute("测试任务")
        
        assert result["status"] == "success"
        assert "step1" in result["data"]["results"]
        assert "step2" in result["data"]["results"]
    
    @pytest.mark.asyncio
    async def test_execute_with_custom_flow(self, agent):
        """测试自定义流程执行"""
        agent.register_skill(MockSkill("a"))
        agent.register_skill(MockSkill("b"))
        agent.register_skill(MockSkill("c"))
        
        result = await agent.execute(
            "自定义流程测试",
            flow=["a", "c"]  # 跳过b
        )
        
        assert result["status"] == "success"
        assert "a" in result["data"]["results"]
        assert "c" in result["data"]["results"]
        # b不应该被执行
        assert "b" not in result["data"]["results"]
    
    @pytest.mark.asyncio
    async def test_execute_with_params(self, agent):
        """测试带参数执行"""
        agent.register_skill(MockSkill("param_test"))
        agent.set_flow(["param_test"])
        
        result = await agent.execute(
            "参数测试",
            params={"key": "value", "number": 42}
        )
        
        assert result["status"] == "success"
        param_result = result["data"]["results"]["param_test"]
        assert "key" in str(param_result) or "value" in str(param_result)
    
    @pytest.mark.asyncio
    async def test_execute_missing_skill(self, agent):
        """测试Skill缺失时的错误处理"""
        agent.set_flow(["nonexistent_skill"])
        
        result = await agent.execute("测试错误处理")
        
        # 应该返回错误状态而不是抛出异常
        assert result["status"] == "error"
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_execute_empty_flow(self, agent):
        """测试空流程处理"""
        agent.set_flow([])
        
        result = await agent.execute("空流程测试")
        
        assert result["status"] == "error"
    
    def test_agent_info(self, agent):
        """测试Agent信息获取"""
        agent.register_skill(MockSkill("info_test"))
        agent.set_flow(["info_test"])
        
        info = agent.get_info()
        
        assert "id" in info
        assert "skills" in info
        assert "flow" in info
        assert "info_test" in info["skills"]


class TestSkillRegistry:
    """SkillRegistry测试"""
    
    def test_register_and_get(self):
        """测试注册和获取"""
        from grid_agent.skill import SkillRegistry
        
        registry = SkillRegistry()
        skill = MockSkill("reg_test")
        registry.register(skill)
        
        assert registry.get("reg_test") is skill
    
    def test_register_duplicate(self):
        """测试重复注册"""
        from grid_agent.skill import SkillRegistry
        
        registry = SkillRegistry()
        skill = MockSkill("dup_test")
        registry.register(skill)
        
        with pytest.raises(ValueError):
            registry.register(skill)
    
    def test_unregister(self):
        """测试注销"""
        from grid_agent.skill import SkillRegistry
        
        registry = SkillRegistry()
        skill = MockSkill("unreg_test")
        registry.register(skill)
        result = registry.unregister("unreg_test")
        
        assert result is True
        assert registry.get("unreg_test") is None
    
    def test_list_all(self):
        """测试列出所有"""
        from grid_agent.skill import SkillRegistry
        
        registry = SkillRegistry()
        registry.register(MockSkill("list1"))
        registry.register(MockSkill("list2"))
        
        all_skills = registry.list_all()
        assert len(all_skills) == 2
    
    def test_exists(self):
        """测试存在检查"""
        from grid_agent.skill import SkillRegistry
        
        registry = SkillRegistry()
        registry.register(MockSkill("exists_test"))
        
        assert registry.exists("exists_test")
        assert not registry.exists("not_exists")


class TestFlowEngine:
    """FlowEngine测试"""
    
    @pytest.mark.asyncio
    async def test_execute_flow(self):
        """测试流程执行"""
        from grid_agent.skill import SkillRegistry
        from grid_agent.llm import LLMAdapter
        from grid_agent.flow import FlowEngine
        
        registry = SkillRegistry()
        registry.register(MockSkill("flow1"))
        registry.register(MockSkill("flow2"))
        
        llm = LLMAdapter("http://localhost:8000/v1")
        engine = FlowEngine(registry, llm)
        engine.set_default_flow(["flow1", "flow2"])
        
        result = await engine.execute("测试流程")
        
        assert result["success"]
        assert "flow1" in result["results"]
        assert "flow2" in result["results"]


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
