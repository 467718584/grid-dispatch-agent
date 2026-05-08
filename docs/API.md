# Grid Agent - API使用指南

## 快速开始

### 1. Docker部署

```bash
# 构建镜像
docker build -t grid-agent:latest .

# 启动服务
docker-compose up -d

# 或直接运行
docker run -p 8000:8000 grid-agent:latest
```

### 2. 本地运行

```bash
pip install -r requirements.txt
python -m uvicorn api.server:app --reload --port 8000
```

## API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API端点

### 健康检查

```bash
GET /health
```

响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "skills_registered": ["data_fetch", "calc_reserve", "expert_infer", "output_json"]
}
```

### 初始化Agent

```bash
POST /init?llm_url=http://localhost:8000/v1
```

### 执行任务

```bash
POST /execute
Content-Type: application/json

{
  "task": "电网调度综合分析",
  "flow": ["data_fetch", "calc_reserve", "expert_infer", "output_json"],
  "params": {}
}
```

响应：
```json
{
  "task_id": "a1b2c3d4",
  "status": "success",
  "data": {
    "load_data": [...],
    "reserve_calculation": {...},
    "alert_level": "normal"
  }
}
```

### 列出Skill

```bash
GET /skills
```

## 前端集成示例

### JavaScript

```javascript
// 执行任务
async function executeTask(task) {
  const response = await fetch('/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task })
  });
  return response.json();
}

// 获取结果并展示
async function displayResult(task) {
  const result = await executeTask(task);
  
  if (result.status === 'success') {
    // 显示数据
    displayData(result.data);
    // 显示预警状态
    displayAlert(result.data.alert_level);
  }
}
```

### Vue 3

```vue
<template>
  <div class="grid-agent">
    <button @click="executeAnalysis">执行分析</button>
    <div v-if="loading">加载中...</div>
    <div v-else-if="result">
      <AlertLevel :level="result.data.alert_level" />
      <LoadChart :data="result.data.load_data" />
      <ReserveTable :data="result.data.reserve_calculation" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const result = ref(null);
const loading = ref(false);

async function executeAnalysis() {
  loading.value = true;
  try {
    const response = await fetch('/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        task: '电网调度综合分析',
        flow: ['data_fetch', 'calc_reserve', 'expert_infer', 'output_json']
      })
    });
    result.value = await response.json();
  } finally {
    loading.value = false;
  }
}
</script>
```

### React

```jsx
function GridAgentDashboard() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const executeAnalysis = async () => {
    setLoading(true);
    try {
      const response = await fetch('/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          task: '电网调度综合分析'
        })
      });
      const data = await response.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={executeAnalysis}>执行分析</button>
      {loading && <div>加载中...</div>}
      {result?.status === 'success' && (
        <>
          <AlertLevel level={result.data.alert_level} />
          <LoadChart data={result.data.load_data} />
        </>
      )}
    </div>
  );
}
```

## 返回数据格式

```json
{
  "task_id": "string",
  "status": "success | error | warning",
  "data": {
    "load_data": [
      {"station": "A站", "load_mw": 120, "timestamp": "..."}
    ],
    "reserve_calculation": {
      "total_load_mw": 361,
      "spinning_reserve_mw": 28.88,
      "non_spinning_reserve_mw": 25.27,
      "emergency_reserve_mw": 36.1,
      "total_reserve_mw": 90.25,
      "reserve_status": "adequate | warning | critical"
    },
    "expert_suggestions": ["建议1", "建议2"],
    "warnings": ["警告1"],
    "alert_level": "normal | warning | critical"
  },
  "message": null
}
```
