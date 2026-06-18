import unittest
import os
import shutil
import pandas as pd
from matcher import CopywritingMatcher

class TestCopywritingMatcher(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory inside the workspace for test files
        self.test_dir = os.path.join(os.getcwd(), 'test_temp')
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        self.inventory_path = os.path.join(self.test_dir, 'test_inventory.xlsx')

    def tearDown(self):
        # Clean up temporary test files
        import gc
        import time
        gc.collect()
        if os.path.exists(self.test_dir):
            for i in range(5):
                try:
                    shutil.rmtree(self.test_dir)
                    break
                except PermissionError:
                    time.sleep(0.1)

    def test_init_and_create_inventory(self):
        """测试初始化和自动创建库存文件"""
        matcher = CopywritingMatcher(self.inventory_path, id_prefix="TEST_")
        self.assertTrue(os.path.exists(self.inventory_path))
        self.assertEqual(len(matcher.df_inventory), 0)
        self.assertListEqual(list(matcher.df_inventory.columns), ['编号', '文案内容', '入库时间', '匹配次数'])

    def test_clean_text(self):
        """测试文本清洗"""
        matcher = CopywritingMatcher(self.inventory_path)
        self.assertEqual(matcher.clean_text("  Hello   World  \nNew Line "), "hello world new line")
        self.assertEqual(matcher.clean_text(None), "")
        self.assertEqual(matcher.clean_text(123), "123")

    def test_first_batch_processing(self):
        """测试在空白库存下处理第一批文案"""
        matcher = CopywritingMatcher(self.inventory_path, id_prefix="TEST_", threshold=0.8)
        new_texts = [
            "Prachtige rode bloemen in de tuin",  # TEST_000001
            "Een hele mooie dag om te wandelen",  # TEST_000002
            "Prachtige rode bloemen in de tuin"   # TEST_000001 (完全重复，应沿用)
        ]
        
        results = matcher.process_batch(new_texts)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['分配编号'], "TEST_000001")
        self.assertEqual(results[0]['匹配状态'], "新文案")
        
        self.assertEqual(results[1]['分配编号'], "TEST_000002")
        self.assertEqual(results[1]['匹配状态'], "新文案")
        
        # 第三条与第一条完全相同，应该沿用 TEST_000001
        self.assertEqual(results[2]['分配编号'], "TEST_000001")
        self.assertEqual(results[2]['匹配状态'], "已存在 (完全匹配)")
        
        # 验证数据库是否写入
        updated_matcher = CopywritingMatcher(self.inventory_path, id_prefix="TEST_")
        self.assertEqual(len(updated_matcher.df_inventory), 2)  # 库里应该只有2条不重复的数据
        
        # 验证 TEST_000001 的匹配次数
        row = updated_matcher.df_inventory[updated_matcher.df_inventory['编号'] == "TEST_000001"].iloc[0]
        self.assertEqual(row['匹配次数'], 2)  # 初始入库1次 + 重复匹配1次 = 2

    def test_fuzzy_matching(self):
        """测试模糊匹配"""
        matcher = CopywritingMatcher(self.inventory_path, id_prefix="TEST_", threshold=0.7)
        
        # 1. 写入基础文案到库中
        matcher.df_inventory = pd.DataFrame([
            {'编号': 'TEST_000001', '文案内容': 'De kat zit op de vensterbank en kijkt naar de vogels', '入库时间': '2026-06-15 09:00:00', '匹配次数': 1},
            {'编号': 'TEST_000002', '文案内容': 'Lekker eten koken met verse ingrediënten uit de supermarkt', '入库时间': '2026-06-15 09:00:00', '匹配次数': 1}
        ])
        matcher.save_inventory()
        
        # 重新加载以运行正常流程
        matcher.load_inventory()
        
        # 2. 准备有一些微小变化的新文案（模糊相似）以及完全不相关的新文案
        new_texts = [
            "De kat zit op de vensterbank en kijkt naar vogels",  # 删除了"de"，相似度极高，应该匹配 TEST_000001
            "Ik hou van programmeren in Python",                 # 全新文案，应该分配 TEST_000003
            "Lekker eten koken met verse ingrediënten uit supermarkt"   # 与 TEST_000002 类似（只少了"de"），相似度高，应该匹配 TEST_000002
        ]
        
        results = matcher.process_batch(new_texts)
        
        # 第1条文案：模糊匹配成功
        self.assertEqual(results[0]['分配编号'], "TEST_000001")
        self.assertEqual(results[0]['匹配状态'], "已存在 (模糊匹配)")
        
        # 第2条文案：分配新编号
        self.assertEqual(results[1]['分配编号'], "TEST_000003")
        self.assertEqual(results[1]['匹配状态'], "新文案")
        
        # 第3条文案：模糊匹配成功
        self.assertEqual(results[2]['分配编号'], "TEST_000002")
        self.assertEqual(results[2]['匹配状态'], "已存在 (模糊匹配)")
        
        # 数据库中现在应该有 3 条（原有 2 条 + 新增的 1 条）
        matcher_db = CopywritingMatcher(self.inventory_path, id_prefix="TEST_")
        self.assertEqual(len(matcher_db.df_inventory), 3)

    def test_semantic_matching(self):
        """测试 AI 语义比对模式（解决同义词和严重黏连拼写错误）"""
        matcher = CopywritingMatcher(self.inventory_path, id_prefix="TEST_", threshold=0.75, mode="semantic")
        
        # 1. 写入带有同义词句式的基础文案到库中
        matcher.df_inventory = pd.DataFrame([
            {'编号': 'TEST_000001', '文案内容': 'Huil niet om je huidige situatie. God heeft een beter plan voor je. Schrijf “Amen en er zal iets moois gebeuren', '入库时间': '2026-06-15 09:00:00', '匹配次数': 1}
        ])
        matcher.save_inventory()
        matcher.load_inventory()
        
        # 2. 准备包含同义词（Huil niet -> Maak je geen zorgen）和多处书写黏连（planvoorjou, zaliets）的新文案
        new_texts = [
            "MAAK JE GEEN ZORGEN OVER JE HUIDIGE SITUATIE GOD HEEFT EEN BETER PLANVOORJOU SCHRIJF'AMEN' EN ER ZALIETS MOOIS GEBEUREN! AMEN"
        ]
        
        results = matcher.process_batch(new_texts)
        
        # 验证 AI 语义模式下，由于语义相近，成功归入同一个编号
        self.assertEqual(results[0]['分配编号'], "TEST_000001")
        self.assertTrue("AI语义匹配" in results[0]['匹配状态'])
        
        # 库中匹配次数应该增加到 2
        matcher_db = CopywritingMatcher(self.inventory_path, id_prefix="TEST_", mode="semantic")
        row = matcher_db.df_inventory[matcher_db.df_inventory['编号'] == "TEST_000001"].iloc[0]
        self.assertEqual(row['匹配次数'], 2)

if __name__ == '__main__':
    unittest.main()
