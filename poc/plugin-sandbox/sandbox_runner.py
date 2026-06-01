"""
Plugin Sandbox Runner - 启动 ephemeral Docker container 执行插件脚本
"""

import subprocess
from dataclasses import dataclass


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    oom_killed: bool


def run_plugin_script(
    plugin_dir: str,
    script_name: str,
    allowed_domains: list[str] | None = None,
    timeout: int = 30,
    cpu_limit: float = 0.5,
    memory_limit: str = "512m"
) -> SandboxResult:
    """
    在隔离的 Docker 容器中运行插件脚本
    
    Args:
        plugin_dir: 插件目录路径
        script_name: 要执行的脚本名称
        allowed_domains: 允许访问的域名列表（如果提供则启用网络）
        timeout: 执行超时时间（秒）
        cpu_limit: CPU 限制（核数）
        memory_limit: 内存限制（如 "512m"）
    
    Returns:
        SandboxResult 包含执行结果
    """
    # 生成唯一的容器名称以便追踪
    import uuid
    container_name = f"plugin-sandbox-{uuid.uuid4().hex[:8]}"
    
    # 构建 docker run 命令
    cmd = [
        "docker", "run",
        "--name", container_name,
        "--rm",
        "--read-only",
        "--tmpfs", "/tmp:size=64m",
        "-v", f"{plugin_dir}:/plugin:ro",
        "--cpus", str(cpu_limit),
        "--memory", memory_limit,
        "--security-opt", "no-new-privileges",
        "--user", "sandbox"
    ]
    
    # 网络配置
    if allowed_domains:
        # POC 阶段：简化实现为启用默认网络
        # 生产环境应实现：创建自定义网络 + DNS 黑名单/白名单过滤
        # 可使用 Docker 的 --dns 选项配合本地 DNS 服务器实现域名过滤
        cmd.extend(["--network", "bridge"])
    else:
        cmd.extend(["--network", "none"])
    
    # 添加镜像和入口点
    cmd.extend([
        "agentcook-plugin-sandbox",
        f"/plugin/scripts/{script_name}"
    ])
    
    try:
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        timed_out = False
        oom_killed = _check_oom_status(container_name)
        
    except subprocess.TimeoutExpired:
        # 超时，强制停止并清理容器
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            timeout=5
        )
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            timeout=5
        )
        
        stdout = ""
        stderr = f"Execution timed out after {timeout} seconds"
        exit_code = -1
        timed_out = True
        oom_killed = False
    
    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        oom_killed=oom_killed
    )


def _check_oom_status() -> bool:
    """
    检查最近运行的容器是否因 OOM 被杀掉
    
    Returns:
        True 如果最后一个容器因 OOM 被杀掉
    """
    try:
        # 获取最近退出的容器状态
        result = subprocess.run(
            ["docker", "ps", "-a", "--latest", "--format", "{{.ID}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return False
        
        container_id = result.stdout.strip()
        
        # 检查 OOMKilled 状态
        inspect_result = subprocess.run(
            ["docker", "inspect", container_id, "--format", "{{.State.OOMKilled}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if inspect_result.returncode == 0:
            return inspect_result.stdout.strip().lower() == "true"
        
        return False
    
    except Exception:
        return False


if __name__ == "__main__":
    # 示例用法
    import sys
    if len(sys.argv) >= 3:
        plugin_dir = sys.argv[1]
        script_name = sys.argv[2]
        result = run_plugin_script(plugin_dir, script_name)
        print(f"Exit code: {result.exit_code}")
        print(f"Timed out: {result.timed_out}")
        print(f"OOM killed: {result.oom_killed}")
        print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
