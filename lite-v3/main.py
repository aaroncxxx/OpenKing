#!/usr/bin/env python3
"""
帝国架构 v3.2 - CLI
Empire Architecture v3.2 - 因果推理 + 跨Agent知识迁移 + 记忆蒸馏 + 主动检索

用法:
  python3 main.py              # 交互模式
  python3 main.py "指令"        # 单次执行
  python3 main.py --auto "指令" # 自治模式（多轮迭代）
  python3 main.py --status     # 帝国状态
  python3 main.py --agents     # 节点列表
  python3 main.py --tokens     # Token 消耗
  python3 main.py --evolution  # 进化状态
  python3 main.py --models     # 模型状态
  python3 main.py --plugins    # 插件列表
  python3 main.py --realtime   # 实时监控
  python3 main.py --dashboard  # 启动可视化大屏
  python3 main.py --causal     # 因果图谱
  python3 main.py --library    # 帝国图书馆
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
    """帝国控制台 v3.0"""

    def __init__(self):
        self.chancellor = Chancellor()
        self.running = True

    def print_banner(self):
        print("""
╔══════════════════════════════════════════════════════════════╗
║              Empire Architecture 3.2.0                       ║
║──────────────────────────────────────────────────────────────║
║  皇帝: AARONCXXX         丞相: MIMO                          ║
║  节点: 256+              知识层: 已挂载                      ║
║──────────────────────────────────────────────────────────────║
║  🧠 自进化  🌐 多模型  🔌 插件  📡 实时  🎨 大屏  🤖 自治   ║
║  🔗 因果推理  📚 帝国图书馆  🧪 记忆蒸馏  🔍 主动检索       ║
╚══════════════════════════════════════════════════════════════╝
        """)

    def print_help(self):
        print("""
