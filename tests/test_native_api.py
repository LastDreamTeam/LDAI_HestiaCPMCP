# SPDX-License-Identifier: AGPL-3.0-only
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs
import server

class NativeAPI(unittest.TestCase):
    def test_create_and_read_back_with_selected_operator(self):
        calls = []
        def exchange(var,path,body,headers):
            data = {k:v[0] for k,v in parse_qs(body.decode()).items()}
            calls.append(data)
            self.assertEqual(path,"/api/")
            self.assertEqual(data["arg1"],"work")
            self.assertEqual(data["hash"],"fixture:key")
            if data["cmd"]=="v-add-web-domain":
                self.assertEqual(data["returncode"],"yes")
                return b"0"
            return b'{"site.example.org":{"status":"ok","password":"hidden"}}' if len(calls)==3 else b"{}"
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"credential"
            f.write_text("fixture:key",encoding="utf8")
            with patch.dict(os.environ,{"HESTIA_KEY_FILE":str(f),"HESTIA_USER":"work"}),patch.object(server,"request",exchange):
                result=server.hestia_create_website("site.example.org","127.0.0.1")
        self.assertEqual([x["cmd"] for x in calls],["v-list-web-domains","v-add-web-domain","v-list-web-domain"])
        self.assertTrue(result["verified"])
        self.assertNotIn("password",result["website"]["site.example.org"])
