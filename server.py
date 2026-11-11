# SPDX-License-Identifier: AGPL-3.0-only
import ipaddress
import json
import os
import re
from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP
from native_http import clean,request,secret

mcp=FastMCP("hestiacp")

def panel(cmd, args, write=False):
    key=secret("HESTIA_KEY_FILE")
    if ":" not in key:
        raise ValueError("The key file must contain access_key:secret_key.")
    data={"hash":key,"cmd":cmd,"returncode":"yes" if write else "no"}
    data.update({f"arg{i}":v for i,v in enumerate(args,1)})
    raw=request("HESTIA_BASE_URL","/api/",urlencode(data).encode(),{"Content-Type":"application/x-www-form-urlencoded"})
    if write:
        if raw.strip()!=b"0":
            raise ValueError("HestiaCP did not confirm the requested change.")
        return True
    try:
        value=json.loads(raw)
    except ValueError:
        raise ValueError("HestiaCP did not return the requested JSON data.") from None
    if not isinstance(value,(list,dict)):
        raise ValueError("HestiaCP returned an unexpected response.")
    return clean(value)

def owner(user):
    user=user or os.getenv("HESTIA_USER","")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}",user):
        raise ValueError("Select a panel user or configure HESTIA_USER.")
    return user

def domain_name(domain):
    ascii_name=domain.strip().rstrip(".").encode("idna").decode().lower()
    if len(ascii_name)>253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",label) for label in ascii_name.split(".")):
        raise ValueError("Invalid domain.")
    return ascii_name

@mcp.tool()
def hestia_status():
    """Read system information visible to this API key."""
    return panel("v-list-sys-info",["json"])

@mcp.tool()
def hestia_list_users():
    """List panel users visible to this API key."""
    return panel("v-list-users",["json"])

@mcp.tool()
def hestia_list_websites(user:str=""):
    """List a user's hosted web domains."""
    return panel("v-list-web-domains",[owner(user),"json"])

@mcp.tool()
def hestia_get_website(domain:str,user:str=""):
    """Read a web domain's configuration."""
    return panel("v-list-web-domain",[owner(user),domain_name(domain),"json"])

@mcp.tool()
def hestia_list_dns_domains(user:str=""):
    """List the user's DNS zones."""
    return panel("v-list-dns-domains",[owner(user),"json"])

@mcp.tool()
def hestia_list_dns_records(domain:str,user:str=""):
    """List records in a selected DNS zone."""
    return panel("v-list-dns-records",[owner(user),domain_name(domain),"json"])

@mcp.tool()
def hestia_list_databases(user:str=""):
    """List database metadata visible to the panel user."""
    return panel("v-list-databases",[owner(user),"json"])

@mcp.tool()
def hestia_list_backups(user:str=""):
    """List backups for the selected panel user."""
    return panel("v-list-user-backups",[owner(user),"json"])

@mcp.tool()
def hestia_create_website(domain:str,ip:str,user:str=""):
    """Create the explicitly requested web domain and read back the result."""
    u=owner(user); name=domain_name(domain); address=str(ipaddress.ip_address(ip))
    if name in hestia_list_websites(u):
        raise ValueError("Web domain already exists.")
    panel("v-add-web-domain",[u,name,address,"yes"],write=True)
    record=hestia_get_website(name,u)
    return {"verified":name in record,"website":record}


from pathlib import Path
from typing import Literal
from deletion import prepare,consume

def object_name(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}",value):
        raise ValueError("Invalid Hestia object name.")
    return value

def new_password(reference):
    folder=os.getenv("HESTIA_PASSWORD_DIR")
    if not folder:raise ValueError("Set HESTIA_PASSWORD_DIR and provide an operator-provisioned password file.")
    root=Path(folder).expanduser().resolve(strict=True)
    p=root/(object_name(reference)+".txt")
    if p.is_symlink() or p.resolve().parent!=root or not p.is_file():raise ValueError("Unknown password reference.")
    value=p.read_text(encoding="utf-8-sig").rstrip("\r\n")
    if not value or "\n" in value or "\r" in value:raise ValueError("Invalid password file.")
    return value

@mcp.tool()
def hestia_get_database(database:str,user:str=""):
    """Read one full database name from hestia_list_databases."""
    return panel("v-list-database",[owner(user),object_name(database),"json"])

