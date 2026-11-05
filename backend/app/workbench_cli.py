"""Authenticated Run CLI. Uses the same server enforcement as the web workbench."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default=os.getenv("GUI_WORKBENCH_URL","http://127.0.0.1:8000/api/workbench"))
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("devices")
    sub.add_parser("agents")
    for name in ["show","observe","start","pause","resume","stop","agent","assertions"]:
        sub.add_parser(name).add_argument("run_id")
    events=sub.add_parser("events");events.add_argument("run_id");events.add_argument("--after",type=int,default=0)
    coverage=sub.add_parser("coverage");coverage.add_argument("run_id");coverage.add_argument("phase",choices=["baseline","after"])
    action=sub.add_parser("act");action.add_argument("run_id");action.add_argument("--file",type=Path,required=True)
    create=sub.add_parser("create");create.add_argument("app_id");create.add_argument("--file",type=Path,required=True)
    args=parser.parse_args(argv)
    token=os.getenv("GUI_WORKBENCH_TOKEN")
    if not token: parser.error("Set GUI_WORKBENCH_TOKEN to your authenticated local session token")
    body=None;method="GET"
    if args.command in {"devices","agents"}: path="/"+args.command
    elif args.command=="create": path=f"/projects/{args.app_id}/runs";body=json.loads(args.file.read_text(encoding="utf-8"));method="POST"
    else:
        path=f"/runs/{args.run_id}"
        if args.command in {"start","pause","resume","stop"}: path+=f"/control/{args.command}";method="POST"
        elif args.command=="act": path+="/actions";body=json.loads(args.file.read_text(encoding="utf-8"));method="POST"
        elif args.command in {"observe","agent","assertions"}: path+="/"+args.command;method="POST"
        elif args.command=="coverage": path+="/coverage/"+args.phase;method="POST"
        elif args.command=="events": path+=f"/events?after={args.after}"
    request=Request(args.url.rstrip("/")+path,data=json.dumps(body).encode() if body is not None else None,
                    headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method=method)
    try:
        with urlopen(request,timeout=90) as response: print(response.read().decode())
    except HTTPError as exc:
        print(exc.read().decode());return 1
    return 0

if __name__=="__main__": raise SystemExit(main())
