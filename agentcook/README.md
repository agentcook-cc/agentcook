# agentcook

FastAPI 主应用。编排 core + providers + storage 三包。API 入口 + Auth + DB schema。

## 安装

```bash
pip install agentcook
```

## 快速开始

```python
from agentcook import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```
