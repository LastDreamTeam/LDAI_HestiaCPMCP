# SPDX-License-Identifier: AGPL-3.0-only
import json,os,sqlite3,tempfile,unittest,time
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import deletion
from table_data import Table

class DatabaseChanges(unittest.TestCase):
    def test_human_confirmation_and_record_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);db=d/"data.sqlite";cfg=d/"scope.json"
            with closing(sqlite3.connect(db)) as c, c:c.execute("CREATE TABLE items (id TEXT PRIMARY KEY, title TEXT)")
            cfg.write_text(json.dumps({"engine":"sqlite","database":str(db),"tables":{"items":{"table":"items","columns":["title"],"primary_key":"id"}}}))
            with patch.dict(os.environ,{"LDAI_ACCOUNTS_FILE":str(d/"accounts.json"),"HESTIA_DATA_CONFIG_FILE":str(cfg)}):
                t=Table("items");t.change("insert","one",{"title":"first"})
                ticket=t.change("prepare","one")["request_id"]
                with self.assertRaises(ValueError):t.change("delete","one",ticket=ticket)
                with deletion.database() as c:c.execute("UPDATE requests SET state='approved' WHERE id=?",(ticket,))
                t.change("update","one",{"title":"revised"})
                with self.assertRaises(ValueError):t.change("delete","one",ticket=ticket)
                new=t.change("prepare","one")["request_id"]
                with deletion.database() as c:c.execute("UPDATE requests SET state='approved',expires=0 WHERE id=?",(new,))
                with self.assertRaises(ValueError):t.change("delete","one",ticket=new)
                final=t.change("prepare","one")["request_id"]
                with deletion.database() as c:c.execute("UPDATE requests SET state='approved' WHERE id=?",(final,))
                target=t.target("one", t.change("read","one"))
                self.assertEqual(t.change("delete","one",ticket=final),{"deleted":True})
                with self.assertRaises(ValueError):deletion.consume(final,target)
                with self.assertRaises(ValueError):t.change("read","one")
