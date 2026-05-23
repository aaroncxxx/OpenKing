"""帝国架构 v3.2 - 记忆系统单元测试

测试覆盖：
- 原有 Memory3D 接口（向后兼容）
- CausalMemoryGraph（因果推理）
- ImperialLibrary（跨Agent知识共享）
- MemoryDistiller（记忆蒸馏）
- ProactiveRetriever（主动记忆检索）
"""
import json
import os
import shutil
import tempfile
import time
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory3d import (
    MemoryForm, MemoryFunction, MemoryEngram, Memory3D,
    CausalEdge, CausalMemoryGraph,
    KnowledgeEntry, ImperialLibrary,
    Distillate, MemoryDistiller,
    TriggerRule, ProactiveRetriever,
)


class _TmpDirMixin:
    """每个测试用例使用独立临时目录"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="empire_test_")

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
#  原有 Memory3D 测试（向后兼容性验证）
# ═══════════════════════════════════════════════════════════════

class TestMemory3DBasic(_TmpDirMixin, unittest.TestCase):
    """Memory3D 基础功能测试"""

    def test_form_and_retrieve(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        e = m.form("Python 是一种编程语言", importance=0.8, tags=["python", "coding"])
        self.assertIsInstance(e, MemoryEngram)
        self.assertEqual(e.content, "Python 是一种编程语言")
        self.assertIn(e.engram_id, m.engrams)

        results = m.retrieve("Python 编程", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].content, "Python 是一种编程语言")

    def test_form_defaults(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        e = m.form("test")
        self.assertEqual(e.form, MemoryForm.TOKEN)
        self.assertEqual(e.function, MemoryFunction.EPISODIC)
        self.assertEqual(e.importance, 0.5)

    def test_consolidate(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        e = m.form("important event", importance=0.9)
        self.assertEqual(e.consolidation_level, 0.0)
        m.consolidate()
        # 高重要性应被巩固
        self.assertGreater(m.engrams[e.engram_id].consolidation_level, 0.0)

    def test_forget(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        e = m.form("forgettable", importance=0.01)
        # 手动设置强度为极低
        m.engrams[e.engram_id].strength = 0.01
        m.engrams[e.engram_id].last_accessed = time.time() - 999999
        forgotten = m.forget(decay_rate=1.0)
        self.assertGreater(forgotten, 0)
        self.assertNotIn(e.engram_id, m.engrams)

    def test_update(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        e = m.form("original")
        ok = m.update(e.engram_id, content="updated", importance=0.9)
        self.assertTrue(ok)
        self.assertEqual(m.engrams[e.engram_id].content, "updated")
        self.assertEqual(m.engrams[e.engram_id].importance, 0.9)

    def test_update_nonexistent(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        self.assertFalse(m.update("nonexistent", content="x"))

    def test_lifecycle_tick(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("lifecycle test", importance=0.8)
        m.lifecycle_tick()  # 不应抛异常

    def test_get_stats(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("a", function=MemoryFunction.EPISODIC)
        m.form("b", function=MemoryFunction.SEMANTIC)
        stats = m.get_stats()
        self.assertEqual(stats["total_engrams"], 2)
        self.assertEqual(stats["by_function"]["episodic"], 1)
        self.assertEqual(stats["by_function"]["semantic"], 1)

    def test_context_window(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("recent event", function=MemoryFunction.EPISODIC)
        m.form("some knowledge", function=MemoryFunction.SEMANTIC)
        m.form("a skill", function=MemoryFunction.PROCEDURAL)
        ctx = m.get_context_window(max_chars=500)
        self.assertIn("recent event", ctx)
        self.assertIn("some knowledge", ctx)
        self.assertIn("a skill", ctx)

    def test_export_import_shared(self):
        m1 = Memory3D("agent1", data_dir=self._tmpdir)
        m1.form("shared knowledge", function=MemoryFunction.SEMANTIC, tags=["public"])
        exported = m1.export_shareable(privacy_level=0)
        self.assertGreater(len(exported), 0)

        m2 = Memory3D("agent2", data_dir=self._tmpdir)
        m2.import_shared(exported, source="agent1")
        self.assertGreater(len(m2.engrams), 0)

    def test_export_privacy_levels(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("episodic event", function=MemoryFunction.EPISODIC, tags=["private"])
        m.form("public fact", function=MemoryFunction.SEMANTIC, tags=["public"])

        # privacy=2: 只有语义记忆
        exported = m.export_shareable(privacy_level=2)
        for entry in exported:
            self.assertEqual(entry["function"], "semantic")

    def test_persistence(self):
        m1 = Memory3D("persist_agent", data_dir=self._tmpdir)
        m1.form("persistent memory", importance=0.7)
        m1._save()

        m2 = Memory3D("persist_agent", data_dir=self._tmpdir)
        self.assertEqual(len(m2.engrams), 1)
        contents = [e.content for e in m2.engrams.values()]
        self.assertIn("persistent memory", contents)

    def test_compat_remember(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.remember("old interface", importance=0.6, tags=["compat"])
        self.assertEqual(len(m.engrams), 1)

    def test_compat_recall_recent(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("first")
        time.sleep(0.01)
        m.form("second")
        recent = m.recall_recent(n=2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0], "second")  # 最新的在前

    def test_compat_recall_important(self):
        m = Memory3D("agent1", data_dir=self._tmpdir)
        m.form("low", importance=0.1)
        m.form("high", importance=0.9)
        important = m.recall_important(n=1)
        self.assertEqual(important[0], "high")


# ═══════════════════════════════════════════════════════════════
#  CausalMemoryGraph 测试
# ═══════════════════════════════════════════════════════════════

class TestCausalMemoryGraph(_TmpDirMixin, unittest.TestCase):

    def test_add_and_infer_effects(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("下雨", "地面湿", 0.9)
        cg.add_cause_effect("下雨", "交通拥堵", 0.6)

        effects = cg.infer_effects("下雨")
        self.assertEqual(len(effects), 2)
        self.assertEqual(effects[0][0], "地面湿")  # 按置信度降序
        self.assertAlmostEqual(effects[0][1], 0.9)

    def test_infer_causes(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("bug", "crash", 0.8)
        cg.add_cause_effect("memory_leak", "crash", 0.7)

        causes = cg.infer_causes("crash")
        self.assertEqual(len(causes), 2)
        self.assertEqual(causes[0][0], "bug")

    def test_infer_effects_empty(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        self.assertEqual(cg.infer_effects("unknown"), [])

    def test_min_confidence_filter(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("A", "B", 0.3)
        cg.add_cause_effect("A", "C", 0.8)

        effects = cg.infer_effects("A", min_confidence=0.5)
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0][0], "C")

    def test_causal_chain_forward(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("A", "B", 0.9)
        cg.add_cause_effect("B", "C", 0.8)
        cg.add_cause_effect("C", "D", 0.7)

        paths = cg.infer_chain_forward("A", max_depth=5)
        self.assertGreater(len(paths), 0)
        # 最长路径应包含 A→B→C→D
        longest = max(paths, key=len)
        self.assertEqual(len(longest), 4)
        self.assertEqual(longest[0][0], "A")
        self.assertEqual(longest[-1][0], "D")

    def test_causal_chain_cycle(self):
        """环形因果链不应无限循环"""
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("A", "B", 0.9)
        cg.add_cause_effect("B", "A", 0.8)  # 环

        paths = cg.infer_chain_forward("A", max_depth=5)
        # 应能正常返回，不卡死
        self.assertGreater(len(paths), 0)

    def test_visualize_chain(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("root", "child1", 0.9)
        cg.add_cause_effect("root", "child2", 0.7)

        viz = cg.visualize_chain("root", direction="forward")
        self.assertIn("root", viz)
        self.assertIn("child1", viz)
        self.assertIn("child2", viz)
        self.assertIn("🌳", viz)

    def test_visualize_chain_empty(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        viz = cg.visualize_chain("nothing")
        # 无因果边时，起始节点自身仍会显示
        self.assertIn("nothing", viz)

    def test_backward_visualize(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("X", "Y", 0.9)
        cg.add_cause_effect("Y", "Z", 0.8)
        viz = cg.visualize_chain("Z", direction="backward")
        self.assertIn("Z", viz)

    def test_remove_edge(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        edge = cg.add_cause_effect("A", "B", 0.9)
        self.assertTrue(cg.remove_edge(edge.edge_id))
        self.assertEqual(cg.infer_effects("A"), [])
        self.assertFalse(cg.remove_edge("nonexistent"))

    def test_get_all_nodes(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("X", "Y", 0.9)
        cg.add_cause_effect("Y", "Z", 0.8)
        nodes = cg.get_all_nodes()
        self.assertEqual(nodes, {"X", "Y", "Z"})

    def test_get_stats(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("A", "B", 0.9)
        stats = cg.get_stats()
        self.assertEqual(stats["total_edges"], 1)
        self.assertEqual(stats["total_nodes"], 2)

    def test_persistence(self):
        d = os.path.join(self._tmpdir, "persist")
        cg1 = CausalMemoryGraph(data_dir=d)
        cg1.add_cause_effect("cause", "effect", 0.85)

        cg2 = CausalMemoryGraph(data_dir=d)
        self.assertEqual(len(cg2._edges), 1)
        effects = cg2.infer_effects("cause")
        self.assertEqual(len(effects), 1)
        self.assertAlmostEqual(effects[0][1], 0.85)

    def test_confidence_clamped(self):
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        edge = cg.add_cause_effect("A", "B", confidence=1.5)
        self.assertAlmostEqual(edge.confidence, 1.0)
        edge2 = cg.add_cause_effect("C", "D", confidence=-0.5)
        self.assertAlmostEqual(edge2.confidence, 0.0)

    def test_thread_safety(self):
        """并发添加不崩溃"""
        import threading
        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        errors = []

        def add_edges(prefix, n):
            try:
                for i in range(n):
                    cg.add_cause_effect(f"{prefix}_cause_{i}", f"{prefix}_effect_{i}", 0.5)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_edges, args=(f"t{t}", 20)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(cg._edges), 80)


# ═══════════════════════════════════════════════════════════════
#  ImperialLibrary 测试
# ═══════════════════════════════════════════════════════════════

class TestImperialLibrary(_TmpDirMixin, unittest.TestCase):

    def test_publish_and_search(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("agent1", "如何使用 Python 进行数据分析",
                              tags=["python", "data"], category="technical")
        results = lib.search_knowledge("Python 数据")
        self.assertGreater(len(results), 0)
        self.assertIn("Python", results[0].content)

    def test_publish_default_category(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("agent1", "test", category="invalid_category")
        self.assertEqual(entry.category, "general")  # 无效分类降级为 general

    def test_search_with_category_filter(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "tech content", category="technical")
        lib.publish_knowledge("b", "strategy content", category="strategy")

        results = lib.search_knowledge("", category="technical")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "technical")

    def test_search_with_tag_filter(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "content A", tags=["alpha", "shared"])
        lib.publish_knowledge("b", "content B", tags=["beta", "shared"])

        results = lib.search_knowledge("", tags=["alpha"])
        self.assertEqual(len(results), 1)

    def test_access_control(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("admin", "secret knowledge")
        kid = entry.knowledge_id

        # 默认全局可见
        results = lib.search_knowledge("secret", requester_id="agent1")
        self.assertEqual(len(results), 1)

        # 授权后可见
        lib.grant_access("agent1", kid)
        results = lib.search_knowledge("secret", requester_id="agent1")
        self.assertEqual(len(results), 1)

        # 撤销后不可见（非作者）
        lib.revoke_access("agent1", kid)
        lib.grant_access("agent2", kid)  # 设置 ACL 使非 ACL 内的不可见
        lib.revoke_access("agent2", kid)
        # 当 ACL 为空时全局可见，所以需要设置一个非空 ACL
        lib.grant_access("only_agent", kid)
        results = lib.search_knowledge("secret", requester_id="agent1")
        self.assertEqual(len(results), 0)

    def test_access_control_author_always_visible(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("admin", "my knowledge")
        lib.grant_access("someone_else", entry.knowledge_id)
        # 作者始终可见
        results = lib.search_knowledge("knowledge", requester_id="admin")
        self.assertEqual(len(results), 1)

    def test_version_control(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("agent1", "version 1", tags=["v1"])
        kid = entry.knowledge_id

        lib.update_knowledge(kid, "agent1", new_content="version 2", new_tags=["v2"])
        entry = lib.get_by_id(kid)
        self.assertEqual(entry.content, "version 2")
        self.assertEqual(entry.version, 2)
        self.assertEqual(len(entry.history), 1)
        self.assertEqual(entry.history[0]["content"], "version 1")

    def test_rollback(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("agent1", "original")
        kid = entry.knowledge_id

        lib.update_knowledge(kid, "agent1", new_content="changed")
        ok = lib.rollback_knowledge(kid, target_version=1)
        self.assertTrue(ok)
        entry = lib.get_by_id(kid)
        self.assertEqual(entry.content, "original")
        self.assertEqual(entry.version, 3)  # rollback 也增加版本号

    def test_rollback_nonexistent(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        self.assertFalse(lib.rollback_knowledge("no_such_id", 1))

    def test_rollback_invalid_version(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("agent1", "content")
        self.assertFalse(lib.rollback_knowledge(entry.knowledge_id, 999))

    def test_get_by_tags(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "A", tags=["x", "y"])
        lib.publish_knowledge("b", "B", tags=["y", "z"])
        results = lib.get_by_tags(["y"])
        self.assertEqual(len(results), 2)

    def test_get_by_category(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "A", category="technical")
        lib.publish_knowledge("b", "B", category="strategy")
        results = lib.get_by_category("technical")
        self.assertEqual(len(results), 1)

    def test_get_by_author(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("alice", "A")
        lib.publish_knowledge("alice", "B")
        lib.publish_knowledge("bob", "C")
        results = lib.get_by_author("alice")
        self.assertEqual(len(results), 2)

    def test_get_version_history(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("a", "v1")
        lib.update_knowledge(entry.knowledge_id, "a", new_content="v2")
        history = lib.get_version_history(entry.knowledge_id)
        self.assertEqual(len(history), 2)  # v1 历史 + v2 当前

    def test_get_stats(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "A", tags=["t1"], category="technical")
        lib.publish_knowledge("b", "B", tags=["t2"], category="strategy")
        stats = lib.get_stats()
        self.assertEqual(stats["total_entries"], 2)
        self.assertEqual(stats["total_authors"], 2)

    def test_persistence(self):
        d = os.path.join(self._tmpdir, "persist")
        lib1 = ImperialLibrary(data_dir=d)
        lib1.publish_knowledge("agent1", "persistent knowledge", tags=["test"])

        lib2 = ImperialLibrary(data_dir=d)
        self.assertEqual(len(lib2._entries), 1)
        results = lib2.search_knowledge("persistent")
        self.assertGreater(len(results), 0)

    def test_grant_revoke_idempotent(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        entry = lib.publish_knowledge("a", "content")
        kid = entry.knowledge_id
        # 重复授权不报错
        self.assertTrue(lib.grant_access("x", kid))
        self.assertTrue(lib.grant_access("x", kid))
        # 重复撤销不报错
        self.assertTrue(lib.revoke_access("x", kid))
        self.assertTrue(lib.revoke_access("x", kid))

    def test_get_accessible_knowledge(self):
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("a", "public")
        lib.publish_knowledge("b", "restricted")
        entry_c = lib.publish_knowledge("c", "secret")
        lib.grant_access("special_agent", entry_c.knowledge_id)

        accessible = lib.get_accessible_knowledge("special_agent")
        # 可见：public（无ACL）+ restricted（无ACL）+ secret（有授权）
        self.assertEqual(len(accessible), 3)


# ═══════════════════════════════════════════════════════════════
#  MemoryDistiller 测试
# ═══════════════════════════════════════════════════════════════

class TestMemoryDistiller(_TmpDirMixin, unittest.TestCase):

    def _make_memory_with_data(self) -> Memory3D:
        """创建含有多条记忆的 Memory3D 实例"""
        m = Memory3D("distill_agent", data_dir=self._tmpdir)
        # 添加重复主题的记忆（统一用词，确保共现分析有效）
        for i in range(5):
            m.form(f"Python 编程语言学习经验总结", tags=["python", "coding"])
        for i in range(4):
            m.form(f"机器学习模型训练优化经验", tags=["ml", "training"])
        for i in range(3):
            m.form(f"Python 机器学习编程实践", tags=["python", "ml"])
        return m

    def test_distill_basic(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill(min_evidence=2, min_confidence=0.1)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, Distillate)
            self.assertGreater(r.evidence_count, 0)

    def test_distill_frequency_patterns(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill(min_evidence=2, min_confidence=0.1)
        freq = [r for r in results if r.category == "frequency"]
        self.assertGreater(len(freq), 0)

    def test_distill_co_occurrence(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill(min_evidence=2, min_confidence=0.1)
        co = [r for r in results if r.category == "co_occurrence"]
        self.assertGreater(len(co), 0)

    def test_distill_tag_clusters(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill(min_evidence=2, min_confidence=0.1)
        tag_results = [r for r in results if "python" in r.tags or "ml" in r.tags]
        self.assertGreater(len(tag_results), 0)

    def test_distill_too_few_engrams(self):
        m = Memory3D("sparse", data_dir=self._tmpdir)
        m.form("only one")
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill()
        self.assertEqual(len(results), 0)

    def test_distill_dedup(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        d.distill(min_evidence=2, min_confidence=0.1)
        first_count = len(d.distillates)
        d.distill(min_evidence=2, min_confidence=0.1)
        # 不应产生大量重复
        self.assertLessEqual(len(d.distillates), first_count * 1.5 + 5)

    def test_auto_distill(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        d.set_distill_interval(0)  # 立即触发
        d._last_distill_time = 0
        results = d.auto_distill_if_needed()
        self.assertGreater(len(results), 0)

    def test_auto_distill_not_triggered(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        d.set_distill_interval(9999)
        d._last_distill_time = time.time()
        results = d.auto_distill_if_needed()
        self.assertEqual(len(results), 0)

    def test_get_distillates_filtered(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        d.distill(min_evidence=2, min_confidence=0.1)
        freq = d.get_distillates(category="frequency")
        for r in freq:
            self.assertEqual(r.category, "frequency")

    def test_distillate_summary(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        d.distill(min_evidence=2, min_confidence=0.1)
        summary = d.get_distillate_summary()
        if d.distillates:
            self.assertIn("蒸馏知识", summary)

    def test_get_stats(self):
        m = self._make_memory_with_data()
        d = MemoryDistiller(m, data_dir=self._tmpdir)
        stats = d.get_stats()
        self.assertIn("total_distillates", stats)
        self.assertIn("interval_seconds", stats)

    def test_persistence(self):
        m = self._make_memory_with_data()
        d = os.path.join(self._tmpdir, "persist")
        dist1 = MemoryDistiller(m, data_dir=d)
        dist1.distill(min_evidence=2, min_confidence=0.1)
        count1 = len(dist1.distillates)

        dist2 = MemoryDistiller(m, data_dir=d)
        self.assertEqual(len(dist2.distillates), count1)


# ═══════════════════════════════════════════════════════════════
#  ProactiveRetriever 测试
# ═══════════════════════════════════════════════════════════════

class TestProactiveRetriever(_TmpDirMixin, unittest.TestCase):

    def _make_memory(self) -> Memory3D:
        m = Memory3D("proactive_agent", data_dir=self._tmpdir)
        m.form("Python 编程技巧", tags=["python", "coding"])
        m.form("数据库优化方案", tags=["database", "optimization"])
        m.form("Python 数据库连接", tags=["python", "database"])
        return m

    def test_register_trigger(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        rule = pr.register_trigger(["python", "编程"], description="Python 相关")
        self.assertIsInstance(rule, TriggerRule)
        self.assertEqual(rule.keywords, ["python", "编程"])

    def test_remove_trigger(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        rule = pr.register_trigger(["test"])
        self.assertTrue(pr.remove_trigger(rule.rule_id))
        self.assertEqual(len(pr.get_rules()), 0)
        self.assertFalse(pr.remove_trigger("nonexistent"))

    def test_enable_disable_trigger(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        rule = pr.register_trigger(["test"])
        self.assertTrue(pr.disable_trigger(rule.rule_id))
        self.assertFalse(pr.get_rules()[0].enabled)
        self.assertTrue(pr.enable_trigger(rule.rule_id))
        self.assertTrue(pr.get_rules()[0].enabled)

    def test_on_context_change_triggers(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python"], description="Python trigger")
        results = pr.on_context_change("我在学习 python 编程")
        self.assertGreater(len(results), 0)

    def test_on_context_change_no_match(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["quantum", "physics"])
        results = pr.on_context_change("今天天气不错")
        self.assertEqual(len(results), 0)

    def test_cooldown(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python"], cooldown=9999)

        pr.on_context_change("python 代码")  # 第一次触发
        results = pr.on_context_change("python 测试")  # 冷却中，不触发
        # 冷却期内不会通过触发规则检索，但 on_context_change 仍返回空
        # （因为触发规则被跳过）
        self.assertEqual(len(results), 0)

    def test_callback_invoked(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        callback_results = []

        def on_trigger(memories):
            callback_results.extend(memories)

        pr.register_trigger(["python"], callback=on_trigger)
        pr.on_context_change("python 学习")
        self.assertGreater(len(callback_results), 0)

    def test_callback_exception_handled(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)

        def bad_callback(memories):
            raise ValueError("intentional error")

        pr.register_trigger(["python"], callback=bad_callback)
        # 不应抛异常
        results = pr.on_context_change("python 学习")
        self.assertIsInstance(results, list)

    def test_keyword_scan(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python", "编程"], priority=10)
        pr.register_trigger(["database"], priority=5)

        matched = pr.keyword_scan("我在用 python 写代码")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].keywords, ["python", "编程"])

    def test_keyword_scan_substring(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python"])
        matched = pr.keyword_scan("I love pythonic code")  # 子串匹配
        self.assertEqual(len(matched), 1)

    def test_retrieve_proactive(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python"])
        results = pr.retrieve_proactive("python 编程", top_k=5)
        self.assertGreater(len(results), 0)

    def test_get_rules_sorted_by_priority(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["a"], priority=1)
        pr.register_trigger(["b"], priority=10)
        pr.register_trigger(["c"], priority=5)
        rules = pr.get_rules()
        self.assertEqual(rules[0].priority, 10)
        self.assertEqual(rules[1].priority, 5)
        self.assertEqual(rules[2].priority, 1)

    def test_get_history(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["python"])
        pr.on_context_change("python 学习")
        history = pr.get_history()
        self.assertGreater(len(history), 0)
        self.assertIn("context_preview", history[0])

    def test_get_stats(self):
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["a"])
        pr.register_trigger(["b"])
        pr.disable_trigger(pr.get_rules()[1].rule_id)
        stats = pr.get_stats()
        self.assertEqual(stats["total_rules"], 2)
        self.assertEqual(stats["enabled_rules"], 1)

    def test_persistence(self):
        m = self._make_memory()
        d = os.path.join(self._tmpdir, "persist")
        pr1 = ProactiveRetriever(m, data_dir=d)
        pr1.register_trigger(["python", "coding"])

        pr2 = ProactiveRetriever(m, data_dir=d)
        self.assertEqual(len(pr2._rules), 1)

    def test_priority_ordering(self):
        """高优先级规则先触发"""
        m = self._make_memory()
        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        trigger_order = []

        def make_cb(name):
            def cb(memories):
                trigger_order.append(name)
            return cb

        pr.register_trigger(["python"], priority=1, callback=make_cb("low"))
        pr.register_trigger(["python", "编程"], priority=10, callback=make_cb("high"))
        pr.on_context_change("python 编程")
        self.assertEqual(trigger_order[0], "high")


# ═══════════════════════════════════════════════════════════════
#  集成测试：模块间协作
# ═══════════════════════════════════════════════════════════════

class TestIntegration(_TmpDirMixin, unittest.TestCase):

    def test_memory_to_causal_pipeline(self):
        """记忆 → 因果图谱 管线"""
        m = Memory3D("integ_agent", data_dir=self._tmpdir)
        m.form("部署新版本导致服务崩溃", tags=["deploy", "crash"])
        m.form("数据库连接池耗尽导致超时", tags=["database", "timeout"])

        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("部署新版本", "服务崩溃", 0.85)
        cg.add_cause_effect("数据库连接池耗尽", "请求超时", 0.9)

        # 从记忆中发现的事件可以查询因果关系
        effects = cg.infer_effects("部署新版本")
        self.assertEqual(effects[0][0], "服务崩溃")

    def test_library_to_distiller_pipeline(self):
        """图书馆 → 蒸馏器 管线"""
        lib = ImperialLibrary(data_dir=self._tmpdir)
        lib.publish_knowledge("agent1", "Python 编程是最好的选择", tags=["python"])
        lib.publish_knowledge("agent2", "Python 编程适合数据科学", tags=["python", "data"])
        lib.publish_knowledge("agent3", "Python 编程广泛应用", tags=["python"])
        lib.publish_knowledge("agent4", "Python 编程效率很高", tags=["python"])

        m = Memory3D("pipe_agent", data_dir=self._tmpdir)
        for entry in lib.get_by_tags(["python"]):
            m.form(entry.content, tags=entry.tags, source_agent=entry.author)

        d = MemoryDistiller(m, data_dir=self._tmpdir)
        results = d.distill(min_evidence=2, min_confidence=0.1)
        self.assertGreater(len(results), 0)

    def test_proactive_with_causal(self):
        """主动检索 + 因果推理"""
        m = Memory3D("combo_agent", data_dir=self._tmpdir)
        m.form("服务器磁盘空间不足", tags=["disk", "server"])

        cg = CausalMemoryGraph(data_dir=self._tmpdir)
        cg.add_cause_effect("磁盘空间不足", "服务宕机", 0.9)

        pr = ProactiveRetriever(m, data_dir=self._tmpdir)
        pr.register_trigger(["磁盘", "disk"])
        results = pr.on_context_change("检查磁盘空间使用情况")
        self.assertGreater(len(results), 0)

        # 因果推理可以补充：磁盘不足 → 宕机
        causes = cg.infer_causes("服务宕机")
        self.assertEqual(causes[0][0], "磁盘空间不足")


if __name__ == "__main__":
    unittest.main()
