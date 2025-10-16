import re
import unittest

from scripts.plan import _build_flowchart


class TestBuildFlowchart(unittest.TestCase):
    def test_single_node_default_orientation_lr(self):
        plan_root = {
            "Node Type": "Seq Scan",
            "Relation Name": "users",
            "Plan Rows": 10,
            "Total Cost": 3.14159,
        }
        result = _build_flowchart(plan_root)
        self.assertEqual("""flowchart LR
n1["Seq Scan on users<br/>rows=10<br/>cost=3.14"]""",result)

    def test_parent_child_edge_tb_orientation(self):
        plan_root = {
            "Node Type": "Nested Loop",
            "Total Cost": 42.0,
            "Plan Rows": 5,
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Relation Name": "users",
                    "Index Name": "ix_users",
                    "Plan Rows": 5,
                    "Total Cost": 10.0,
                }
            ],
        }
        result = _build_flowchart(plan_root, orientation="TB")
        self.assertEqual("""flowchart TB
n1["Nested Loop<br/>rows=5<br/>cost=42.00"]
n2["Index Scan on users<br/>rows=5<br/>cost=10.00<br/>index=ix_users"]
n1 --> n2
linkStyle 0 stroke-width:2px""",result)

    def test_label_escaping_brackets_and_quotes(self):
        plan_root = {
            "Node Type": 'Seq "Scan"[weird]',
            "Relation Name": 'tbl[name]',
            "Index Name": 'ix["sq"][br]',
            "Plan Rows": 1,
            "Total Cost": 2,
        }
        result = _build_flowchart(plan_root)
        # Extract the first node's label content inside n1["..."]
        m = re.search(r'n1\["([^\"]+)"\]', result)
        self.assertIsNotNone(m, f"Could not parse node label from: {result}")
        label = m.group(1)
        # Mermaid label should escape brackets to parentheses and quotes to &quot;
        self.assertNotIn('[', label)
        self.assertNotIn(']', label)
        self.assertIn('&quot;', label)
        # Sanity check: key parts preserved
        self.assertIn('Seq &quot;Scan&quot;(weird) on tbl(name)', label)
        self.assertIn('index=ix(&quot;sq&quot;)(br)', label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
