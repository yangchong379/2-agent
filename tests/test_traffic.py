import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('traffic_harness',ROOT/'scripts/traffic.py')
traffic=importlib.util.module_from_spec(spec);spec.loader.exec_module(traffic)

class TestTraffic(unittest.TestCase):
    def test_reproducible_stream_and_prefix(self):
        d,a=traffic.build(count=24);d2,b=traffic.build(count=48)
        self.assertEqual(d,d2);self.assertEqual(a,b[:24]);self.assertEqual(a,traffic.build(count=24)[1])
    def test_monitor_detects_false_success(self):
        data,events=traffic.build(count=2)
        if traffic.KIND=='scheduling':
            req={'request_id':'monitor','material_ids':['M01'],'channel':'douyin','preferred_slot':'2026-11-05T17:00+08:00','hard_time':True}
        else:
            req={'request_id':'monitor','topic':'夏日旅行','budget':15,'start_at':'2026-11-05T09:00+08:00','deadline':'2026-11-05T11:30+08:00'}
        with tempfile.TemporaryDirectory() as temp:
            store=traffic.Store(Path(temp)/'state.sqlite',data)
            try:
                before=traffic.inspect(store)
                r=traffic.Agent(traffic.MockModel(),store,data).run(req)
                after=traffic.inspect(store)
                self.assertTrue(all(traffic.audit(r,req,before,after).values()))
                if traffic.KIND=='scheduling':r['items'][0]['draft_id']='fabricated-id'
                else:r['actual_cost_total']+=1
                self.assertFalse(all(traffic.audit(r,req,before,after).values()))
            finally:store.close()

if __name__=='__main__':unittest.main()
