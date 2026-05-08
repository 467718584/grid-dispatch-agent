"""
Grid Agent CLI - 命令行接口
"""
import asyncio
import argparse
import json
import sys
from . import GridAgent


def main():
    parser = argparse.ArgumentParser(
        description="Grid Dispatch Agent - 轻量化智能Agent框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化Agent
  grid-agent init
  
  # 执行任务
  grid-agent exec "查询负荷数据"
  
  # 列出已注册Skill
  grid-agent list-skills
  
  # 交互模式
  grid-agent shell
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化Agent配置")
    init_parser.add_argument("--url", default="http://localhost:8000/v1", help="LLM API地址")
    init_parser.add_argument("--api-key", help="API密钥")
    init_parser.add_argument("--model", default="default", help="模型名称")
    
    # exec 命令
    exec_parser = subparsers.add_parser("exec", help="执行任务")
    exec_parser.add_argument("task", help="任务描述")
    exec_parser.add_argument("--flow", help="指定执行流程（逗号分隔）")
    exec_parser.add_argument("--params", help="任务参数（JSON格式）")
    
    # list-skills 命令
    subparsers.add_parser("list-skills", help="列出所有已注册Skill")
    
    # shell 命令
    subparsers.add_parser("shell", help="交互模式")
    
    args = parser.parse_args()
    
    if args.command == "init":
        config = {
            "llm_url": args.url,
            "llm_api_key": args.api_key,
            "model": args.model,
        }
        with open("grid_agent_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("✅ 配置文件已创建: grid_agent_config.json")
    
    elif args.command == "exec":
        asyncio.run(exec_task(args.task, args.flow, args.params))
    
    elif args.command == "list-skills":
        list_skills()
    
    elif args.command == "shell":
        shell()
    
    else:
        parser.print_help()


async def exec_task(task: str, flow: str = None, params: str = None):
    """执行任务"""
    config = load_config()
    agent = GridAgent(
        llm_url=config.get("llm_url", "http://localhost:8000/v1"),
        llm_api_key=config.get("llm_api_key"),
        model=config.get("model", "default")
    )
    
    # 注册基础Skill
    from .skills import DataFetchSkill, CalcReserveSkill, ExpertInferSkill, OutputJsonSkill
    agent.register_skill(DataFetchSkill())
    agent.register_skill(CalcReserveSkill())
    agent.register_skill(ExpertInferSkill())
    agent.register_skill(OutputJsonSkill())
    
    flow_list = flow.split(",") if flow else None
    params_dict = json.loads(params) if params else None
    
    result = await agent.execute(task, params_dict, flow_list)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def list_skills():
    """列出Skill"""
    config = load_config()
    agent = GridAgent(llm_url=config.get("llm_url", "http://localhost:8000/v1"))
    
    from .skills import DataFetchSkill, CalcReserveSkill, ExpertInferSkill, OutputJsonSkill
    agent.register_skill(DataFetchSkill())
    agent.register_skill(CalcReserveSkill())
    agent.register_skill(ExpertInferSkill())
    agent.register_skill(OutputJsonSkill())
    
    skills = agent.list_skills()
    print(f"\n已注册Skill ({len(skills)}个):")
    for skill in skills:
        print(f"  • {skill['name']}: {skill['description']}")


def shell():
    """交互模式"""
    print("🟢 Grid Agent Shell (输入 'exit' 退出)")
    print("="*50)
    
    config = load_config()
    agent = GridAgent(llm_url=config.get("llm_url", "http://localhost:8000/v1"))
    
    from .skills import DataFetchSkill, CalcReserveSkill, ExpertInferSkill, OutputJsonSkill
    agent.register_skill(DataFetchSkill())
    agent.register_skill(CalcReserveSkill())
    agent.register_skill(ExpertInferSkill())
    agent.register_skill(OutputJsonSkill())
    agent.set_flow(["data_fetch", "calc_reserve", "expert_infer", "output_json"])
    
    while True:
        try:
            task = input("\n任务> ").strip()
            if task.lower() in ["exit", "quit", "q"]:
                break
            if not task:
                continue
            
            result = asyncio.run(agent.execute(task))
            print(f"\n结果:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")
    
    print("\n再见!")


def load_config():
    """加载配置"""
    try:
        with open("grid_agent_config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


if __name__ == "__main__":
    main()
