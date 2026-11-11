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

if __name__=="__main__":
    mcp.run(transport="stdio")
