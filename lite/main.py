#!/usr/bin/env python3
"""
帝国架构 v2.9.6 - CLI
Empire Architecture v2.9.6

用法:
  python3 main.py              # 交互模式
  python3 main.py "指令"        # 单次执行
  python3 main.py --status     # 查看状态
  python3 main.py --agents     # 查看节点
  python3 main.py --tokens     # 查看 token
  python3 main.py --knowledge  # 查看知识层
  python3 main.py --queue      # 查看队列
  python3 main.py --memory     # 查看记忆
"""
import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from chancellor import Chancellor
from core.logger import get_logger

log = get_logger("cli")


class EmpireCLI:
    """帝国控制台 v2.9.6"""

    def __init__(self):
        self.chancellor = Chancellor()
        self.running = True

    def print_banner(self):
        print("""
╔══════════════════════════════════════════════════════╗
║          Empire Architecture 2.9.6                   ║
║──────────────────────────────────────────────────────║
║  皇帝: AARONCXXX         丞相: Mimo                  ║
║  节点: 256               知识层: 已挂载              ║
║  新增: 标签路由 | 模型分级 | 任务队列 | 熔断器       ║
║        Agent记忆 | 事前审批 | 中文分词 | 热加载      ║
╚══════════════════════════════════════════════════════╝
        """)

    def print_help(self):
        print("""
命令:
  <指令>        向帝国下达指令
  status        查看帝国状态
  agents        查看所有节点状态
  tokens        查看 token 使用情况
  knowledge     查看知识层状态
  queue         查看任务队列
  memory <id>   查看 Agent 记忆
  bus           查看消息总线统计
  history       查看消息历史
  help          显示帮助
  exit / quit   退出
        """)

    async def execute_command(self, command: str):
        """执行皇帝指令"""
        print(f"\n⚡ 丞相接令，开始编排...")
        print(f"{'─' * 50}")

        try:
            result = await self.chancellor.receive_command(command)

            print(f"\n📋 任务 {result['task_id']} 完成 ({result['elapsed_seconds']}s)")
            print(f"{'─' * 50}")

            for agent_id, content in result["results"].items():
                if agent_id == "chancellor_summary":
                    continue
                agent = self.chancellor.agents.get(agent_id)
                name = agent.state.name if agent else agent_id
                display = content[:500] + "..." if len(content) > 500 else content
                print(f"\n🔸 {name}:")
                print(f"  {display}")

            print(f"\n{'═' * 50}")
            print(f"📊 丞相汇总:")
            print(result["results"].get("chancellor_summary", "无汇总"))

            audit = result.get("audit", {})
            safe_icon = "✅" if audit.get("safe", True) else "⚠️"
            print(f"\n{safe_icon} 锦衣卫审计: {'通过' if audit.get('safe', True) else '发现问题'}")
            if audit.get("issues"):
                for issue in audit["issues"]:
                    print(f"   - {issue}")

            kb_icon = "📚" if result.get("knowledge_used") else "📭"
            print(f"{kb_icon} 知识层: {'已注入' if result.get('knowledge_used') else '无匹配'}")

            if result.get("sensitive"):
                print(f"⚠️  敏感任务: 已记录")

            print(f"\n⏱  耗时: {result['elapsed_seconds']}s | Token 今日: {result['tokens_used']}")

        except Exception as e:
            print(f"\n❌ 执行失败: {e}")
            log.error(f"执行失败: {e}", exc_info=True)

    def show_status(self):
        status = self.chancellor.get_status()
        print(f"\n{'═' * 50}")
        print(f"帝国状态 v2.9.6")
        print(f"{'─' * 50}")
        print(f"节点数: {len(status['agents'])}")
        print(f"消息总数: {status['message_history']}")
        print(f"安全事件: {status['security']['total_violations']}")
        print(f"任务队列: 提交={status['task_queue']['submitted']} 完成={status['task_queue']['completed']} 失败={status['task_queue']['failed']}")
        print(f"消息总线: 发送={status['bus_stats']['sent']} 接收={status['bus_stats']['received']}")
        if "knowledge_sources" in status:
            print(f"知识源: {', '.join(status['knowledge_sources']) or '无'}")
        if status.get("model_stats"):
            print(f"模型使用:")
            for model, stats in status["model_stats"].items():
                print(f"  {model}: {stats['calls']}次 输入={stats['input']} 输出={stats['output']}")

    def show_agents(self):
        status = self.chancellor.get_status()
        print(f"\n{'═' * 50}")
        print(f"节点状态 (共{len(status['agents'])}个)")
        print(f"{'─' * 50}")
        for aid, info in status["agents"].items():
            icon = {"idle": "🟢", "busy": "🟡", "error": "🔴"}.get(info["status"], "⚪")
            tags = ",".join(info.get("tags", []))[:12]
            avg_rt = info.get("avg_response_time", 0)
            print(f"  {icon} {info['name']:8s} [{info['role']:8s}] "
                  f"tags=[{tags:12s}] 状态:{info['status']:6s} "
                  f"完成:{info['tasks_completed']} 失败:{info.get('tasks_failed',0)} "
                  f"avg:{avg_rt:.1f}s")

    def show_tokens(self):
        usage = self.chancellor.tracker.get_usage()
        print(f"\n{'═' * 50}")
        print(f"Token 使用")
        print(f"{'─' * 50}")
        total_input = 0
        total_output = 0
        for agent_id, info in usage.items():
            name = self.chancellor.agents[agent_id].state.name if agent_id in self.chancellor.agents else agent_id
            print(f"  {name:8s} 输入:{info['input']:6d} 输出:{info['output']:6d}")
            total_input += info["input"]
            total_output += info["output"]
        print(f"{'─' * 50}")
        print(f"  总计    输入:{total_input:6d} 输出:{total_output:6d} 合计:{total_input+total_output}")
        print(f"  今日总消耗: {self.chancellor.tracker.get_total_today()}")

    def show_knowledge(self):
        print(f"\n{'═' * 50}")
        print(f"知识层状态")
        print(f"{'─' * 50}")

        if not self.chancellor.knowledge_router:
            print("  ⚠️ 知识层未挂载")
            return

        sources = self.chancellor.knowledge_router.list_sources()
        print(f"  已注册知识源: {len(sources)}")
        for s in sources:
            print(f"    📖 {s}")

        if self.chancellor.hanlin_director:
            hanlin = self.chancellor.hanlin_director.get_status()
            print(f"\n  翰林院:")
            print(f"    总索引文档: {hanlin['total_docs']}")
            print(f"    总检索次数: {hanlin['total_queries']}")

    def show_queue(self):
        qs = self.chancellor.task_queue.get_stats()
        print(f"\n{'═' * 50}")
        print(f"任务队列")
        print(f"{'─' * 50}")
        print(f"  提交: {qs['submitted']}  完成: {qs['completed']}  失败: {qs['failed']}  重试: {qs['retried']}")
        print(f"  队列深度: {qs['queue_size']}")
        print(f"  熔断节点: {qs['circuit_open'] or '无'}")

    def show_bus(self):
        bs = self.chancellor.bus.get_stats()
        print(f"\n{'═' * 50}")
        print(f"消息总线")
        print(f"{'─' * 50}")
        print(f"  发送: {bs['sent']}  接收: {bs['received']}")
        if bs.get("queue_depth"):
            print(f"  队列深度:")
            for aid, depth in bs["queue_depth"].items():
                print(f"    {aid}: {depth}")

    def show_memory(self, agent_id: str):
        if agent_id not in self.chancellor.agents:
            print(f"  未知节点: {agent_id}")
            return
        agent = self.chancellor.agents[agent_id]
        mem = agent.memory
        print(f"\n{'═' * 50}")
        print(f"{agent.state.name} 的记忆")
        print(f"{'─' * 50}")
        print(f"  短期记忆: {len(mem.short_term)} 条")
        print(f"  长期记忆: {len(mem.long_term)} 条")
        recent = mem.recall_recent(5)
        if recent:
            print(f"\n  最近记忆:")
            for m in recent:
                print(f"    · {m[:80]}")
        important = mem.recall_important(3)
        if important:
            print(f"\n  重要记忆:")
            for m in important:
                print(f"    ⭐ {m[:80]}")

    def show_history(self):
        history = self.chancellor.bus.get_history(20)
        print(f"\n{'═' * 50}")
        print(f"最近消息 (最新20条)")
        print(f"{'─' * 50}")
        for msg in history:
            ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
            print(f"  [{ts}] {msg.sender} → {msg.receiver} ({msg.msg_type.value}): {msg.content[:80]}")

    async def interactive(self):
        self.print_banner()
        self.print_help()

        while self.running:
            try:
                cmd = input("\n👑 皇帝> ").strip()
                if not cmd:
                    continue

                if cmd in ("exit", "quit", "q"):
                    print("帝国关闭。皇帝万岁。")
                    break
                elif cmd == "help":
                    self.print_help()
                elif cmd == "status":
                    self.show_status()
                elif cmd == "agents":
                    self.show_agents()
                elif cmd == "tokens":
                    self.show_tokens()
                elif cmd == "knowledge":
                    self.show_knowledge()
                elif cmd == "queue":
                    self.show_queue()
                elif cmd == "bus":
                    self.show_bus()
                elif cmd == "history":
                    self.show_history()
                elif cmd.startswith("memory "):
                    self.show_memory(cmd[7:].strip())
                else:
                    await self.execute_command(cmd)

            except KeyboardInterrupt:
                print("\n帝国关闭。")
                break
            except EOFError:
                break


async def main():
    cli = EmpireCLI()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--status":
            cli.show_status()
        elif arg == "--agents":
            cli.show_agents()
        elif arg == "--tokens":
            cli.show_tokens()
        elif arg == "--knowledge":
            cli.show_knowledge()
        elif arg == "--queue":
            cli.show_queue()
        elif arg == "--bus":
            cli.show_bus()
        elif arg == "--memory" and len(sys.argv) > 2:
            cli.show_memory(sys.argv[2])
        else:
            command = " ".join(sys.argv[1:])
            await cli.execute_command(command)
    else:
        await cli.interactive()


if __name__ == "__main__":
    asyncio.run(main())
