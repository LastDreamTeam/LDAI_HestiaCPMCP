# SPDX-License-Identifier: AGPL-3.0-only
"""A human approves a specific database deletion in the local account manager."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

@contextmanager
def database():
    from account_manager import location
    base=location().parent
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=base/"deletion-requests.sqlite"
    db=sqlite3.connect(path,timeout=10)
    if os.name!="nt":path.chmod(0o600)
    db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, target TEXT, expires INTEGER, state TEXT)")
    db.execute("DELETE FROM requests WHERE expires < ?",(int(time.time())-86400,))
    db.commit()
    try:
        with db:yield db
    finally:db.close()

def prepare(target):
    request_id=secrets.token_urlsafe(24)
    with database() as db:
        db.execute("INSERT INTO requests VALUES (?,?,?,?)",(request_id,json.dumps(target,sort_keys=True),int(time.time())+600,"pending"))
    return {"request_id":request_id,"target":target,"next":"在 HestiaCP 账号管理窗口的「审核删除」确认此项。10 分钟内使用同一请求 ID 执行。"}

def consume(request_id,target):
    with database() as db:
        change=db.execute("UPDATE requests SET state='consumed' WHERE id=? AND target=? AND expires>=? AND state='approved'",
                          (request_id,json.dumps(target,sort_keys=True),int(time.time())))
        if change.rowcount!=1:raise ValueError("删除尚未人工确认、目标已改变、请求已过期或已使用。")

def review(parent):
    from tkinter import messagebox
    with database() as db:
        rows=db.execute("SELECT id,target FROM requests WHERE state='pending' AND expires>=? ORDER BY expires",(int(time.time()),)).fetchall()
        if not rows:messagebox.showinfo("审核删除","没有待审核请求。",parent=parent);return
        for rid,body in rows:
            choice=messagebox.askyesnocancel("二次确认删除","要批准删除以下目标吗？\n"+json.dumps(json.loads(body),ensure_ascii=False,indent=2),parent=parent,default="no")
            if choice is None:break
            db.execute("UPDATE requests SET state=? WHERE id=? AND state='pending' AND expires>=?",("approved" if choice else "rejected",rid,int(time.time())))
