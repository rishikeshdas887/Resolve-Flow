#!/usr/bin/env python3
"""Runner utility for Google Stitch MCP tools."""
import argparse
import json
import os
import subprocess
import urllib.request
from typing import Any

API_KEY = os.environ.get("STITCH_API_KEY", "")


class StitchMCPClient:
    def __init__(self, api_key: str = API_KEY):
        if not api_key:
            raise ValueError("STITCH_API_KEY environment variable is required")
        cmd = [
            "npx",
            "-y",
            "mcp-remote",
            "https://stitch.googleapis.com/mcp",
            "--header",
            f"X-Goog-Api-Key: {api_key}",
        ]
        self.process = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.req_id = 1
        self._initialize()

    def _send_recv(self, req: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(req)
        self.process.stdin.write(data + "\n")
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read()
                raise RuntimeError(f"Stitch process closed unexpectedly. Stderr: {stderr}")
            line = line.strip()
            if not line:
                continue
            try:
                res = json.loads(line)
                # Ignore notifications without id
                if "id" in res and res["id"] == req["id"]:
                    return res
            except json.JSONDecodeError:
                continue

    def _initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "resolveflow-builder", "version": "1.0"},
            },
        }
        self.req_id += 1
        self._send_recv(req)

        # initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.process.stdin.write(json.dumps(notif) + "\n")
        self.process.stdin.flush()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        req = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }
        self.req_id += 1
        return self._send_recv(req)

    def close(self):
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()


def download_file(url: str, dest_path: str):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:  # noqa: S310
        out.write(resp.read())
    print(f"Downloaded: {dest_path}")


def main():
    parser = argparse.ArgumentParser(description="Call Stitch MCP tool")
    parser.add_argument("--tool", required=True, help="Tool name")
    parser.add_argument("--args", default="{}", help="Tool arguments as JSON string")
    parser.add_argument("--download-dir", default=None, help="Directory to download returned assets")
    parser.add_argument("--prefix", default="", help="Prefix for downloaded asset filenames")
    args = parser.parse_args()

    tool_args = json.loads(args.args)
    client = StitchMCPClient()
    try:
        print(f"Invoking Stitch tool: {args.tool}...")
        resp = client.call_tool(args.tool, tool_args)
        print("Response received.")
        print(json.dumps(resp, indent=2))

        # Check for downloadUrl in output content
        if args.download_dir and "result" in resp:
            content = resp["result"].get("content", [])
            for item in content:
                if item.get("type") == "text":
                    try:
                        parsed = json.loads(item.get("text", "{}"))
                        # Check htmlCode downloadUrl
                        html_url = (
                            parsed.get("htmlCode", {}).get("downloadUrl")
                            or parsed.get("screen", {}).get("htmlCode", {}).get("downloadUrl")
                        )
                        if html_url:
                            dest = os.path.join(args.download_dir, f"{args.prefix}.html")
                            download_file(html_url, dest)

                        # Check screenshot downloadUrl
                        shot_url = (
                            parsed.get("screenshot", {}).get("downloadUrl")
                            or parsed.get("screen", {}).get("screenshot", {}).get("downloadUrl")
                        )
                        if shot_url:
                            dest = os.path.join(args.download_dir, f"{args.prefix}.png")
                            download_file(shot_url, dest)
                    except Exception as e:
                        print(f"Error parsing download URLs: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
