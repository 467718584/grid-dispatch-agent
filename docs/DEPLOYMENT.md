# Grid Dispatch Agent - 详细部署与测试指南

## 📋 目录

1. [环境要求](#环境要求)
2. [安装步骤](#安装步骤)
3. [配置说明](#配置说明)
4. [启动服务](#启动服务)
5. [功能测试](#功能测试)
6. [Skill单独测试](#skill单独测试)
7. [真实API对接测试](#真实api对接测试)
8. [飞书流式接口测试](#飞书流式接口测试)
9. [故障排查](#故障排查)

---

## 环境要求

| 项目 | 要求 | 说明 |
|------|------|------|
| Python | >= 3.8 | 推荐3.10 |
| Docker | >= 20.10 | 可选，用于容器部署 |
| 网络 | 可访问LLM和电网API | 局域网也可 |

### 依赖包

```
fastapi>=0.100.0
uvicorn>=0.22.0
requests>=2.28.0
pydantic>=2.0.0
```

---

## 安装步骤

### 方式A: Docker部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 2. 构建镜像
docker build -t grid-dispatch-agent:latest .

# 3. 配置环境
cp .env.example .env
# 编辑.env填入配置（见配置说明章节）

# 4. 启动服务
docker-compose up -d

# 5. 验证
docker-compose ps
```

### 方式B: pip安装

```bash
# 1. 克隆项目
git clone https://github.com/467718584/grid-dispatch-agent.git
cd grid-dispatch-agent

# 2. 安装依赖
pip install fastapi uvicorn requests pydantic

# 3. 验证Python包
python3 -c "import fastapi, uvicorn, requests, pydantic; print('依赖安装成功')"
```

### 方式C: 离线部署

```bash
# 1. 在有外网的环境下载
pip download fastapi uvicorn requests pydantic -d ./packages

# 2. 拷贝到内网服务器
scp -r ./packages user@192.168.1.100:/tmp/

# 3. 在内网服务器安装
cd /tmp/packages
pip install *.whl
```

---

## 配置说明

### .env 配置文件

创建 `.env` 文件：

```bash
cat > .env << 'EOF'
# ============== LLM 配置 ==============
# 大模型API地址（必需）
LLM_URL=http://192.168.1.100:8000/v1

# LLM API密钥（如果需要）
LLM_API_KEY=sk-your-key-here

# ============== 电网调度API配置 ==============
# 真实电网调度系统API地址（用于真实API对接）
GRID_API_BASE=http://192.168.1.200:8080/api

# API用户名
GRID_API_USER=66605384.475033835

# ============== Agent配置 ==============
# Agent服务端口
AGENT_PORT=8000
EOF
```

### 配置检查清单

- [ ] `LLM_URL` 是否可访问？
- [ ] `GRID_API_BASE` 是否可访问？（仅真实API对接时需要）
- [ ] `LLM_API_KEY` 是否正确？（如果LLM需要认证）

---

## 启动服务

### Docker启动

```bash
# 启动（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 直接运行

```bash
# 前台运行
python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000

# 后台运行
nohup python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 > agent.log 2>&1 &

# 验证运行
ps aux | grep uvicorn
```

### 服务验证

```bash
# 检查进程
curl http://localhost:8000/health
```

预期响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "skills_registered": ["data_fetch", "calc_reserve", "expert_infer", "output_json"]
}
```

---

## 功能测试

### 测试1: 健康检查

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**预期**: 返回 `healthy` 状态

---

### 测试2: 获取Agent信息

```bash
curl -s http://localhost:8000/agent/info | python3 -m json.tool
```

**预期**: 显示Agent配置、已注册Skills、当前Flow

---

### 测试3: 列出所有Skills

```bash
curl -s http://localhost:8000/skills | python3 -m json.tool
```

**预期**: 列出4个内置Skill
- `data_fetch` - 数据获取
- `calc_reserve` - 备用计算
- `expert_infer` - 专家推断
- `output_json` - JSON输出

---

### 测试4: 执行完整业务流程（模拟数据）

```bash
curl -s -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "执行电网调度综合分析"}' | python3 -m json.tool
```

**预期输出**:
```json
{
  "task_id": "xxxxxxxx",
  "status": "success",
  "data": {
    "status": "success",
    "task": "执行电网调度综合分析",
    "timestamp": "2026-05-08T14:58:00",
    "data": {
      "total_load_mw": 361,
      "reserve_calculation": {...},
      "expert_suggestions": [...],
      "alert_level": "normal"
    },
    "summary": {
      "status": "normal",
      "priority": "P2",
      "action_required": "常规关注"
    }
  }
}
```

---

## Skill单独测试

### DataFetchSkill（数据获取）

```python
# test_data_fetch.py
import asyncio
from grid_agent.skills import DataFetchSkill

async def test():
    skill = DataFetchSkill()
    result = await skill.execute({}, {})
    print("=== DataFetchSkill 测试 ===")
    print(f"数据条目: {len(result.get('data', []))}")
    print(f"总负荷: {result.get('total_load')} MW")
    print(f"数据: {result.get('data')}")

asyncio.run(test())
```

```bash
python3 test_data_fetch.py
```

**预期输出**:
```
=== DataFetchSkill 测试 ===
数据条目: 3
总负荷: 361 MW
数据: [{'station': 'A站', ...}, {'station': 'B站', ...}, {'station': 'C站', ...}]
```

---

### CalcReserveSkill（备用计算）

```python
# test_calc_reserve.py
import asyncio
from grid_agent.skills import CalcReserveSkill

async def test():
    skill = CalcReserveSkill()
    # 模拟输入：总负荷361MW
    result = await skill.execute(
        {"total_load": 361},
        {"data_fetch": {"total_load": 361}}
    )
    print("=== CalcReserveSkill 测试 ===")
    print(f"旋转备用: {result.get('spinning_reserve_mw')} MW")
    print(f"事故备用: {result.get('emergency_reserve_mw')} MW")
    print(f"非旋转备用: {result.get('non_spinning_reserve_mw')} MW")
    print(f"备用状态: {result.get('reserve_status')}")

asyncio.run(test())
```

```bash
python3 test_calc_reserve.py
```

**预期输出**:
```
=== CalcReserveSkill 测试 ===
旋转备用: 54.15 MW
事故备用: 36.1 MW
非旋转备用: 90.25 MW
备用状态: adequate
```

---

### ExpertInferSkill（专家推断）

```python
# test_expert_infer.py
import asyncio
from grid_agent.skills import ExpertInferSkill

async def test():
    skill = ExpertInferSkill()
    result = await skill.execute(
        {"alert_level": "normal"},
        {
            "calc_reserve": {
                "reserve_status": "adequate",
                "total_load": 361
            }
        }
    )
    print("=== ExpertInferSkill 测试 ===")
    print(f"预警级别: {result.get('alert_level')}")
    print(f"优先级: {result.get('priority')}")
    print(f"建议: {result.get('suggestions')}")
    print(f"预警: {result.get('warnings')}")

asyncio.run(test())
```

```bash
python3 test_expert_infer.py
```

**预期输出**:
```
=== ExpertInferSkill 测试 ===
预警级别: normal
优先级: P2
建议: ['常规关注', '继续保持监控']
预警: []
```

---

### OutputJsonSkill（JSON输出）

```python
# test_output_json.py
import asyncio
from grid_agent.skills import OutputJsonSkill

async def test():
    skill = OutputJsonSkill()
    context = {
        "task": "电网调度分析",
        "results": {
            "data_fetch": {
                "data": [{"station": "A站", "load_mw": 100}],
                "total_load": 361
            },
            "calc_reserve": {
                "spinning_reserve_mw": 54.15,
                "reserve_status": "adequate"
            },
            "expert_infer": {
                "alert_level": "normal",
                "suggestions": ["常规关注"]
            }
        }
    }
    result = await skill.execute({"format": "standard"}, context)
    print("=== OutputJsonSkill 测试 ===")
    print(f"状态: {result.get('status')}")
    print(f"摘要: {result.get('summary')}")

asyncio.run(test())
```

```bash
python3 test_output_json.py
```

**预期输出**:
```
=== OutputJsonSkill 测试 ===
状态: success
摘要: {'status': 'normal', 'priority': 'P2', 'action_required': '常规关注', ...}
```

---

## 真实API对接测试

### 前提条件

1. 确认 `GRID_API_BASE` 地址可访问
2. 确认用户名 `GRID_API_USER` 有效

### 联通性测试

```bash
# 测试API服务器连通性
curl -v http://192.168.1.200:8080/api/common_getTableData \
  -H "Content-Type: application/json" \
  -d '{"userName": "66605384.475033835", "tableName": "plan_table"}'
```

**预期**: TCP连接成功（即使API返回错误，至少网络通）

---

### GridDispatchAPISkill（API网关）

```python
# test_grid_api.py
import asyncio
from grid_agent.skills.integration import GridDispatchAPISkill

async def test():
    skill = GridDispatchAPISkill(
        api_base_url="http://192.168.1.200:8080/api",
        api_user="66605384.475033835"
    )
    
    # 测试1: 获取计划数据
    print("=== 测试 common_getPlan ===")
    result = await skill.execute(
        {"action": "get_plan", "plan_date": "2026-05-08"},
        {}
    )
    print(f"结果: {result}")
    
    # 测试2: 获取表格数据
    print("\n=== 测试 common_getTableData ===")
    result = await skill.execute(
        {"action": "get_table", "table_name": "plan_table"},
        {}
    )
    print(f"结果: {result}")

asyncio.run(test())
```

---

### 完整真实API流程测试

```python
# test_real_flow.py
import asyncio
from grid_agent import GridAgent
from grid_agent.skills.integration import (
    DataFetchRealSkill,
    CalcDispatchRealSkill,
    PublishSchemeRealSkill
)

async def test():
    agent = GridAgent(llm_url="http://192.168.1.100:8000/v1")
    
    # 注册真实API Skills
    api_base = "http://192.168.1.200:8080/api"
    agent.register_skill(DataFetchRealSkill(api_base=api_base))
    agent.register_skill(CalcDispatchRealSkill(api_base=api_base))
    agent.register_skill(PublishSchemeRealSkill(api_base=api_base))
    
    # 设置流程
    agent.set_flow([
        "data_fetch_real",
        "calc_dispatch_real",
        "publish_scheme_real"
    ])
    
    # 执行
    result = await agent.execute("执行调度计算")
    print(f"执行状态: {result.get('status')}")
    print(f"结果: {result}")

asyncio.run(test())
```

---

## 飞书流式接口测试

### 测试流式输出

```bash
# 启动流式测试
curl -X POST http://localhost:8000/execute/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "电网调度分析", "chat_id": null}' \
  --no-buffer

# 或用curl -N
curl -N -X POST http://localhost:8000/execute/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "电网调度分析"}'
```

**预期SSE响应格式**:
```
data:{"chatId":2088,"conversationId":"xxx","messageId":"xxx","type":"text","content":"🔄 正在分析...","complete":false,"finish":false,"status":1,"role":{...}}

data:{"chatId":2088,"conversationId":"xxx","messageId":"xxx","type":"table","content":"{\"columns\":{...},\"rows\":[...]}", "complete":true,"finish":false,"status":1,"role":{...}}

data:{"chatId":2088,"conversationId":"xxx","messageId":"xxx","type":"finish","content":"","complete":true,"finish":true,"status":1,"role":{...}}
```

---

### Python流式客户端测试

```python
# test_stream_client.py
import requests
import json

def test_stream():
    url = "http://localhost:8000/execute/stream"
    data = {
        "task": "电网调度分析",
        "chat_id": None
    }
    
    response = requests.post(url, json=data, stream=True)
    
    print("=== 流式响应测试 ===")
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data:'):
                json_str = line[5:].strip()
                try:
                    msg = json.loads(json_str)
                    print(f"[{msg.get('type')}] {msg.get('content', '')[:50]}...")
                    if msg.get('finish'):
                        break
                except:
                    pass

test_stream()
```

```bash
python3 test_stream_client.py
```

---

## 故障排查

### 问题1: 服务无法启动

```bash
# 检查端口占用
netstat -tlnp | grep 8000

# 检查Python进程
ps aux | grep python

# 查看日志
docker-compose logs grid-agent
# 或
tail -f agent.log
```

**解决方案**: 端口被占用则修改 `AGENT_PORT` 或 kill 占用进程

---

### 问题2: 健康检查失败

```bash
curl -v http://localhost:8000/health
```

**可能原因**:
- Agent未初始化 → 等待几秒再试
- 依赖包缺失 → `pip install fastapi uvicorn requests pydantic`

---

### 问题3: Skills为空

**可能原因**: 初始化失败

**解决方案**:
```python
# 手动初始化
import asyncio
from api.server import AgentManager

asyncio.run(AgentManager.initialize(
    llm_url="http://192.168.1.100:8000/v1"
))
```

---

### 问题4: LLM连接失败

```bash
# 测试LLM连通性
curl -X POST "http://192.168.1.100:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}]}'
```

**错误类型**:
- `Connection refused` → LLM服务未启动或地址错误
- `401 Unauthorized` → API Key错误
- `timeout` → 网络不通

---

### 问题5: 电网API连接失败

```bash
# 测试API连通性
curl -v http://192.168.1.200:8080/api/common_getTableData \
  -H "Content-Type: application/json" \
  -d '{"userName": "66605384.475033835", "tableName": "plan_table"}'
```

**错误类型**:
- `Connection refused` → 电网API服务未启动
- `400 Bad Request` → 请求参数错误（需检查tableName等）
- `401 Unauthorized` → 用户名无效

---

### 问题6: 内存占用高

```bash
# 检查内存
docker stats

# 或
ps aux | grep python
```

**优化建议**:
- 减少并发请求
- 增加LLM服务的超时配置
- 使用Docker资源限制

---

## 测试检查清单

完成所有测试后，确认以下项目全部通过：

- [ ] `GET /health` 返回 `healthy`
- [ ] `GET /skills` 返回4个Skill
- [ ] `POST /execute` 成功返回结果
- [ ] DataFetchSkill 返回3条模拟数据
- [ ] CalcReserveSkill 正确计算备用容量
- [ ] ExpertInferSkill 正确推断预警级别
- [ ] OutputJsonSkill 正确格式化JSON
- [ ] 流式接口 `/execute/stream` 正常输出SSE
- [ ] 真实API对接（如已配置）正常工作

---

## 联系支持

如遇问题，请检查：
1. GitHub Issues: https://github.com/467718584/grid-dispatch-agent/issues
2. 查看完整日志
3. 确认网络连通性