@mcp.tool()
def hestia_create_database(name:str,db_user:str,password_ref:str,engine:Literal["mysql","pgsql"]="mysql",user:str=""):
    """Create a database with unprefixed database and login names. Password comes from a local reference."""
    u=owner(user);n=object_name(name); login=object_name(db_user);full=u+"_"+n
    if engine=="pgsql":full=full.lower()
    if full in hestia_list_databases(u):raise ValueError("Database already exists.")
    panel("v-add-database",[u,n,login,new_password(password_ref),engine],write=True)
    return {"database":full,"verified":full in hestia_get_database(full,u)}

@mcp.tool()
def hestia_change_database_password(database:str,password_ref:str,user:str=""):
    """Change the password of a selected panel database using a local password reference."""
    u=owner(user);db=object_name(database)
    if db not in hestia_get_database(db,u):raise ValueError("Database not found.")
    panel("v-change-database-password",[u,db,new_password(password_ref)],write=True)
    return {"panel_accepted":True,"database":db}

def deletion_target(database,user):
    u=owner(user);db=object_name(database);record=hestia_get_database(db,u).get(db)
    if not isinstance(record,dict):raise ValueError("Database identity unavailable.")
    return {"site":os.environ["HESTIA_BASE_URL"],"account":os.getenv("LDAI_ACCOUNT_ALIAS","default"),
            "owner":u,"database":db,"identity":{k:record[k] for k in ("DBUSER","TYPE","HOST","DATE","TIME") if k in record}}

@mcp.tool()
def hestia_prepare_delete_database(database:str,user:str=""):
    """Prepare deletion of one named database. A human must approve in the account manager."""
    return prepare(deletion_target(database,user))

@mcp.tool()
def hestia_delete_database(database:str,request_id:str,user:str=""):
    """Consume an approved request for this exact database and verify its removal."""
    target=deletion_target(database,user)
    consume(request_id,target)
    panel("v-delete-database",[target["owner"],target["database"]],write=True)
    return {"verified":database not in hestia_list_databases(target["owner"])}

@mcp.tool()
def hestia_create_ftp(domain:str,ftp_name:str,password_ref:str,user:str=""):
    """Create a website FTP account in the website's default directory."""
    u=owner(user); d=domain_name(domain); ftp=object_name(ftp_name)
    if d not in hestia_get_website(d,u):raise ValueError("Website not found.")
    panel("v-add-web-domain-ftp",[u,d,ftp,new_password(password_ref)],write=True)
    return {"panel_accepted":True,"website":hestia_get_website(d,u)}

@mcp.tool()
def hestia_change_ftp_password(domain:str,ftp_name:str,password_ref:str,user:str=""):
    """Change the selected website FTP account password."""
    u=owner(user);d=domain_name(domain)
    panel("v-change-web-domain-ftp-password",[u,d,object_name(ftp_name),new_password(password_ref)],write=True)
    return {"panel_accepted":True,"domain":d}

@mcp.tool()
def hestia_website_directory(domain:str,user:str=""):
    """Read configured document root and aliases, or identify Hestia's conventional layout."""
    u=owner(user);d=domain_name(domain); record=hestia_get_website(d,u)[d]
    actual=record.get("CUSTOM_DOCROOT") or record.get("DOCUMENT_ROOT") or record.get("DOCROOT")
    return {"domain":d,"configured_root":actual,"conventional_root":f"/home/{u}/web/{d}/public_html",
            "aliases":record.get("ALIAS"),"filesystem_checked":False}

@mcp.tool()
def hestia_add_domain_alias(domain:str,alias:str,user:str=""):
    """Add a domain alias to one website and read back its settings."""
    u=owner(user);d=domain_name(domain);a=domain_name(alias)
    panel("v-add-web-domain-alias",[u,d,a],write=True)
    return hestia_get_website(d,u)


from table_data import Table

@mcp.tool()
def hestia_read_row(table:str,key:str):
    """Read a record by primary key from a locally allowlisted table."""
    return Table(table).change("read",key)

@mcp.tool()
def hestia_insert_row(table:str,key:str,values:dict):
    """Insert one record into an allowlisted table and read it back."""
    return Table(table).change("insert",key,values)

@mcp.tool()
def hestia_update_row(table:str,key:str,values:dict):
    """Update explicit columns in the selected record and read it back."""
    return Table(table).change("update",key,values)

@mcp.tool()
def hestia_prepare_delete_row(table:str,key:str):
    """Prepare deletion of one row. A human must approve it in the account manager."""
    return Table(table).change("prepare",key)

@mcp.tool()
def hestia_delete_row(table:str,key:str,request_id:str):
    """Delete one approved record only if its visible values still match the preview."""
    return Table(table).change("delete",key,ticket=request_id)

if __name__=="__main__":
    mcp.run(transport="stdio")
