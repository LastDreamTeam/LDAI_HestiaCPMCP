# SPDX-License-Identifier: AGPL-3.0-only
"""Parameterized row operations limited to operator-configured tables and fields."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

def identifier(name):
    if not isinstance(name,str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}",name):
        raise ValueError("Invalid table or column identifier.")
    return name

class Table:
    def __init__(self,alias):
        cfg=os.getenv("HESTIA_DATA_CONFIG_FILE")
        if not cfg:raise ValueError("Configure HESTIA_DATA_CONFIG_FILE with a scoped database login and table allowlist.")
        conf=json.loads(Path(cfg).expanduser().read_text(encoding="utf-8-sig"))
        entry=conf["tables"][alias]
        self.alias=alias;self.engine=conf["engine"];self.config=conf
        quote=chr(96) if self.engine=="mysql" else '"'
        self.quote=lambda n:quote+identifier(n)+quote
        self.table=self.quote(entry["table"]);self.pk=identifier(entry["primary_key"])
        self.fields=list(dict.fromkeys([self.pk,*[identifier(v) for v in entry["columns"]]]))
        self.mark="?" if self.engine=="sqlite" else "%s"
        self.identity={k:str(conf.get(k,"")) for k in ("engine","host","port","database","user")}
        self.identity.update(table=entry["table"],primary_key=self.pk,account=os.getenv("LDAI_ACCOUNT_ALIAS","default"))
    def connect(self):
        c=self.config
        if self.engine=="sqlite":
            uri=Path(c["database"]).expanduser().resolve(strict=True).as_uri()+"?mode=rw"
            return sqlite3.connect(uri,uri=True,timeout=10)
        password=Path(c["password_file"]).expanduser().read_text(encoding="utf-8-sig").rstrip("\r\n")
        if self.engine=="pgsql":
            import psycopg
            return psycopg.connect(host=c["host"],port=int(c.get("port",5432)),dbname=c["database"],user=c["user"],
                                   password=password,sslmode="verify-full",sslrootcert=c["ca_file"],connect_timeout=10)
        if self.engine=="mysql":
            import pymysql
            return pymysql.connect(host=c["host"],port=int(c.get("port",3306)),database=c["database"],user=c["user"],
                 password=password,ssl_ca=c["ca_file"],ssl_verify_cert=True,ssl_verify_identity=True,connect_timeout=10)
        raise ValueError("Supported engines are pgsql, mysql and sqlite.")
    def one(self,cur,key,lock=False):
        fields=",".join(map(self.quote,self.fields))
        cur.execute(f"SELECT {fields} FROM {self.table} WHERE {self.quote(self.pk)}={self.mark} LIMIT 2"+
                    (" FOR UPDATE" if lock and self.engine!="sqlite" else ""),(key,))
        rows=cur.fetchall()
        if len(rows)!=1:raise ValueError("A unique record is required.")
        return dict(zip(self.fields,rows[0]))
    def target(self,key,row):
        digest=hashlib.sha256(json.dumps(row,sort_keys=True,default=str).encode()).hexdigest()
        return {**self.identity,"key":key,"record_digest":digest}
    def change(self,action,key,values=None,ticket=None):
        from deletion import prepare,consume
        with closing(self.connect()) as db,closing(db.cursor()) as cur:
            try:
                if action in ("update","insert","delete") and self.engine=="sqlite":cur.execute("BEGIN IMMEDIATE")
                if action!="insert":row=self.one(cur,key,action in ("update","delete"))
                if action=="read":return row
                if action=="prepare":return prepare(self.target(key,row))
                if action=="delete":
                    consume(ticket,self.target(key,row))
                    cur.execute(f"DELETE FROM {self.table} WHERE {self.quote(self.pk)}={self.mark}",(key,))
                    if cur.rowcount!=1:raise ValueError("Unexpected affected row count.")
                    db.commit();return {"deleted":True}
                if not values or not set(values)<=set(self.fields) or self.pk in values:raise ValueError("Use permitted non-key fields.")
                if not all(isinstance(v,(str,int,float,bool)) or v is None for v in values.values()):raise ValueError("Use scalar values.")
                if action=="insert":
                    cols=[self.pk,*values]
                    cur.execute(f"INSERT INTO {self.table} ("+",".join(map(self.quote,cols))+") VALUES ("+",".join([self.mark]*len(cols))+")",(key,*values.values()))
                elif action=="update":
                    assignments=",".join(self.quote(k)+"="+self.mark for k in values)
                    cur.execute(f"UPDATE {self.table} SET {assignments} WHERE {self.quote(self.pk)}={self.mark}",(*values.values(),key))
                else:raise ValueError("Unknown action.")
                observed=self.one(cur,key);db.commit();return observed
            except Exception:
                db.rollback();raise