命令:
  <指令>           向帝国下达指令
  auto <指令>      自治模式（多轮迭代优化）
  status           帝国状态
  agents           节点状态
  tokens           Token 使用
  evolution        进化状态
  models           可用模型
  plugins          插件列表
  realtime         实时监控状态
  dashboard        启动可视化大屏
  memory <id>      Agent 记忆
  bus              消息总线
  history          消息历史

  ─── v3.2 记忆系统 ───
  causal           因果图谱状态与可视化
  causal add <因> <果> [置信度]  添加因果关系
  causal infer <节点> [forward|backward]  因果推理
  library          帝国图书馆状态
  library search <关键词>  搜索共享知识
  library publish <内容> [--tags a,b] [--cat 分类]  发布知识
  distill [agent_id]  执行记忆蒸馏
  proactive        主动检索器状态

  help             帮助
  exit / quit      退出
        """)

    async def execute_command(self, command: str, autonomous: bool = False):
        mode = "🤖 自治" if autonomous else "⚡ 普通"
        print(f"\n{mode} 丞相接令，开始编排...")
        print(f"{'─' * 50}")

        try:
            result = await self.chancellor.receive_command(command, autonomous=autonomous)

            print(f"\n📋 任务 {result['task_id']} 完成 ({result['elapsed_seconds']}s)")
            print(f"{'─' * 50}")

            if autonomous:
                print(f"🔄 迭代次数: {result.get('iterations', 1)}")
                print(f"📊 最终评分: {result.get('score', 0):.2f}")

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

            print(f"\n⏱  耗时: {result['elapsed_seconds']}s | Token 今日: {result['tokens_used']}")

        except Exception as e:
            print(f"\n❌ 执行失败: {e}")
            log.error(f"执行失败: {e}", exc_info=True)

    def show_status(self):
        status = self.chancellor.get_status()
        print(f"\n{'═' * 50}")
        print(f"帝国状态 v{status['version']}")
        print(f"{'─' * 50}")
        print(f"节点数: {len(status['agents'])}")
        print(f"消息总数: {status['message_history']}")
        print(f"安全事件: {status['security']['total_violations']}")
        print(f"任务队列: 提交={status['task_queue']['submitted']} 完成={status['task_queue']['completed']} 失败={status['task_queue']['failed']}")

        evo = status.get("evolution", {})
        print(f"\n🧠 进化系统:")
        print(f"  评估总数: {evo.get('total_evaluations', 0)}")
        print(f"  跟踪节点: {evo.get('agents_tracked', 0)}")
        print(f"  进化 prompt: {evo.get('evolved_prompts', 0)} 个")

        rt = status.get("realtime", {})
        print(f"\n📡 实时监控: {'运行中' if rt.get('running') else '未启动'}")
        print(f"  监控规则: {rt.get('rules', 0)}")
        print(f"  Webhook: {rt.get('webhooks', 0)}")

        print(f"\n🔌 插件: {len(status.get('plugins', []))} 个")

    def show_agents(self):
        status = self.chancellor.get_status()
        print(f"\n{'═' * 50}")
        print(f"节点状态 (共{len(status['agents'])}个)")
        print(f"{'─' * 50}")
        for aid, info in status["agents"].items():
            icon = {"idle": "🟢", "busy": "🟡", "error": "🔴"}.get(info["status"], "⚪")
            tags = ",".join(info.get("tags", []))[:12]
            score = info.get("performance_score", 1.0)
            evo = self.chancellor.evolution.get_agent_evolution_status(aid)
            rank = evo.get("rank", "")
            rank_str = f" [{rank}]" if rank else ""
            print(f"  {icon} {info['name']:8s} [{info['role']:8s}] "
                  f"tags=[{tags:12s}] 评分:{score:.2f}{rank_str} "
                  f"完成:{info['tasks_completed']} 失败:{info.get('tasks_failed', 0)}")

    def show_tokens(self):
        usage = self.chancellor.tracker.get_usage()
        cost = self.chancellor.tracker.get_cost_summary()
        print(f"\n{'═' * 50}")
        print(f"Token 使用 & 成本")
        print(f"{'─' * 50}")
        total_input = 0
        total_output = 0
        total_cost = 0
        for agent_id, info in usage.items():
            name = self.chancellor.agents[agent_id].state.name if agent_id in self.chancellor.agents else agent_id
            print(f"  {name:8s} 输入:{info['input']:6d} 输出:{info['output']:6d}")
            total_input += info["input"]
            total_output += info["output"]
        print(f"{'─' * 50}")
        print(f"  总计    输入:{total_input:6d} 输出:{total_output:6d} 合计:{total_input+total_output}")

        if cost:
            print(f"\n  按模型:")
            for model, stats in cost.items():
                print(f"    {model}: {stats['calls']}次 成本=${stats['cost']:.4f}")

    def show_evolution(self):
        evo = self.chancellor.evolution
        status = evo.get_all_status()
        print(f"\n{'═' * 50}")
        print(f"🧠 自进化系统")
        print(f"{'─' * 50}")
        print(f"评估总数: {status['total_evaluations']}")
        print(f"跟踪节点: {status['agents_tracked']}")
        print(f"进化 prompt: {status['evolved_prompts']} 个")

        ranks = status.get("ranks", {})
        if ranks:
            print(f"\n等级分布:")
            rank_count = {}
            for agent_id, rank in ranks.items():
                rank_count[rank] = rank_count.get(rank, 0) + 1
            for rank, count in sorted(rank_count.items()):
                print(f"  {rank}: {count} 人")

        # 显示 top 5
        all_scores = []
        for agent_id in self.chancellor.agents:
            evo_status = evo.get_agent_evolution_status(agent_id)
            if evo_status.get("evaluations", 0) > 0:
                all_scores.append((agent_id, evo_status.get("avg_overall", 0), evo_status.get("rank", "")))
        all_scores.sort(key=lambda x: -x[1])
        if all_scores:
            print(f"\nTop 5 Agent:")
            for aid, score, rank in all_scores[:5]:
                name = self.chancellor.agents[aid].state.name if aid in self.chancellor.agents else aid
                print(f"  {name:8s} 评分:{score:.2f} 等级:{rank}")

    def show_models(self):
        from core.model_router import get_available_models
        models = get_available_models()
        print(f"\n{'═' * 50}")
        print(f"🌐 可用模型")
        print(f"{'─' * 50}")
        for alias, cfg in models.items():
            cost = cfg.get("cost_per_1k_input", 0)
            print(f"  {alias:12s} → {cfg['name']:25s} max_tokens={cfg.get('max_tokens', '?')} cost=${cost}/1k")

    def show_plugins(self):
        plugins = self.chancellor.plugins.discover_plugins()
        loaded = self.chancellor.plugins.loaded_plugins
        print(f"\n{'═' * 50}")
        print(f"🔌 插件系统")
        print(f"{'─' * 50}")
        if not plugins:
            print("  暂无插件")
            return
        for p in plugins:
            status = "✅ 已加载" if p["_id"] in loaded else "⬜ 未加载"
            print(f"  {status} {p.get('name', p['_id'])} v{p.get('version', '?')}")

    def show_realtime(self):
        rt = self.chancellor.realtime.get_status()
        print(f"\n{'═' * 50}")
        print(f"📡 实时监控")
        print(f"{'─' * 50}")
        print(f"状态: {'🟢 运行中' if rt['running'] else '🔴 未启动'}")
        print(f"监控规则: {rt['rules']}")
        print(f"Webhook: {rt['webhooks']}")
        if rt.get("rules_detail"):
            print(f"\n规则详情:")
            for r in rt["rules_detail"]:
                icon = "🟢" if r["enabled"] else "🔴"
                print(f"  {icon} {r['name']} (间隔 {r['interval']}s)")

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
                elif cmd == "evolution":
                    self.show_evolution()
                elif cmd == "models":
                    self.show_models()
                elif cmd == "plugins":
                    self.show_plugins()
                elif cmd == "realtime":
                    self.show_realtime()
                elif cmd.startswith("auto "):
                    await self.execute_command(cmd[5:], autonomous=True)
                elif cmd.startswith("memory "):
                    self.show_memory(cmd[7:].strip())
                elif cmd == "bus":
                    self.show_bus()
                elif cmd == "history":
                    self.show_history()
                elif cmd == "dashboard":
                    print("启动 Dashboard... 请运行: streamlit run dashboard/app.py")
                # ─── v3.2 记忆系统命令 ───
                elif cmd == "causal":
                    self.show_causal()
                elif cmd.startswith("causal add "):
                    self.cmd_causal_add(cmd[11:].strip())
                elif cmd.startswith("causal infer "):
                    self.cmd_causal_infer(cmd[14:].strip())
                elif cmd == "library":
                    self.show_library()
                elif cmd.startswith("library search "):
                    self.cmd_library_search(cmd[16:].strip())
                elif cmd.startswith("library publish "):
                    self.cmd_library_publish(cmd[17:].strip())
                elif cmd.startswith("distill"):
                    self.cmd_distill(cmd[7:].strip())
                elif cmd == "proactive":
                    self.show_proactive()
                else:
                    await self.execute_command(cmd)

            except KeyboardInterrupt:
                print("\n帝国关闭。")
                break
            except EOFError:
                break

    def show_memory(self, agent_id: str):
        if agent_id not in self.chancellor.agents:
            print(f"  未知节点: {agent_id}")
            return
        agent = self.chancellor.agents[agent_id]
        mem = agent.memory
        print(f"\n{'═' * 50}")
        print(f"{agent.state.name} 的记忆")
        print(f"{'─' * 50}")
        print(f"  短期: {len(mem.short_term)} 条 | 长期: {len(mem.long_term)} 条")
        for m in mem.recall_recent(5):
            print(f"  · {m[:80]}")

    def show_bus(self):
        bs = self.chancellor.bus.get_stats()
        print(f"\n{'═' * 50}")
        print(f"消息总线")
        print(f"{'─' * 50}")
        print(f"  发送: {bs['sent']}  接收: {bs['received']}")

    def show_history(self):
        history = self.chancellor.bus.get_history(20)
        print(f"\n{'═' * 50}")
        print(f"最近消息 (最新20条)")
        print(f"{'─' * 50}")
        for msg in history:
            ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
            print(f"  [{ts}] {msg.sender} → {msg.receiver}: {msg.content[:80]}")

    # ──────────────── v3.2: 因果图谱命令 ────────────────

    def show_causal(self):
        cg = self.chancellor.causal_graph
        stats = cg.get_stats()
        print(f"\n{'═' * 50}")
        print(f"🔗 因果记忆图谱")
        print(f"{'─' * 50}")
        print(f"  节点数: {stats['total_nodes']}")
        print(f"  关系数: {stats['total_edges']}")
        print(f"  因源数: {stats['forward_sources']}")
        print(f"  果目标: {stats['backward_targets']}")

        nodes = cg.get_all_nodes()
        if nodes:
            print(f"\n  所有节点: {', '.join(sorted(nodes))}")
            # 显示最近的因果关系
            recent = sorted(cg._edges.values(), key=lambda e: -e.timestamp)[:10]
            if recent:
                print(f"\n  最近的因果关系:")
                for e in recent:
                    print(f"    {e.cause} → {e.effect} [置信度 {e.confidence:.0%}]")

    def cmd_causal_add(self, args: str):
        parts = args.split()
        if len(parts) < 2:
            print("  用法: causal add <因> <果> [置信度]")
            return
        cause, effect = parts[0], parts[1]
        confidence = float(parts[2]) if len(parts) > 2 else 0.7
        edge = self.chancellor.causal_graph.add_cause_effect(cause, effect, confidence)
        print(f"  ✅ 添加因果关系: {cause} → {effect} [置信度 {confidence:.0%}] (id={edge.edge_id})")

    def cmd_causal_infer(self, args: str):
        parts = args.split()
        if not parts:
            print("  用法: causal infer <节点> [forward|backward]")
            return
        node = parts[0]
        direction = parts[1] if len(parts) > 1 else "forward"
        cg = self.chancellor.causal_graph

        if direction == "forward":
            results = cg.infer_effects(node)
            label = "结果"
        else:
            results = cg.infer_causes(node)
            label = "原因"

        if not results:
            print(f"  未找到「{node}」的{label}")
            return

        print(f"\n  「{node}」的可能{label}:")
        for name, conf in results:
            print(f"    → {name} [置信度 {conf:.0%}]")

        # 显示因果链
        viz = cg.visualize_chain(node, direction=direction)
        print(f"\n{viz}")

    # ──────────────── v3.2: 帝国图书馆命令 ────────────────

    def show_library(self):
        lib = self.chancellor.library
        stats = lib.get_stats()
        print(f"\n{'═' * 50}")
        print(f"📚 帝国图书馆")
        print(f"{'─' * 50}")
        print(f"  知识条目: {stats['total_entries']}")
        print(f"  标签数: {stats['total_tags']}")
        print(f"  作者数: {stats['total_authors']}")
        if stats['categories']:
            print(f"\n  分类分布:")
            for cat, count in stats['categories'].items():
                print(f"    {cat}: {count} 条")

    def cmd_library_search(self, query: str):
        if not query:
            print("  用法: library search <关键词>")
            return
        results = self.chancellor.library.search_knowledge(query, top_k=5)
        if not results:
            print(f"  未找到「{query}」相关知识")
            return
        print(f"\n  搜索「{query}」结果 ({len(results)} 条):")
        for i, entry in enumerate(results, 1):
            tags = ", ".join(entry.tags[:5]) if entry.tags else "无标签"
            print(f"  {i}. [{entry.category}] {entry.content[:80]}")
            print(f"     作者: {entry.author} | 标签: {tags} | 版本: v{entry.version}")

    def cmd_library_publish(self, args: str):
        if not args:
            print("  用法: library publish <内容> [--tags a,b] [--cat 分类]")
            return
        # 解析参数
        content = args
        tags = []
        category = "general"
        if "--tags" in args:
            parts = args.split("--tags")
            content = parts[0].strip()
            tag_part = parts[1].split("--")[0].strip() if "--" in parts[1] else parts[1].strip()
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
        if "--cat" in args:
            parts = args.split("--cat")
            if not content or content == args.split("--cat")[0]:
                content = parts[0].strip()
            category = parts[1].strip().split()[0] if parts[1].strip() else "general"

        entry = self.chancellor.library.publish_knowledge(
            "cli_user", content, tags=tags, category=category,
        )
        print(f"  ✅ 发布知识: {entry.knowledge_id}")
        print(f"     内容: {content[:80]}")
        print(f"     分类: {category} | 标签: {', '.join(tags) if tags else '无'}")

    # ──────────────── v3.2: 记忆蒸馏命令 ────────────────

    def cmd_distill(self, agent_id: str):
        if agent_id:
            # 指定 agent
            agent = self.chancellor.agents.get(agent_id)
            if not agent or not agent.distiller:
                print(f"  未知节点或该节点无蒸馏器: {agent_id}")
                return
            distiller = agent.distiller
        else:
            # 全局蒸馏
            print(f"  对所有 Agent 执行记忆蒸馏...")
            total_new = 0
            for aid, agent in self.chancellor.agents.items():
                if agent.distiller:
                    new = agent.distiller.distill()
                    total_new += len(new)
                    if new:
                        print(f"    {aid}: 蒸馏出 {len(new)} 条规律")
            print(f"  ✅ 全局蒸馏完成: 共 {total_new} 条新规律")
            return

        results = distiller.distill()
        if results:
            print(f"\n  蒸馏出 {len(results)} 条新规律:")
            for d in results:
                print(f"    · {d.pattern} [置信度 {d.confidence:.0%}, 证据 {d.evidence_count}]")
        else:
            print(f"  无新规律（数据不足或已全部蒸馏）")

        summary = distiller.get_distillate_summary()
        if summary:
            print(f"\n{summary}")

    # ──────────────── v3.2: 主动检索命令 ────────────────

    def show_proactive(self):
        print(f"\n{'═' * 50}")
        print(f"🔍 主动记忆检索器")
        print(f"{'─' * 50}")
        total_rules = 0
        total_enabled = 0
        for aid, agent in self.chancellor.agents.items():
            if agent.retriever:
                stats = agent.retriever.get_stats()
                total_rules += stats['total_rules']
                total_enabled += stats['enabled_rules']
                if stats['total_rules'] > 0:
                    print(f"  {aid}: {stats['total_rules']} 规则 ({stats['enabled_rules']} 启用)")

        print(f"\n  总计: {total_rules} 规则 ({total_enabled} 启用)")


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
        elif arg == "--evolution":
            cli.show_evolution()
        elif arg == "--models":
            cli.show_models()
        elif arg == "--plugins":
            cli.show_plugins()
        elif arg == "--realtime":
            cli.show_realtime()
        elif arg == "--causal":
            cli.show_causal()
        elif arg == "--library":
            cli.show_library()
        elif arg == "--auto" and len(sys.argv) > 2:
            command = " ".join(sys.argv[2:])
            await cli.execute_command(command, autonomous=True)
        elif arg == "--dashboard":
            print("启动 Dashboard: streamlit run dashboard/app.py")
        else:
            command = " ".join(sys.argv[1:])
            await cli.execute_command(command)
    else:
        await cli.interactive()


if __name__ == "__main__":
    asyncio.run(main())
